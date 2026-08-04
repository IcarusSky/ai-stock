"""
AI Stock - 形态扫描 API

数据源：akshare 腾讯 K 线（stock_zh_a_hist_tx）+ 新浪全市场快照（stock_zh_a_spot）
原因：东财 push2/push2his 在当前网络下 TLS 层断连不可用。

核心扫描逻辑已下沉到 app.services.patterns_service。
全市场扫描改为异步任务模式，避免 HTTP 超时。
"""
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import asyncio

from app.services import patterns_service

router = APIRouter(prefix="/patterns", tags=["形态扫描"])


# ============================================================
# 请求/响应模型
# ============================================================

class PatternScanRequest(BaseModel):
    """形态扫描请求"""
    patterns: List[str] = ["ma5_above_ma10"]
    market: Optional[str] = "all"
    limit: int = 100


class PatternMatchItem(BaseModel):
    """形态匹配条目"""
    code: str
    name: str
    price: float
    change_pct: float
    match_type: str
    confidence: float
    signal: str
    extra: dict = {}


class PatternScanResponse(BaseModel):
    """形态扫描响应"""
    total: int
    items: List[PatternMatchItem]
    patterns: List[str]
    updated_at: str


class PatternStatsItem(BaseModel):
    """形态统计条目"""
    pattern: str
    name: str
    count: int
    avg_change_pct: float
    avg_confidence: float


class PatternStatsResponse(BaseModel):
    """形态统计响应"""
    items: List[PatternStatsItem]
    total_patterns: int
    updated_at: str


class ScanTaskResponse(BaseModel):
    """扫描任务创建响应"""
    task_id: str
    status: str
    message: str


class ScanTaskStatus(BaseModel):
    """扫描任务状态"""
    task_id: str
    status: str
    progress: dict
    patterns: List[str]
    items: List[PatternMatchItem]
    total: int
    error: Optional[str]
    updated_at: str


# ============================================================
# API 路由
# ============================================================

@router.post("/scan", response_model=ScanTaskResponse)
async def scan_patterns(
    request: PatternScanRequest,
    background_tasks: BackgroundTasks,
    stock_list: Optional[List[str]] = Query(None, description="指定股票代码列表，不填则全市场扫描"),
    max_stocks: int = Query(200, ge=1, le=500, description="最大扫描股票数（仅全市场模式）"),
    sync: bool = Query(False, description="是否同步返回结果（小批量可开启，全市场建议异步）"),
):
    """技术形态扫描（全市场或指定股票）

    默认行为：提交异步任务，立即返回 task_id，通过 GET /patterns/scan/{task_id} 轮询结果。
    小批量场景可传 sync=true 同步返回。

    支持的形态类型：
    - **ma5_above_ma10**: MA5 金叉 MA10（买入信号）
    - **ma5_below_ma10**: MA5 死叉 MA10（卖出信号）
    - **price_above_ma20**: 站上20日均线（买入信号）
    - **price_below_ma20**: 跌破20日均线（卖出信号）
    - **volume_surge**: 量能突破（买入信号）
    - **golden_cross**: 金叉量价配合（强烈买入）
    - **death_cross**: 死叉量价配合（强烈卖出）
    """
    valid_patterns = [p for p in request.patterns if p in patterns_service.PATTERN_DEFINITIONS]
    if not valid_patterns:
        raise HTTPException(status_code=400, detail="未提供有效的形态类型")

    # 指定股票列表或小批量模式允许同步返回
    if sync or stock_list:
        result = await patterns_service.scan_patterns_sync(
            patterns=valid_patterns,
            market=request.market or "all",
            limit=request.limit,
            stock_list=stock_list,
            max_stocks=max_stocks,
        )
        return {
            "task_id": "",
            "status": "sync_done",
            "message": "同步扫描完成",
            **result,
        }

    task_id = await patterns_service.create_scan_task(
        patterns=valid_patterns,
        market=request.market or "all",
        limit=request.limit,
        stock_list=stock_list,
        max_stocks=max_stocks,
    )

    background_tasks.add_task(
        patterns_service.run_scan_task,
        task_id,
        valid_patterns,
        request.market or "all",
        request.limit,
        stock_list,
        max_stocks,
    )

    return ScanTaskResponse(
        task_id=task_id,
        status="pending",
        message="扫描任务已提交，请通过 /patterns/scan/{task_id} 轮询结果",
    )


@router.get("/scan/{task_id}", response_model=ScanTaskStatus)
async def get_scan_task(task_id: str):
    """查询扫描任务状态/结果"""
    task = await patterns_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return ScanTaskStatus(**task)


@router.get("/stats", response_model=PatternStatsResponse)
async def get_pattern_stats(
    limit: int = Query(200, ge=1, le=500),
):
    """全市场形态统计（每种形态当前有多少只股票符合）"""
    patterns = list(patterns_service.PATTERN_DEFINITIONS.keys())
    stocks = await patterns_service.fetch_all_stocks()
    stocks = stocks[:limit]

    stats = {p: {"count": 0, "change_sum": 0.0, "confidence_sum": 0.0} for p in patterns}

    semaphore = asyncio.Semaphore(10)

    async def scan_one(stock: dict):
        code = stock["code"]
        df = await patterns_service.fetch_kline(code, limit=60)
        if df is None or len(df) < 25:
            return
        matches = patterns_service.detect_patterns(df, patterns)
        for m in matches:
            p = m["pattern"]
            stats[p]["count"] += 1
            stats[p]["confidence_sum"] += m["confidence"]
            if len(df) >= 2:
                change = float(df.iloc[-1]["close"]) / float(df.iloc[-2]["close"]) * 100 - 100
                stats[p]["change_sum"] += change

    tasks = [scan_one(s) for s in stocks]
    await asyncio.gather(*tasks, return_exceptions=True)

    items = []
    for p, s in stats.items():
        count = s["count"]
        items.append(PatternStatsItem(
            pattern=p,
            name=patterns_service.PATTERN_DEFINITIONS[p]["name"],
            count=count,
            avg_change_pct=round(s["change_sum"] / count, 2) if count > 0 else 0,
            avg_confidence=round(s["confidence_sum"] / count, 3) if count > 0 else 0,
        ))

    items.sort(key=lambda x: x.count, reverse=True)

    return PatternStatsResponse(
        items=items,
        total_patterns=len(items),
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@router.get("/defs", response_model=dict)
async def get_pattern_definitions():
    """获取所有形态定义"""
    return {
        "patterns": patterns_service.PATTERN_DEFINITIONS,
        "total": len(patterns_service.PATTERN_DEFINITIONS),
    }


@router.get("/stock/{code}", response_model=PatternScanResponse)
async def scan_stock_patterns(
    code: str,
    patterns: str = Query("ma5_above_ma10,ma5_below_ma10,price_above_ma20,volume_surge",
                          description="逗号分隔的形态类型"),
):
    """扫描单只股票的所有形态"""
    pattern_list = [p.strip() for p in patterns.split(",") if p.strip() in patterns_service.PATTERN_DEFINITIONS]
    if not pattern_list:
        raise HTTPException(status_code=400, detail="未提供有效的形态类型")

    df = await patterns_service.fetch_kline(code, limit=120)
    if df is None:
        raise HTTPException(status_code=404, detail=f"未找到股票 {code} 的 K 线数据")

    matches = patterns_service.detect_patterns(df, pattern_list)

    items = []
    for m in matches:
        change_pct = 0.0
        if len(df) >= 2:
            change_pct = float(df.iloc[-1]["close"]) / float(df.iloc[-2]["close"]) * 100 - 100
        items.append(PatternMatchItem(
            code=code,
            name="",
            price=float(df.iloc[-1]["close"]),
            change_pct=change_pct,
            match_type=m["pattern"],
            confidence=m["confidence"],
            signal=m["signal"],
            extra=m["extra"],
        ))

    return PatternScanResponse(
        total=len(items),
        items=items,
        patterns=pattern_list,
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

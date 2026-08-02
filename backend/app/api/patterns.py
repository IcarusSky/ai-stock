"""
AI Stock - 形态扫描 API

数据源：akshare 腾讯 K 线（stock_zh_a_hist_tx）+ 新浪全市场快照（stock_zh_a_spot）
原因：东财 push2/push2his 在当前网络下 TLS 层断连不可用。
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import asyncio
import akshare as ak
import pandas as pd

router = APIRouter(prefix="/patterns", tags=["形态扫描"])

# akshare 在并发 thread 下不稳定，用全局锁串行化
_AK_LOCK = asyncio.Lock()


# ============================================================
# 请求/响应模型
# ============================================================

class PatternScanRequest(BaseModel):
    """形态扫描请求"""
    patterns: List[str] = ["ma5_above_ma10"]  # 要扫描的形态类型
    market: Optional[str] = "all"               # all | sh | sz
    limit: int = 100                            # 返回条数上限


class PatternMatchItem(BaseModel):
    """形态匹配条目"""
    code: str
    name: str
    price: float
    change_pct: float
    match_type: str      # 形态类型
    confidence: float    # 置信度（0~1）
    signal: str          # buy | sell | neutral
    extra: dict = {}     # 附加数据（如 MA 值、成交量等）


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


# ============================================================
# 形态定义
# ============================================================

PATTERN_DEFINITIONS = {
    "ma5_above_ma10": {
        "name": "MA5 金叉 MA10",
        "signal": "buy",
        "description": "5日均线上穿10日均线，短期多头排列"
    },
    "ma5_below_ma10": {
        "name": "MA5 死叉 MA10",
        "signal": "sell",
        "description": "5日均线下穿10日均线，短期空头排列"
    },
    "price_above_ma20": {
        "name": "站上20日均线",
        "signal": "buy",
        "description": "收盘价站上20日均线，趋势转多"
    },
    "price_below_ma20": {
        "name": "跌破20日均线",
        "signal": "sell",
        "description": "收盘价跌破20日均线，趋势转空"
    },
    "volume_surge": {
        "name": "量能突破",
        "signal": "buy",
        "description": "成交量超过5日均量2倍"
    },
    "golden_cross": {
        "name": "MA5 金叉 MA10（量价配合）",
        "signal": "buy",
        "description": "MA5 上穿 MA10 且成交量放大"
    },
    "death_cross": {
        "name": "MA5 死叉 MA10（量价配合）",
        "signal": "sell",
        "description": "MA5 下穿 MA10 且成交量放大"
    },
}


# ============================================================
# K 线数据获取（腾讯接口，走 akshare）
# ============================================================

def _normalize_code_for_tx(code: str) -> str:
    """统一加上 sh/sz 前缀，腾讯接口要求 sz000001 / sh600000 格式"""
    code = code.strip().lower()
    if code.startswith(("sh", "sz", "bj")):
        return code
    if code.startswith("6"):
        return f"sh{code}"
    if code.startswith(("0", "3")):
        return f"sz{code}"
    if code.startswith(("4", "8", "9")):
        return f"bj{code}"
    return f"sz{code}"


async def _run_sync(fn, *args, **kwargs):
    """akshare 是同步库，丢到线程池跑；用全局锁防止并发崩溃"""
    async with _AK_LOCK:
        return await asyncio.to_thread(fn, *args, **kwargs)


async def fetch_kline(code: str, limit: int = 120) -> Optional[pd.DataFrame]:
    """获取股票日 K（腾讯数据源，前复权）"""
    tx_code = _normalize_code_for_tx(code)
    end = datetime.now()
    start = end - timedelta(days=max(limit * 2, 60))

    try:
        df = await _run_sync(
            ak.stock_zh_a_hist_tx,
            symbol=tx_code,
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust="qfq",
        )
    except Exception:
        return None

    if df is None or df.empty:
        return None

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df.tail(limit).reset_index(drop=True)


# ============================================================
# 形态计算
# ============================================================

def _calc_ma(df: pd.DataFrame, period: int, col: str = "close") -> pd.Series:
    """计算移动平均"""
    return df[col].rolling(window=period).mean()


def _detect_patterns(df: pd.DataFrame, patterns: List[str]) -> List[dict]:
    """检测形态，返回匹配列表"""
    if len(df) < 25:
        return []

    results = []
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # 计算均线
    df["ma5"] = _calc_ma(df, 5)
    df["ma10"] = _calc_ma(df, 10)
    df["ma20"] = _calc_ma(df, 20)
    df["ma5_vol"] = df["volume"].rolling(window=5).mean()

    latest_ma5 = df["ma5"].iloc[-1]
    latest_ma10 = df["ma10"].iloc[-1]
    latest_ma20 = df["ma20"].iloc[-1]
    prev_ma5 = df["ma5"].iloc[-2]
    prev_ma10 = df["ma10"].iloc[-2]

    # MA5 金叉 MA10
    if "ma5_above_ma10" in patterns:
        if pd.notna(latest_ma5) and pd.notna(latest_ma10):
            if prev_ma5 <= prev_ma10 and latest_ma5 > latest_ma10:
                results.append({
                    "pattern": "ma5_above_ma10",
                    "confidence": 0.85,
                    "signal": "buy",
                    "extra": {
                        "ma5": round(latest_ma5, 2),
                        "ma10": round(latest_ma10, 2),
                        "ma20": round(latest_ma20, 2) if pd.notna(latest_ma20) else None,
                    }
                })

    # MA5 死叉 MA10
    if "ma5_below_ma10" in patterns:
        if pd.notna(latest_ma5) and pd.notna(latest_ma10):
            if prev_ma5 >= prev_ma10 and latest_ma5 < latest_ma10:
                results.append({
                    "pattern": "ma5_below_ma10",
                    "confidence": 0.85,
                    "signal": "sell",
                    "extra": {
                        "ma5": round(latest_ma5, 2),
                        "ma10": round(latest_ma10, 2),
                        "ma20": round(latest_ma20, 2) if pd.notna(latest_ma20) else None,
                    }
                })

    # 站上20日均线
    if "price_above_ma20" in patterns:
        if pd.notna(latest_ma20) and pd.notna(prev["close"]):
            if prev["close"] <= prev_ma20 and latest["close"] > latest_ma20:
                results.append({
                    "pattern": "price_above_ma20",
                    "confidence": 0.80,
                    "signal": "buy",
                    "extra": {
                        "price": round(float(latest["close"]), 2),
                        "ma20": round(latest_ma20, 2),
                    }
                })

    # 跌破20日均线
    if "price_below_ma20" in patterns:
        if pd.notna(latest_ma20) and pd.notna(prev["close"]):
            if prev["close"] >= prev_ma20 and latest["close"] < latest_ma20:
                results.append({
                    "pattern": "price_below_ma20",
                    "confidence": 0.80,
                    "signal": "sell",
                    "extra": {
                        "price": round(float(latest["close"]), 2),
                        "ma20": round(latest_ma20, 2),
                    }
                })

    # 量能突破
    if "volume_surge" in patterns:
        ma5_vol = df["ma5_vol"].iloc[-1]
        if pd.notna(ma5_vol) and ma5_vol > 0:
            vol_ratio = float(latest["volume"]) / ma5_vol
            if vol_ratio >= 2.0:
                results.append({
                    "pattern": "volume_surge",
                    "confidence": min(vol_ratio / 3.0, 1.0),
                    "signal": "buy",
                    "extra": {
                        "volume": round(float(latest["volume"]), 0),
                        "ma5_volume": round(ma5_vol, 0),
                        "vol_ratio": round(vol_ratio, 2),
                    }
                })

    # 金叉（量价配合）
    if "golden_cross" in patterns:
        if pd.notna(latest_ma5) and pd.notna(latest_ma10):
            ma5_vol = df["ma5_vol"].iloc[-1]
            vol_ratio = float(latest["volume"]) / ma5_vol if pd.notna(ma5_vol) and ma5_vol > 0 else 0
            if (prev_ma5 <= prev_ma10 and latest_ma5 > latest_ma10 and vol_ratio >= 1.5):
                results.append({
                    "pattern": "golden_cross",
                    "confidence": 0.92,
                    "signal": "buy",
                    "extra": {
                        "ma5": round(latest_ma5, 2),
                        "ma10": round(latest_ma10, 2),
                        "vol_ratio": round(vol_ratio, 2),
                    }
                })

    # 死叉（量价配合）
    if "death_cross" in patterns:
        if pd.notna(latest_ma5) and pd.notna(latest_ma10):
            ma5_vol = df["ma5_vol"].iloc[-1]
            vol_ratio = float(latest["volume"]) / ma5_vol if pd.notna(ma5_vol) and ma5_vol > 0 else 0
            if (prev_ma5 >= prev_ma10 and latest_ma5 < latest_ma10 and vol_ratio >= 1.5):
                results.append({
                    "pattern": "death_cross",
                    "confidence": 0.92,
                    "signal": "sell",
                    "extra": {
                        "ma5": round(latest_ma5, 2),
                        "ma10": round(latest_ma10, 2),
                        "vol_ratio": round(vol_ratio, 2),
                    }
                })

    return results


# ============================================================
# 全市场股票列表（新浪快照，走 akshare）
# ============================================================

async def fetch_all_stocks() -> List[dict]:
    """获取全市场股票列表（新浪数据源）"""
    try:
        df = await _run_sync(ak.stock_zh_a_spot)
    except Exception:
        return []

    if df is None or df.empty:
        return []

    df = df.copy()
    df["code_str"] = df["代码"].astype(str).str.replace(r"^(sh|sz|bj)", "", regex=True)
    df["price_f"] = pd.to_numeric(df["最新价"], errors="coerce").fillna(0.0)
    df["pct_f"] = pd.to_numeric(df["涨跌幅"], errors="coerce").fillna(0.0)
    df = df[df["price_f"] > 0]

    return [
        {
            "code": row["code_str"],
            "name": str(row["名称"]),
            "price": float(row["price_f"]),
            "change_pct": float(row["pct_f"]),
        }
        for _, row in df.iterrows()
    ]


# ============================================================
# API 路由
# ============================================================

@router.post("/scan", response_model=PatternScanResponse)
async def scan_patterns(
    request: PatternScanRequest,
    stock_list: Optional[List[str]] = Query(None, description="指定股票代码列表，不填则全市场扫描"),
    max_stocks: int = Query(200, ge=1, le=500, description="最大扫描股票数（仅全市场模式）"),
):
    """技术形态扫描（全市场或指定股票）

    支持的形态类型：
    - **ma5_above_ma10**: MA5 金叉 MA10（买入信号）
    - **ma5_below_ma10**: MA5 死叉 MA10（卖出信号）
    - **price_above_ma20**: 站上20日均线（买入信号）
    - **price_below_ma20**: 跌破20日均线（卖出信号）
    - **volume_surge**: 量能突破（买入信号）
    - **golden_cross**: 金叉量价配合（强烈买入）
    - **death_cross**: 死叉量价配合（强烈卖出）

    - **request.patterns**: 要扫描的形态列表
    - **request.market**: all=全市场（默认）/ sh=上海 / sz=深圳
    - **request.limit**: 返回条数上限（默认100）
    - **stock_list**: 指定股票代码列表（如 ["000001", "600000"]）
    - **max_stocks**: 全市场模式下最大扫描股票数（默认200）
    """
    # 获取股票列表
    if stock_list:
        stocks = [{"code": c, "name": "", "price": 0, "change_pct": 0} for c in stock_list]
    else:
        stocks = await fetch_all_stocks()
        # 过滤市场
        if request.market == "sh":
            stocks = [s for s in stocks if s["code"].startswith("6")]
        elif request.market == "sz":
            stocks = [s for s in stocks if s["code"].startswith(("0", "3"))]
        stocks = stocks[:max_stocks]

    results: List[PatternMatchItem] = []

    # 批量扫描（并发控制）
    semaphore = asyncio.Semaphore(10)  # 最多10个并发

    async def scan_one(stock: dict) -> List[PatternMatchItem]:
        async with semaphore:
            code = stock["code"]
            df = await fetch_kline(code, limit=60)
            if df is None or len(df) < 25:
                return []

            matches = _detect_patterns(df, request.patterns)
            items = []
            for m in matches:
                items.append(PatternMatchItem(
                    code=code,
                    name=stock.get("name", ""),
                    price=float(df.iloc[-1]["close"]),
                    change_pct=float(df.iloc[-1]["close"]) / float(df.iloc[-2]["close"]) * 100 - 100 if len(df) >= 2 else 0,
                    match_type=m["pattern"],
                    confidence=m["confidence"],
                    signal=m["signal"],
                    extra=m["extra"],
                ))
            return items

    # 并发扫描
    tasks = [scan_one(s) for s in stocks]
    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in all_results:
        if isinstance(r, list):
            results.extend(r)

    # 按置信度排序
    results.sort(key=lambda x: x.confidence, reverse=True)

    return PatternScanResponse(
        total=len(results),
        items=results[:request.limit],
        patterns=request.patterns,
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@router.get("/stats", response_model=PatternStatsResponse)
async def get_pattern_stats(
    limit: int = Query(200, ge=1, le=500),
):
    """全市场形态统计（每种形态当前有多少只股票符合）

    用于市场情绪判断和策略参考
    """
    patterns = list(PATTERN_DEFINITIONS.keys())
    stocks = await fetch_all_stocks()
    stocks = stocks[:limit]

    stats = {p: {"count": 0, "change_sum": 0.0, "confidence_sum": 0.0} for p in patterns}

    semaphore = asyncio.Semaphore(10)

    async def scan_one(stock: dict):
        code = stock["code"]
        df = await fetch_kline(code, limit=60)
        if df is None or len(df) < 25:
            return
        matches = _detect_patterns(df, patterns)
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
            name=PATTERN_DEFINITIONS[p]["name"],
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
        "patterns": PATTERN_DEFINITIONS,
        "total": len(PATTERN_DEFINITIONS),
    }


@router.get("/stock/{code}", response_model=PatternScanResponse)
async def scan_stock_patterns(
    code: str,
    patterns: str = Query("ma5_above_ma10,ma5_below_ma10,price_above_ma20,volume_surge",
                          description="逗号分隔的形态类型"),
):
    """扫描单只股票的所有形态

    - **code**: 股票代码
    - **patterns**: 要检测的形态（逗号分隔）
    """
    pattern_list = [p.strip() for p in patterns.split(",") if p.strip() in PATTERN_DEFINITIONS]
    if not pattern_list:
        raise HTTPException(status_code=400, detail="未提供有效的形态类型")

    df = await fetch_kline(code, limit=120)
    if df is None:
        raise HTTPException(status_code=404, detail=f"未找到股票 {code} 的 K 线数据")

    matches = _detect_patterns(df, pattern_list)

    items = []
    for m in matches:
        items.append(PatternMatchItem(
            code=code,
            name="",
            price=float(df.iloc[-1]["close"]),
            change_pct=float(df.iloc[-1]["close"]) / float(df.iloc[-2]["close"]) * 100 - 100 if len(df) >= 2 else 0,
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

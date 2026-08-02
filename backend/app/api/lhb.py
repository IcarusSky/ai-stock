"""
AI Stock - 龙虎榜 API

数据源：akshare 东财 datacenter（stock_lhb_detail_em / stock_lhb_stock_statistic_em）
原因：东财 push2 实时快照在当前网络下 TLS 断连不可用，但 datacenter-web 域名可通。
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional

import akshare as ak
import pandas as pd
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/lhb", tags=["龙虎榜"])

# akshare 部分接口在并发 thread 下不稳定，用全局锁串行化
_AK_LOCK = asyncio.Lock()


class LHBStockItem(BaseModel):
    code: str
    name: str
    close_price: float
    change_pct: float
    turnover_rate: float = 0.0
    main_net_buy: float = 0.0
    main_buy_rate: float = 0.0
    reason: str = ""
    buy_seats: int = 0
    sell_seats: int = 0


class LHBResponse(BaseModel):
    items: List[LHBStockItem]
    total: int
    date: str
    updated_at: str


async def _run_sync(fn, *args, **kwargs):
    """akshare 是同步库，丢到线程池跑；用全局锁防止并发崩溃"""
    async with _AK_LOCK:
        return await asyncio.to_thread(fn, *args, **kwargs)


def _to_date_str(d: datetime) -> str:
    return d.strftime("%Y%m%d")


def _row_to_item(row: pd.Series) -> Optional[LHBStockItem]:
    try:
        return LHBStockItem(
            code=str(row.get("代码", "")).zfill(6),
            name=str(row.get("名称", "")),
            close_price=float(row.get("收盘价", 0) or 0),
            change_pct=float(row.get("涨跌幅", 0) or 0),
            turnover_rate=float(row.get("换手率", 0) or 0),
            main_net_buy=float(row.get("龙虎榜净买额", 0) or 0),
            main_buy_rate=float(row.get("净买额占总成交比", 0) or 0),
            reason=str(row.get("上榜原因", "") or ""),
        )
    except (ValueError, TypeError):
        return None


@router.get("/today", response_model=LHBResponse)
async def get_today_lhb(
    limit: int = Query(100, ge=1, le=200),
    direction: str = Query("all", description="all | buy | sell"),
):
    """获取今日龙虎榜（若今日无数据自动回退到最近一个交易日）"""
    today = datetime.now()
    # 龙虎榜数据 T+1 才完整，先尝试今日，失败/为空则回退到近 7 天
    for delta in range(0, 8):
        target = today - timedelta(days=delta)
        date_str = _to_date_str(target)
        try:
            df = await _run_sync(ak.stock_lhb_detail_em, start_date=date_str, end_date=date_str)
        except Exception:
            continue
        if df is not None and not df.empty:
            items = [it for it in (_row_to_item(r) for _, r in df.iterrows()) if it]
            if direction == "buy":
                items = [x for x in items if x.main_net_buy > 0]
            elif direction == "sell":
                items = [x for x in items if x.main_net_buy < 0]
            items.sort(key=lambda x: abs(x.main_net_buy), reverse=True)
            return LHBResponse(
                items=items[:limit],
                total=len(items),
                date=target.strftime("%Y-%m-%d"),
                updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )

    return LHBResponse(
        items=[],
        total=0,
        date=today.strftime("%Y-%m-%d"),
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@router.get("/history", response_model=LHBResponse)
async def get_lhb_history(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=500),
):
    """获取历史龙虎榜（按日期范围）"""
    end = end_date or datetime.now().strftime("%Y-%m-%d")
    start_fmt = start_date.replace("-", "")
    end_fmt = end.replace("-", "")

    try:
        df = await _run_sync(ak.stock_lhb_detail_em, start_date=start_fmt, end_date=end_fmt)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"龙虎榜历史数据接口异常: {e}")

    if df is None or df.empty:
        return LHBResponse(items=[], total=0, date=f"{start_date} ~ {end}",
                           updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    items = [it for it in (_row_to_item(r) for _, r in df.iterrows()) if it]
    items.sort(key=lambda x: abs(x.main_net_buy), reverse=True)

    return LHBResponse(
        items=items[:limit],
        total=len(items),
        date=f"{start_date} ~ {end}",
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@router.get("/stock/{code}", response_model=dict)
async def get_stock_lhb_history(code: str, limit: int = Query(20, ge=1, le=100)):
    """获取单只股票近 1 年龙虎榜记录"""
    end = datetime.now()
    start = end - timedelta(days=365)

    try:
        df = await _run_sync(
            ak.stock_lhb_detail_em,
            start_date=_to_date_str(start),
            end_date=_to_date_str(end),
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"龙虎榜接口异常: {e}")

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"未找到股票 {code} 的龙虎榜记录")

    code_str = str(code).lstrip("shsz").zfill(6)
    df = df.copy()
    df["code_str"] = df["代码"].astype(str).str.zfill(6)
    matched = df[df["code_str"] == code_str]

    if matched.empty:
        raise HTTPException(status_code=404, detail=f"未找到股票 {code} 的龙虎榜记录")

    records = []
    for _, row in matched.head(limit).iterrows():
        records.append({
            "date": str(row.get("上榜日", "")),
            "close_price": float(row.get("收盘价", 0) or 0),
            "change_pct": float(row.get("涨跌幅", 0) or 0),
            "turnover_rate": float(row.get("换手率", 0) or 0),
            "main_net_buy": float(row.get("龙虎榜净买额", 0) or 0),
            "main_buy_rate": float(row.get("净买额占总成交比", 0) or 0),
            "reason": str(row.get("上榜原因", "") or ""),
        })

    return {
        "code": code_str,
        "name": str(matched.iloc[0].get("名称", "")),
        "total": len(matched),
        "records": records,
    }


@router.get("/stats/daily", response_model=dict)
async def get_lhb_daily_stats(
    days: int = Query(5, ge=1, le=30, description="统计近N个交易日"),
):
    """龙虎榜统计（近 N 日上榜次数 + 资金）"""
    symbol_map = {5: "近一月", 10: "近一月", 30: "近一月", 60: "近三月", 180: "近六月", 365: "近一年"}
    symbol = symbol_map.get(days, "近一月")

    try:
        df = await _run_sync(ak.stock_lhb_stock_statistic_em, symbol=symbol)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"龙虎榜统计接口异常: {e}")

    if df is None or df.empty:
        return {
            "period": symbol,
            "total_count": 0,
            "inflow_count": 0,
            "outflow_count": 0,
            "total_main_net": 0.0,
            "top_inflow": [],
            "top_outflow": [],
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    df = df.copy()
    df["net"] = pd.to_numeric(df["龙虎榜净买额"], errors="coerce").fillna(0.0)
    df["pct_f"] = pd.to_numeric(df["涨跌幅"], errors="coerce").fillna(0.0)
    df["close_f"] = pd.to_numeric(df["收盘价"], errors="coerce").fillna(0.0)

    inflow = df[df["net"] > 0].sort_values("net", ascending=False).head(10)
    outflow = df[df["net"] < 0].sort_values("net", ascending=True).head(10)

    def _row_to_brief(r) -> dict:
        return {
            "code": str(r["代码"]).zfill(6),
            "name": str(r["名称"]),
            "close_price": float(r["close_f"]),
            "change_pct": float(r["pct_f"]),
            "main_net_buy": float(r["net"]),
            "on_list_count": int(r.get("上榜次数", 0) or 0),
        }

    return {
        "period": symbol,
        "total_count": len(df),
        "inflow_count": int((df["net"] > 0).sum()),
        "outflow_count": int((df["net"] < 0).sum()),
        "total_main_net": float(df["net"].sum()),
        "top_inflow": [_row_to_brief(r) for _, r in inflow.iterrows()],
        "top_outflow": [_row_to_brief(r) for _, r in outflow.iterrows()],
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

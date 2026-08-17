"""
AI Stock - 龙虎榜服务层

数据源：akshare 东财 datacenter（stock_lhb_detail_em）
核心数据获取逻辑从 API 路由剥离，供 HTTP API 与后台预热任务复用。
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import akshare as ak
import pandas as pd
from loguru import logger

from app.core.cache import cache_key, get_cache, set_cache, ttl_until_tomorrow

# 历史交易日龙虎榜数据已定格，缓存 30 天；当日数据缓存到次日
HISTORY_TTL = 30 * 86400

# akshare 部分接口底层依赖 py_mini_racer（V8），多线程并发初始化会导致进程崩溃
_AK_LOCK = asyncio.Lock()


async def run_ak_sync(fn, *args, **kwargs):
    """在线程池中串行调用 akshare 同步接口"""
    async with _AK_LOCK:
        return await asyncio.to_thread(fn, *args, **kwargs)


def to_date_str(dt: datetime) -> str:
    """datetime -> YYYYMMDD"""
    return dt.strftime("%Y%m%d")


def _to_float(value) -> float:
    """容错转换：'1,234.5' / '6.29%' / None -> float"""
    if value is None:
        return 0.0
    try:
        if isinstance(value, float) and pd.isna(value):
            return 0.0
        return float(str(value).replace(",", "").rstrip("%"))
    except (ValueError, TypeError):
        return 0.0


def row_to_item(row) -> Optional[dict]:
    """stock_lhb_detail_em 行 -> 统一 item 结构"""
    code_raw = str(row.get("代码", "") or "").strip()
    if not code_raw:
        return None
    return {
        "code": code_raw.zfill(6),
        "name": str(row.get("名称", "") or ""),
        "close_price": _to_float(row.get("收盘价")),
        "change_pct": _to_float(row.get("涨跌幅")),
        "turnover_rate": _to_float(row.get("换手率")),
        "main_net_buy": _to_float(row.get("龙虎榜净买额")),
        "main_buy_rate": _to_float(row.get("净买额占总成交比")),
        "reason": str(row.get("上榜原因", "") or ""),
        "buy_seats": 0,
        "sell_seats": 0,
    }


async def get_today_lhb(limit: int = 100, direction: str = "all", date: Optional[str] = None) -> dict:
    """
    获取指定日期龙虎榜；若该日无数据（非交易日），自动向前回退最多 7 天，
    取最近一个有数据的交易日。结果按交易日缓存到次日。
    """
    req_date = date or datetime.now().strftime("%Y-%m-%d")
    ck = cache_key("lhb:today", req_date, direction=direction, limit=limit)

    cached = await get_cache(ck)
    if cached:
        return cached

    df = None
    actual_date = req_date
    day = datetime.strptime(req_date, "%Y-%m-%d")
    for _ in range(7):
        dstr = day.strftime("%Y%m%d")
        df = await run_ak_sync(ak.stock_lhb_detail_em, start_date=dstr, end_date=dstr)
        if df is not None and not df.empty:
            actual_date = day.strftime("%Y-%m-%d")
            break
        day -= timedelta(days=1)

    if df is None or df.empty:
        result = {
            "items": [],
            "total": 0,
            "date": req_date,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        await set_cache(ck, result, expire=3600)
        return result

    items = [it for it in (row_to_item(r) for _, r in df.iterrows()) if it]

    if direction == "buy":
        items = [i for i in items if i["main_net_buy"] > 0]
    elif direction == "sell":
        items = [i for i in items if i["main_net_buy"] < 0]

    items.sort(key=lambda x: abs(x["main_net_buy"]), reverse=True)

    result = {
        "items": items[:limit],
        "total": len(items),
        "date": actual_date,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    # 历史交易日的龙虎榜已定格，长缓存 30 天；当日数据缓存到次日
    is_today = actual_date == datetime.now().strftime("%Y-%m-%d")
    await set_cache(ck, result, expire=ttl_until_tomorrow() if is_today else HISTORY_TTL)
    return result


async def get_lhb_daily_stats(days: int = 5) -> dict:
    """近 N 个交易日龙虎榜统计：每日上榜数量与净买额合计"""
    ck = cache_key("lhb:stats:daily", days=days)

    cached = await get_cache(ck)
    if cached:
        return cached

    end = datetime.now()
    start = end - timedelta(days=min(days * 2 + 10, 90))
    df = await run_ak_sync(
        ak.stock_lhb_detail_em,
        start_date=to_date_str(start),
        end_date=to_date_str(end),
    )

    stats = []
    if df is not None and not df.empty:
        df = df.copy()
        df["date_str"] = df["上榜日"].astype(str)
        df["net"] = df["龙虎榜净买额"].apply(_to_float)
        grouped = (
            df.groupby("date_str")
            .agg(count=("代码", "count"), net_buy=("net", "sum"))
            .reset_index()
            .sort_values("date_str", ascending=False)
            .head(days)
        )
        for _, r in grouped.iterrows():
            stats.append({
                "date": str(r["date_str"]),
                "count": int(r["count"]),
                "net_buy": float(r["net_buy"]),
            })

    result = {
        "days": days,
        "items": stats,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    await set_cache(ck, result, expire=ttl_until_tomorrow())
    return result

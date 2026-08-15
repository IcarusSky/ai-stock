"""
AI Stock - 主力资金流服务层

把 akshare 数据获取与缓存逻辑从 API 路由中剥离，供：
1. HTTP API 直接调用
2. 后台预热任务调用
"""
import asyncio
import re
from datetime import datetime
from typing import List, Optional

import akshare as ak
import pandas as pd
from loguru import logger

from app.core.cache import cache_key, get_cache, set_cache, ttl_until_tomorrow

# 历史快照保留 30 天（收盘后当日数据定格，转为长期快照供历史日期筛选）
HISTORY_TTL = 30 * 86400

# 同花顺个股资金流接口的 symbol 只支持这几种（不支持任意历史日期）
_PERIOD_SYMBOL = {
    "today": "即时",
    "3d": "3日排行",
    "5d": "5日排行",
    "10d": "10日排行",
    "20d": "20日排行",
}

# 不同排行周期返回的列名不同
_PERIOD_COLUMNS = {
    "即时": {"net": "净额", "pct": "涨跌幅", "turnover": "换手率"},
    "3日排行": {"net": "资金流入净额", "pct": "阶段涨跌幅", "turnover": "连续换手率"},
    "5日排行": {"net": "资金流入净额", "pct": "阶段涨跌幅", "turnover": "连续换手率"},
    "10d排行": {"net": "资金流入净额", "pct": "阶段涨跌幅", "turnover": "连续换手率"},
    "20日排行": {"net": "资金流入净额", "pct": "阶段涨跌幅", "turnover": "连续换手率"},
}


def _cache_expire(trade_date: str) -> int:
    """缓存有效期：收盘后（>=15点）的当日数据已定格，转 30 天历史快照；其余到次日"""
    today = datetime.now().strftime("%Y-%m-%d")
    if trade_date != today:
        return HISTORY_TTL
    if datetime.now().hour >= 15:
        return HISTORY_TTL
    return ttl_until_tomorrow()


_CN_NUM_RE = re.compile(r"^(-?[\d.]+)(亿|万)?$")


def _parse_cn_number(value) -> float:
    """解析 '3.38亿' / '-8306.28万' / 50.86 这类中文数字串，统一返回元。"""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "")
    if not s:
        return 0.0
    m = _CN_NUM_RE.match(s)
    if not m:
        try:
            return float(s)
        except ValueError:
            return 0.0
    num = float(m.group(1))
    unit = m.group(2)
    if unit == "亿":
        return num * 1e8
    if unit == "万":
        return num * 1e4
    return num


def _parse_pct(value) -> float:
    """解析 '20.01%' / 6.29 -> 20.01"""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().rstrip("%")
    try:
        return float(s)
    except ValueError:
        return 0.0


# akshare 同花顺接口依赖 py_mini_racer（V8），多线程并发初始化会导致进程崩溃
_AK_LOCK = asyncio.Lock()


async def _run_ak_sync(fn, *args, **kwargs):
    """在线程池中串行调用 akshare。"""
    async with _AK_LOCK:
        return await asyncio.to_thread(fn, *args, **kwargs)


def _fetch_individual_flow(symbol: str = "即时") -> pd.DataFrame:
    return ak.stock_fund_flow_individual(symbol=symbol)


def _fetch_sector_flow(sector_type: str, symbol: str = "即时") -> pd.DataFrame:
    if sector_type == "industry":
        return ak.stock_fund_flow_industry(symbol=symbol)
    return ak.stock_fund_flow_concept(symbol=symbol)


# ============================================================
# 对外服务函数
# ============================================================

async def get_money_flow_rank(
    period: str = "today",
    direction: str = "inflow",
    limit: int = 100,
    date: Optional[str] = None,
) -> dict:
    """个股主力净流入排名，返回可直接缓存的字典

    日期规则：
    - 当日：按 period 实时拉取同花顺排行（today/3d/5d/10d/20d 真正生效）
    - 历史日期：同花顺不提供任意历史资金流，仅返回系统每日积累的历史快照；
      无快照时返回空列表并在 message 中说明，不报错
    """
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    is_today = trade_date == datetime.now().strftime("%Y-%m-%d")
    cache_key_name = cache_key("moneyflow:rank", trade_date, period=period, direction=direction, limit=limit)

    cached = await get_cache(cache_key_name)
    if cached:
        return cached

    if not is_today:
        return {
            "items": [],
            "total": 0,
            "period": period,
            "date": trade_date,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message": "该日期暂无资金流历史快照（历史快照自系统部署后每日收盘自动积累）",
        }

    symbol = _PERIOD_SYMBOL.get(period, "即时")
    cols = _PERIOD_COLUMNS[symbol]
    try:
        df = await _run_ak_sync(_fetch_individual_flow, symbol)
    except Exception as e:
        logger.warning(f"同花顺个股资金流接口异常: {e}")
        raise

    if df is None or df.empty:
        result = {
            "items": [],
            "total": 0,
            "period": period,
            "date": trade_date,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        await set_cache(cache_key_name, result, expire=_cache_expire(trade_date))
        return result

    df = df.copy()
    df["net"] = df[cols["net"]].apply(_parse_cn_number)
    df["price_f"] = pd.to_numeric(df["最新价"], errors="coerce").fillna(0.0)
    df["pct_f"] = df[cols["pct"]].apply(_parse_pct)
    df["turnover"] = df[cols["turnover"]].apply(_parse_pct)

    df = df[df["net"] != 0]
    df = df.sort_values("net", ascending=(direction == "outflow"))
    df = df.head(limit)

    items = []
    for i, (_, row) in enumerate(df.iterrows()):
        items.append({
            "code": str(row["股票代码"]).zfill(6),
            "name": str(row["股票简称"]),
            "price": float(row["price_f"]),
            "change_pct": float(row["pct_f"]),
            "main_net_inflow": float(row["net"]),
            "main_inflow_rate": float(row["turnover"]),
            "rank": i + 1,
        })

    result = {
        "items": items,
        "total": len(items),
        "period": period,
        "date": trade_date,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    await set_cache(cache_key_name, result, expire=_cache_expire(trade_date))
    return result


async def get_sector_money_flow(
    sector_type: str = "concept",
    limit: int = 50,
    date: Optional[str] = None,
) -> dict:
    """板块资金流向排名（同花顺仅提供当日数据，历史日期读快照）"""
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    is_today = trade_date == datetime.now().strftime("%Y-%m-%d")
    cache_key_name = cache_key("moneyflow:sector", trade_date, sector_type=sector_type, limit=limit)

    cached = await get_cache(cache_key_name)
    if cached:
        return cached

    if not is_today:
        return {
            "items": [],
            "total": 0,
            "period": "today",
            "date": trade_date,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message": "该日期暂无板块资金流历史快照（历史快照自系统部署后每日收盘自动积累）",
        }

    symbol = "即时"
    try:
        df = await _run_ak_sync(_fetch_sector_flow, sector_type, symbol)
    except Exception as e:
        logger.warning(f"同花顺板块资金流接口异常: {e}")
        raise

    if df is None or df.empty:
        result = {
            "items": [],
            "total": 0,
            "period": "today",
            "date": trade_date,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        await set_cache(cache_key_name, result, expire=_cache_expire(trade_date))
        return result

    df = df.copy()
    df["net"] = pd.to_numeric(df["净额"], errors="coerce").fillna(0.0) * 1e8
    df["pct_f"] = pd.to_numeric(df["行业-涨跌幅"], errors="coerce").fillna(0.0)
    df = df[df["net"] != 0].sort_values("net", ascending=False).head(limit)

    name_col = "行业"
    items = []
    for i, (_, row) in enumerate(df.iterrows()):
        items.append({
            "code": f"{sector_type[:2].upper()}{i+1:04d}",
            "name": str(row[name_col]),
            "change_pct": float(row["pct_f"]),
            "main_net_inflow": float(row["net"]),
            "main_inflow_rate": 0.0,
        })

    result = {
        "items": items,
        "total": len(items),
        "period": "today",
        "date": trade_date,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    await set_cache(cache_key_name, result, expire=_cache_expire(trade_date))
    return result


async def get_market_flow_overview(date: Optional[str] = None) -> dict:
    """市场整体资金流概览（同花顺仅提供当日数据，历史日期读快照）"""
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    is_today = trade_date == datetime.now().strftime("%Y-%m-%d")
    cache_key_name = cache_key("moneyflow:overview", trade_date)

    cached = await get_cache(cache_key_name)
    if cached:
        return cached

    if not is_today:
        return {
            "total_stocks": 0,
            "inflow_count": 0,
            "outflow_count": 0,
            "total_main_inflow": 0.0,
            "total_main_outflow": 0.0,
            "net_flow": 0.0,
            "date": trade_date,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message": "该日期暂无资金流历史快照（历史快照自系统部署后每日收盘自动积累）",
        }

    symbol = "即时"
    try:
        df = await _run_ak_sync(_fetch_individual_flow, symbol)
    except Exception as e:
        logger.warning(f"同花顺资金流接口异常: {e}")
        raise

    if df is None or df.empty:
        result = {
            "total_stocks": 0,
            "inflow_count": 0,
            "outflow_count": 0,
            "total_main_inflow": 0.0,
            "total_main_outflow": 0.0,
            "net_flow": 0.0,
            "date": trade_date,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        await set_cache(cache_key_name, result, expire=_cache_expire(trade_date))
        return result

    df = df.copy()
    df["net"] = df["净额"].apply(_parse_cn_number)
    inflow = df[df["net"] > 0]["net"].sum()
    outflow = df[df["net"] < 0]["net"].sum()

    result = {
        "total_stocks": len(df),
        "inflow_count": int((df["net"] > 0).sum()),
        "outflow_count": int((df["net"] < 0).sum()),
        "total_main_inflow": float(inflow),
        "total_main_outflow": float(abs(outflow)),
        "net_flow": float(inflow + outflow),
        "date": trade_date,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    await set_cache(cache_key_name, result, expire=_cache_expire(trade_date))
    return result

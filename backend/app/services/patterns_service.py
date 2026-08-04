"""
AI Stock - 形态扫描服务层

把形态扫描核心逻辑从 API 路由中剥离，支持：
1. HTTP API 同步扫描（小批量 / 单只股票）
2. 异步任务扫描（全市场 / 大批量），结果写入 Redis 后通过 task_id 查询
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

import akshare as ak
import pandas as pd
from loguru import logger

from app.core.cache import get_cache, set_cache


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
# K 线数据获取
# ============================================================

_AK_LOCK = asyncio.Lock()


async def _run_ak_sync(fn, *args, **kwargs):
    """akshare 是同步库，丢到线程池跑；用全局锁防止并发崩溃"""
    async with _AK_LOCK:
        return await asyncio.to_thread(fn, *args, **kwargs)


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


async def fetch_kline(code: str, limit: int = 120) -> Optional[pd.DataFrame]:
    """获取股票日 K（腾讯数据源，前复权）"""
    tx_code = _normalize_code_for_tx(code)
    end = datetime.now()
    start = end - timedelta(days=max(limit * 2, 60))

    try:
        df = await _run_ak_sync(
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


async def fetch_all_stocks() -> List[dict]:
    """获取全市场股票列表（新浪数据源）"""
    try:
        df = await _run_ak_sync(ak.stock_zh_a_spot)
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
# 形态计算
# ============================================================

def _calc_ma(df: pd.DataFrame, period: int, col: str = "close") -> pd.Series:
    return df[col].rolling(window=period).mean()


def detect_patterns(df: pd.DataFrame, patterns: List[str]) -> List[dict]:
    """检测形态，返回匹配列表"""
    if len(df) < 25:
        return []

    results = []
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    df["ma5"] = _calc_ma(df, 5)
    df["ma10"] = _calc_ma(df, 10)
    df["ma20"] = _calc_ma(df, 20)
    df["ma5_vol"] = df["volume"].rolling(window=5).mean()

    latest_ma5 = df["ma5"].iloc[-1]
    latest_ma10 = df["ma10"].iloc[-1]
    latest_ma20 = df["ma20"].iloc[-1]
    prev_ma5 = df["ma5"].iloc[-2]
    prev_ma10 = df["ma10"].iloc[-2]

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
# 异步任务扫描
# ============================================================

TASK_TTL = 3600  # 任务结果保留 1 小时

# 当 Redis 不可用时的内存兜底（进程内有效，重启丢失）
_TASK_MEMORY: dict[str, dict] = {}


def _task_key(task_id: str) -> str:
    return f"pattern:task:{task_id}"


def _new_task_id() -> str:
    return uuid.uuid4().hex


async def _save_task(task_id: str, payload: dict):
    _TASK_MEMORY[task_id] = payload
    await set_cache(_task_key(task_id), payload, expire=TASK_TTL)


async def get_task(task_id: str) -> Optional[dict]:
    # 优先读 Redis，未命中则读内存兜底
    cached = await get_cache(_task_key(task_id))
    if cached:
        return cached
    return _TASK_MEMORY.get(task_id)


async def run_scan_task(
    task_id: str,
    patterns: List[str],
    market: str,
    limit: int,
    stock_list: Optional[List[str]],
    max_stocks: int,
):
    """后台执行扫描任务并持续更新状态"""
    await _save_task(task_id, {
        "task_id": task_id,
        "status": "running",
        "progress": {"total": 0, "processed": 0},
        "patterns": patterns,
        "items": [],
        "total": 0,
        "error": None,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })

    try:
        if stock_list:
            stocks = [{"code": c, "name": "", "price": 0, "change_pct": 0} for c in stock_list]
        else:
            stocks = await fetch_all_stocks()
            if market == "sh":
                stocks = [s for s in stocks if s["code"].startswith("6")]
            elif market == "sz":
                stocks = [s for s in stocks if s["code"].startswith(("0", "3"))]
            stocks = stocks[:max_stocks]

        total = len(stocks)
        await _save_task(task_id, {
            "task_id": task_id,
            "status": "running",
            "progress": {"total": total, "processed": 0},
            "patterns": patterns,
            "items": [],
            "total": 0,
            "error": None,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

        results = []
        semaphore = asyncio.Semaphore(10)

        async def scan_one(idx: int, stock: dict) -> List[dict]:
            async with semaphore:
                code = stock["code"]
                df = await fetch_kline(code, limit=60)
                if df is None or len(df) < 25:
                    return []

                matches = detect_patterns(df, patterns)
                items = []
                for m in matches:
                    change_pct = 0.0
                    if len(df) >= 2:
                        change_pct = float(df.iloc[-1]["close"]) / float(df.iloc[-2]["close"]) * 100 - 100
                    items.append({
                        "code": code,
                        "name": stock.get("name", ""),
                        "price": round(float(df.iloc[-1]["close"]), 2),
                        "change_pct": round(change_pct, 2),
                        "match_type": m["pattern"],
                        "confidence": m["confidence"],
                        "signal": m["signal"],
                        "extra": m["extra"],
                    })

                # 每处理 10 只更新一次进度
                if (idx + 1) % 10 == 0 or idx == total - 1:
                    await _save_task(task_id, {
                        "task_id": task_id,
                        "status": "running",
                        "progress": {"total": total, "processed": idx + 1},
                        "patterns": patterns,
                        "items": results + items,
                        "total": len(results) + len(items),
                        "error": None,
                        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    })
                return items

        tasks = [scan_one(i, s) for i, s in enumerate(stocks)]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in all_results:
            if isinstance(r, list):
                results.extend(r)

        results.sort(key=lambda x: x["confidence"], reverse=True)

        await _save_task(task_id, {
            "task_id": task_id,
            "status": "done",
            "progress": {"total": total, "processed": total},
            "patterns": patterns,
            "items": results[:limit],
            "total": len(results),
            "error": None,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    except Exception as e:
        logger.exception(f"形态扫描任务 {task_id} 失败")
        await _save_task(task_id, {
            "task_id": task_id,
            "status": "failed",
            "progress": {"total": 0, "processed": 0},
            "patterns": patterns,
            "items": [],
            "total": 0,
            "error": str(e),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })


async def create_scan_task(
    patterns: List[str],
    market: str,
    limit: int,
    stock_list: Optional[List[str]],
    max_stocks: int,
) -> str:
    """创建扫描任务，返回 task_id"""
    task_id = _new_task_id()
    # 立即保存 pending 状态
    await _save_task(task_id, {
        "task_id": task_id,
        "status": "pending",
        "progress": {"total": 0, "processed": 0},
        "patterns": patterns,
        "items": [],
        "total": 0,
        "error": None,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    return task_id


async def scan_patterns_sync(
    patterns: List[str],
    market: str,
    limit: int,
    stock_list: Optional[List[str]],
    max_stocks: int,
) -> dict:
    """同步扫描：用于小批量或单只股票"""
    if stock_list:
        stocks = [{"code": c, "name": "", "price": 0, "change_pct": 0} for c in stock_list]
    else:
        stocks = await fetch_all_stocks()
        if market == "sh":
            stocks = [s for s in stocks if s["code"].startswith("6")]
        elif market == "sz":
            stocks = [s for s in stocks if s["code"].startswith(("0", "3"))]
        stocks = stocks[:max_stocks]

    results = []
    semaphore = asyncio.Semaphore(10)

    async def scan_one(stock: dict) -> List[dict]:
        async with semaphore:
            code = stock["code"]
            df = await fetch_kline(code, limit=60)
            if df is None or len(df) < 25:
                return []

            matches = detect_patterns(df, patterns)
            items = []
            for m in matches:
                change_pct = 0.0
                if len(df) >= 2:
                    change_pct = float(df.iloc[-1]["close"]) / float(df.iloc[-2]["close"]) * 100 - 100
                items.append({
                    "code": code,
                    "name": stock.get("name", ""),
                    "price": round(float(df.iloc[-1]["close"]), 2),
                    "change_pct": round(change_pct, 2),
                    "match_type": m["pattern"],
                    "confidence": m["confidence"],
                    "signal": m["signal"],
                    "extra": m["extra"],
                })
            return items

    tasks = [scan_one(s) for s in stocks]
    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in all_results:
        if isinstance(r, list):
            results.extend(r)

    results.sort(key=lambda x: x["confidence"], reverse=True)

    return {
        "total": len(results),
        "items": results[:limit],
        "patterns": patterns,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

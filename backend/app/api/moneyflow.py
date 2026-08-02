"""
AI Stock - 主力资金流 API

数据源：akshare 同花顺资金流接口（stock_fund_flow_individual / industry / concept）
原因：东财 push2 在当前网络下 TLS 层断连不可用。
"""
import asyncio
import re
from datetime import datetime
from typing import List, Optional

import akshare as ak
import pandas as pd
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/moneyflow", tags=["资金流"])

# akshare 同花顺接口依赖 py_mini_racer（V8），多线程并发初始化会导致进程崩溃
# 用全局 asyncio.Lock 串行化所有 akshare 调用
_AK_LOCK = asyncio.Lock()


class StockMoneyFlow(BaseModel):
    """单只股票资金流数据"""
    code: str
    name: str
    price: float
    change_pct: float
    main_net_inflow: float
    main_net_inflow_3d: float = 0.0
    main_net_inflow_5d: float = 0.0
    main_inflow_rate: float = 0.0
    super_net_inflow: float = 0.0
    big_net_inflow: float = 0.0
    mid_net_inflow: float = 0.0
    small_net_inflow: float = 0.0


class MoneyFlowRankItem(BaseModel):
    code: str
    name: str
    price: float
    change_pct: float
    main_net_inflow: float
    main_inflow_rate: float
    rank: int


class MoneyFlowResponse(BaseModel):
    items: List[MoneyFlowRankItem]
    total: int
    period: str
    updated_at: str


class SectorFlowItem(BaseModel):
    code: str
    name: str
    change_pct: float
    main_net_inflow: float
    main_inflow_rate: float


class SectorFlowResponse(BaseModel):
    items: List[SectorFlowItem]
    total: int
    period: str
    updated_at: str


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


async def _run_sync(fn, *args, **kwargs):
    """akshare 是同步库，丢到线程池跑以免阻塞事件循环；用全局锁防止 V8 并发初始化崩溃"""
    async with _AK_LOCK:
        return await asyncio.to_thread(fn, *args, **kwargs)


def _fetch_individual_flow(symbol: str = "即时") -> pd.DataFrame:
    return ak.stock_fund_flow_individual(symbol=symbol)


def _fetch_sector_flow(sector_type: str) -> pd.DataFrame:
    if sector_type == "industry":
        return ak.stock_fund_flow_industry(symbol="即时")
    return ak.stock_fund_flow_concept(symbol="即时")


@router.get("/rank", response_model=MoneyFlowResponse)
async def get_money_flow_rank(
    period: str = Query("today", description="today | 3d | 5d（同花顺接口仅提供即时，3d/5d 当前回退到即时）"),
    limit: int = Query(100, ge=1, le=500),
    direction: str = Query("inflow", description="inflow | outflow 主力流入/流出"),
):
    """主力资金流排名（同花顺数据源）"""
    try:
        df = await _run_sync(_fetch_individual_flow, "即时")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"同花顺资金流接口异常: {e}")

    if df is None or df.empty:
        return MoneyFlowResponse(items=[], total=0, period=period,
                                 updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    df = df.copy()
    df["net"] = df["净额"].apply(_parse_cn_number)
    df["price_f"] = pd.to_numeric(df["最新价"], errors="coerce").fillna(0.0)
    df["pct_f"] = df["涨跌幅"].apply(_parse_pct)
    df["turnover"] = df["换手率"].apply(_parse_pct)

    df = df[df["net"] != 0]
    if direction == "outflow":
        df = df.sort_values("net", ascending=True)
    else:
        df = df.sort_values("net", ascending=False)
    df = df.head(limit)

    items = [
        MoneyFlowRankItem(
            code=str(row["股票代码"]).zfill(6),
            name=str(row["股票简称"]),
            price=float(row["price_f"]),
            change_pct=float(row["pct_f"]),
            main_net_inflow=float(row["net"]),
            main_inflow_rate=float(row["turnover"]),
            rank=i + 1,
        )
        for i, (_, row) in enumerate(df.iterrows())
    ]

    return MoneyFlowResponse(
        items=items,
        total=len(items),
        period=period,
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@router.get("/stock/{code}", response_model=StockMoneyFlow)
async def get_stock_money_flow(code: str):
    """获取单只股票资金流详情"""
    try:
        df = await _run_sync(_fetch_individual_flow, "即时")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"同花顺资金流接口异常: {e}")

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"未找到股票 {code} 的资金流数据")

    code_str = str(code).lstrip("shsz").zfill(6)
    df = df.copy()
    df["code_str"] = df["股票代码"].astype(str).str.zfill(6)
    matched = df[df["code_str"] == code_str]

    if matched.empty:
        raise HTTPException(status_code=404, detail=f"未找到股票 {code} 的资金流数据")

    row = matched.iloc[0]
    inflow = _parse_cn_number(row.get("流入资金"))
    outflow = _parse_cn_number(row.get("流出资金"))
    net = _parse_cn_number(row.get("净额"))
    turnover = _parse_pct(row.get("换手率"))

    return StockMoneyFlow(
        code=code_str,
        name=str(row.get("股票简称", "")),
        price=float(pd.to_numeric(row.get("最新价"), errors="coerce") or 0),
        change_pct=_parse_pct(row.get("涨跌幅")),
        main_net_inflow=net,
        main_inflow_rate=turnover,
        super_net_inflow=inflow,
        big_net_inflow=outflow,
    )


@router.get("/sector", response_model=SectorFlowResponse)
async def get_sector_money_flow(
    sector_type: str = Query("concept", description="industry | concept"),
    limit: int = Query(50, ge=1, le=200),
):
    """板块资金流排名（同花顺数据源）"""
    try:
        df = await _run_sync(_fetch_sector_flow, sector_type)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"同花顺板块资金流接口异常: {e}")

    if df is None or df.empty:
        return SectorFlowResponse(items=[], total=0, period="today",
                                  updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    df = df.copy()
    df["net"] = pd.to_numeric(df["净额"], errors="coerce").fillna(0.0) * 1e8
    df["pct_f"] = pd.to_numeric(df["行业-涨跌幅"], errors="coerce").fillna(0.0)
    df = df[df["net"] != 0].sort_values("net", ascending=False).head(limit)

    name_col = "行业"
    items = [
        SectorFlowItem(
            code=f"{sector_type[:2].upper()}{i+1:04d}",
            name=str(row[name_col]),
            change_pct=float(row["pct_f"]),
            main_net_inflow=float(row["net"]),
            main_inflow_rate=0.0,
        )
        for i, (_, row) in enumerate(df.iterrows())
    ]

    return SectorFlowResponse(
        items=items,
        total=len(items),
        period="today",
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@router.get("/overview", response_model=dict)
async def get_market_flow_overview():
    """市场整体资金流概览（基于同花顺即时数据汇总）"""
    try:
        df = await _run_sync(_fetch_individual_flow, "即时")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"同花顺资金流接口异常: {e}")

    if df is None or df.empty:
        return {
            "total_stocks": 0,
            "inflow_count": 0,
            "outflow_count": 0,
            "total_main_inflow": 0.0,
            "total_main_outflow": 0.0,
            "net_flow": 0.0,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    df = df.copy()
    df["net"] = df["净额"].apply(_parse_cn_number)
    inflow = df[df["net"] > 0]["net"].sum()
    outflow = df[df["net"] < 0]["net"].sum()

    return {
        "total_stocks": len(df),
        "inflow_count": int((df["net"] > 0).sum()),
        "outflow_count": int((df["net"] < 0).sum()),
        "total_main_inflow": float(inflow),
        "total_main_outflow": float(abs(outflow)),
        "net_flow": float(inflow + outflow),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

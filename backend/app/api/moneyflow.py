"""
AI Stock - 主力资金流 API

数据源：akshare 同花顺资金流接口（stock_fund_flow_individual / industry / concept）
原因：东财 push2 在当前网络下 TLS 层断连不可用。

核心数据获取逻辑已下沉到 app.services.moneyflow_service，供 API 和后台预热复用。
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.services import moneyflow_service

router = APIRouter(prefix="/moneyflow", tags=["资金流"])


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


@router.get("/rank", response_model=MoneyFlowResponse)
async def get_money_flow_rank(
    period: str = Query("today", description="today | 3d | 5d（同花顺接口仅提供即时/历史某日，3d/5d 当前回退到即时）"),
    limit: int = Query(100, ge=1, le=500),
    direction: str = Query("inflow", description="inflow | outflow 主力流入/流出"),
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD，为空则取今天"),
):
    """主力资金流排名（同花顺数据源）"""
    try:
        data = await moneyflow_service.get_money_flow_rank(
            period=period, direction=direction, limit=limit, date=date
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"同花顺资金流接口异常: {e}")
    return MoneyFlowResponse(**data)


@router.get("/stock/{code}", response_model=StockMoneyFlow)
async def get_stock_money_flow(code: str, date: Optional[str] = Query(None, description="日期 YYYY-MM-DD，为空则取今天")):
    """获取单只股票资金流详情"""
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        rank_data = await moneyflow_service.get_money_flow_rank(
            period="today", direction="inflow", limit=5000, date=trade_date
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"同花顺资金流接口异常: {e}")

    code_str = str(code).lstrip("shsz").zfill(6)
    matched = [item for item in rank_data["items"] if item["code"] == code_str]
    if not matched:
        raise HTTPException(status_code=404, detail=f"未找到股票 {code} 的资金流数据")

    row = matched[0]
    return StockMoneyFlow(
        code=code_str,
        name=row["name"],
        price=row["price"],
        change_pct=row["change_pct"],
        main_net_inflow=row["main_net_inflow"],
        main_inflow_rate=row["main_inflow_rate"],
    )


@router.get("/sector", response_model=SectorFlowResponse)
async def get_sector_money_flow(
    sector_type: str = Query("concept", description="industry | concept"),
    limit: int = Query(50, ge=1, le=200),
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD，为空则取今天"),
):
    """板块资金流排名（同花顺数据源）"""
    try:
        data = await moneyflow_service.get_sector_money_flow(
            sector_type=sector_type, limit=limit, date=date
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"同花顺板块资金流接口异常: {e}")
    return SectorFlowResponse(**data)


@router.get("/overview", response_model=dict)
async def get_market_flow_overview(
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD，为空则取今天"),
):
    """市场整体资金流概览（基于同花顺即时数据汇总）"""
    try:
        return await moneyflow_service.get_market_flow_overview(date=date)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"同花顺资金流接口异常: {e}")

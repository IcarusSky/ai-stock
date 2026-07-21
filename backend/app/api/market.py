"""
AI Stock - 行情API路由
"""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime

from app.schemas.market import StockQuote, KLine, WatchlistItem, PortfolioPosition, CapitalCurve, MarketSentiment
from app.services.market_data_service import market_data_service
from app.core.order_executor import order_executor

router = APIRouter(prefix="/market", tags=["行情"])


@router.get("/quote/{stock_code}", response_model=StockQuote)
async def get_quote(stock_code: str):
    """获取单只股票实时行情"""
    quote = await market_data_service.get_realtime_quote(stock_code)
    if not quote:
        raise HTTPException(status_code=404, detail="股票未找到")
    return quote


@router.get("/quotes", response_model=List[StockQuote])
async def get_quotes(stock_codes: str):
    """批量获取股票行情，stock_codes用逗号分隔"""
    codes = [c.strip() for c in stock_codes.split(",")]
    if len(codes) > 100:
        raise HTTPException(status_code=400, detail="单次最多查询100只股票")
    return await market_data_service.get_realtime_quotes(codes)


@router.get("/kline/{stock_code}", response_model=List[KLine])
async def get_kline(
    stock_code: str,
    period: str = "daily",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """获取K线数据"""
    return await market_data_service.get_kline_data(stock_code, period, start_date, end_date)


@router.get("/sentiment", response_model=MarketSentiment)
async def get_market_sentiment():
    """获取市场情绪"""
    return await market_data_service.get_market_sentiment()


@router.get("/watchlist", response_model=List[WatchlistItem])
async def get_watchlist():
    """获取自选股列表"""
    # 模拟数据
    return [
        WatchlistItem(code="000001", name="平安银行", tags=["AI推荐", "银行"]),
        WatchlistItem(code="600036", name="招商银行", tags=["价值", "银行"]),
        WatchlistItem(code="600519", name="贵州茅台", tags=["价值", "消费"]),
        WatchlistItem(code="300750", name="宁德时代", tags=["热点", "新能源"]),
        WatchlistItem(code="002594", name="比亚迪", tags=["热点", "汽车"]),
    ]


@router.post("/watchlist")
async def add_to_watchlist(item: WatchlistItem):
    """添加自选股"""
    return {"success": True, "message": f"已添加{item.name}到自选股"}


@router.delete("/watchlist/{stock_code}")
async def remove_from_watchlist(stock_code: str):
    """移除自选股"""
    return {"success": True, "message": f"已从自选股移除{stock_code}"}

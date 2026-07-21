"""
AI Stock - 行情相关 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


class StockQuote(BaseModel):
    """股票实时行情"""
    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    price: float = Field(..., description="当前价格")
    change: float = Field(..., description="涨跌额")
    change_pct: float = Field(..., description="涨跌幅(%)")
    open: float = Field(..., description="开盘价")
    high: float = Field(..., description="最高价")
    low: float = Field(..., description="最低价")
    volume: float = Field(..., description="成交量")
    amount: float = Field(..., description="成交额")
    amplitude: float = Field(..., description="振幅(%)")
    turnover: float = Field(..., description="换手率(%)")
    pe: Optional[float] = Field(None, description="市盈率")
    pb: Optional[float] = Field(None, description="市净率")
    market_cap: Optional[float] = Field(None, description="总市值")
    timestamp: datetime = Field(default_factory=datetime.now)


class KLine(BaseModel):
    """K线数据"""
    code: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    change_pct: float = 0.0


class WatchlistItem(BaseModel):
    """自选股"""
    code: str
    name: str
    added_at: datetime = Field(default_factory=datetime.now)
    tags: List[str] = Field(default_factory=list, description="标签，如：AI推荐, 热点, 价值")
    notes: Optional[str] = None


class PortfolioPosition(BaseModel):
    """持仓"""
    code: str
    name: str
    quantity: int = Field(..., description="持股数量")
    avg_cost: float = Field(..., description="平均成本")
    current_price: float = Field(..., description="当前价格")
    market_value: float = Field(..., description="市值")
    profit_loss: float = Field(..., description="盈亏金额")
    profit_rate: float = Field(..., description="盈亏比例")
    today_change_pct: float = Field(..., description="今日涨跌幅")
    update_time: datetime = Field(default_factory=datetime.now)


class CapitalCurve(BaseModel):
    """资金曲线"""
    date: str
    total_value: float
    cash: float
    positions_value: float
    daily_return: float = 0.0
    cumulative_return: float = 0.0


class MarketSentiment(BaseModel):
    """市场情绪"""
    advance_count: int = Field(..., description="上涨家数")
    decline_count: int = Field(..., description="下跌家数")
    limit_up_count: int = Field(..., description="涨停家数")
    limit_down_count: int = Field(..., description="跌停家数")
    total_volume: float = Field(..., description="总成交量")
    total_amount: float = Field(..., description="总成交额")
    main_net_inflow: float = Field(..., description="主力净流入")
    sentiment_score: float = Field(..., ge=0.0, le=100.0, description="情绪评分")

"""
AI Stock - 订单相关 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from enum import Enum


class OrderDirection(str, Enum):
    """下单方向"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """订单类型"""
    LIMIT = "LIMIT"        # 限价单
    MARKET = "MARKET"      # 市价单


class OrderStatus(str, Enum):
    """订单状态"""
    PENDING = "PENDING"       # 待成交
    PARTIAL = "PARTIAL"       # 部分成交
    FILLED = "FILLED"         # 全部成交
    CANCELLED = "CANCELLED"   # 已撤单
    REJECTED = "REJECTED"     # 已拒绝
    FAILED = "FAILED"         # 失败


class OrderCreate(BaseModel):
    """创建订单请求"""
    stock_code: str = Field(..., min_length=6, max_length=6)
    direction: OrderDirection
    order_type: OrderType = OrderType.LIMIT
    price: float = Field(..., gt=0)
    quantity: int = Field(..., gt=0, description="股数（A股为100的整数倍）")


class OrderResponse(BaseModel):
    """订单响应"""
    id: str
    order_id: str = Field(..., description="券商订单号")
    stock_code: str
    stock_name: str = ""
    direction: OrderDirection
    order_type: OrderType
    price: float
    quantity: int
    filled_quantity: int = 0
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    message: Optional[str] = None


class OrderCancel(BaseModel):
    """撤单请求"""
    order_id: str


class AccountInfo(BaseModel):
    """账户信息"""
    account_id: str
    account_name: str
    total_assets: float = Field(..., description="总资产")
    available_cash: float = Field(..., description="可用资金")
    market_value: float = Field(..., description="持仓市值")
    today_profit: float = Field(..., description="今日盈亏")
    today_profit_rate: float = Field(..., description="今日收益率")
    frozen: float = Field(0, description="冻结资金")


class TradeRecord(BaseModel):
    """成交记录"""
    trade_id: str
    order_id: str
    stock_code: str
    stock_name: str
    direction: OrderDirection
    price: float
    quantity: int
    amount: float
    commission: float = 0.0
    trade_time: datetime

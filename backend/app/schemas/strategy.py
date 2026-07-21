"""
AI Stock - 策略相关 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


class StrategyType(str, Enum):
    """策略类型"""
    TREND_FOLLOWING = "TREND_FOLLOWING"      # 趋势跟踪
    MEAN_REVERSION = "MEAN_REVERSION"        # 均值回归
    BREAKTHROUGH = "BREAKTHROUGH"           # 突破策略
    SECTOR_ROTATION = "SECTOR_ROTATION"      # 板块轮动
    VALUE_INVESTMENT = "VALUE_INVESTMENT"    # 价值投资


class RuleType(str, Enum):
    """规则类型"""
    ENTRY = "ENTRY"      # 入场规则
    EXIT = "EXIT"        # 出场规则
    FILTER = "FILTER"    # 过滤规则


class RuleCondition(BaseModel):
    """规则条件"""
    type: RuleType
    indicator: str = Field(..., description="指标名，如 MA5, RSI, MACD")
    operator: str = Field(..., description="操作符，如 >, <, crossover")
    value: float = Field(..., description="比较值")
    description: str = Field(..., description="条件描述")


class StrategyRule(BaseModel):
    """策略规则"""
    type: RuleType
    conditions: List[RuleCondition]
    logic: str = Field(default="AND", description="多条件逻辑 AND/OR")
    description: str = Field(..., description="规则描述")


class StrategyBase(BaseModel):
    """策略基础模型"""
    name: str = Field(..., min_length=1, max_length=100)
    type: StrategyType
    description: Optional[str] = ""
    params: dict = Field(default_factory=dict, description="策略参数")


class StrategyCreate(StrategyBase):
    """创建策略请求"""
    rules: List[StrategyRule] = Field(default_factory=list)


class StrategyUpdate(BaseModel):
    """更新策略请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    params: Optional[dict] = None
    rules: Optional[List[StrategyRule]] = None
    status: Optional[str] = None


class Strategy(StrategyBase):
    """策略完整模型"""
    id: str
    rules: List[StrategyRule] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    status: str = "ACTIVE"

    class Config:
        from_attributes = True


class StrategySignal(BaseModel):
    """策略信号"""
    strategy_id: str
    strategy_name: str
    stock_code: str
    signal: Literal["BUY", "SELL", "HOLD"] = Field(..., description="交易信号")
    confidence: float = Field(..., ge=0.0, le=1.0, description="信号置信度")
    price: float = Field(..., description="当前价格")
    target_price: Optional[float] = Field(None, description="目标价格")
    stop_loss: Optional[float] = Field(None, description="止损价格")
    position_ratio: Optional[float] = Field(None, description="建议仓位比例")
    reason: str = Field(..., description="信号原因")
    created_at: datetime


class MarketEnv(BaseModel):
    """市场环境"""
    trend: Literal["BULL", "BEAR", "NEUTRAL"] = Field(..., description="趋势方向")
    volatility: Literal["HIGH", "MEDIUM", "LOW"] = Field(..., description="波动率")
    volume: Literal["HIGH", "MEDIUM", "LOW"] = Field(..., description="成交量")
    sector_rotation: Literal["FAST", "MEDIUM", "SLOW"] = Field(..., description="板块轮动速度")
    overall: Literal["OPTIMISTIC", "NEUTRAL", "PESSIMISTIC"] = Field(..., description="整体判断")
    score: float = Field(..., ge=0.0, le=100.0, description="环境评分")
    description: str = Field(..., description="环境描述")


class DailyRecommendation(BaseModel):
    """每日策略推荐"""
    date: str
    market_env: MarketEnv
    recommended_strategies: List[dict] = Field(..., description="推荐的策略列表及权重")
    trading_plan: dict = Field(..., description="当日交易计划")
    risk_alert: Optional[str] = Field(None, description="风险提示")

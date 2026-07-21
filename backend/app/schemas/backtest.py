"""
AI Stock - 回测相关 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class BacktestCreate(BaseModel):
    """创建回测请求"""
    strategy_id: str
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    initial_capital: float = Field(100000, description="初始资金")
    commission: float = Field(0.00025, description="佣金率")
    stamp_tax: float = Field(0.001, description="印花税率")
    slippage: float = Field(0.001, description="滑点率")


class BacktestTask(BaseModel):
    """回测任务"""
    task_id: str
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED
    progress: float = 0.0
    created_at: datetime


class BacktestMetrics(BaseModel):
    """回测指标"""
    total_return: float = Field(..., description="总收益率")
    annualized_return: float = Field(..., description="年化收益率")
    sharpe_ratio: float = Field(..., description="夏普比率")
    max_drawdown: float = Field(..., description="最大回撤")
    max_drawdown_duration: int = Field(0, description="最大回撤持续天数")
    win_rate: float = Field(..., description="胜率")
    profit_loss_ratio: float = Field(..., description="盈亏比")
    total_trades: int = Field(0, description="总交易次数")
    avg_holding_days: float = Field(0, description="平均持仓天数")


class EquityPoint(BaseModel):
    """权益点"""
    date: str
    value: float
    drawdown: float = 0.0


class BacktestTrade(BaseModel):
    """回测交易"""
    stock_code: str
    stock_name: str
    direction: str  # BUY, SELL
    entry_date: str
    entry_price: float
    exit_date: Optional[str]
    exit_price: Optional[float]
    quantity: int
    profit: float = 0.0
    profit_rate: float = 0.0
    holding_days: int = 0


class MonthlyReturn(BaseModel):
    """月度收益"""
    month: str = Field(..., description="月份 YYYY-MM")
    return_pct: float = Field(..., description="月度收益率")


class BacktestResult(BaseModel):
    """回测结果"""
    task_id: str
    strategy_id: str
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    metrics: BacktestMetrics
    equity_curve: List[EquityPoint]
    trades: List[BacktestTrade]
    monthly_returns: List[MonthlyReturn] = Field(default_factory=list, description="月度收益列表")
    completed_at: datetime


class BacktestCompare(BaseModel):
    """策略对比"""
    results: List[BacktestResult]
    best_by_return: Optional[str] = None
    best_by_sharpe: Optional[str] = None
    best_by_drawdown: Optional[str] = None


class OptimizationResult(BaseModel):
    """参数优化结果"""
    param_name: str
    param_values: List[float]
    results: List[BacktestMetrics]
    best_value: float
    best_metrics: BacktestMetrics

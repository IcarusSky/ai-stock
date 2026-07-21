"""
AI Stock - 回测服务
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import asyncio
from loguru import logger

from app.schemas.backtest import (
    BacktestCreate, BacktestResult, BacktestMetrics,
    EquityPoint, BacktestTrade, MonthlyReturn
)
from app.schemas.market import KLine
from app.services.strategy_engine import strategy_engine
from app.services.market_data_service import market_data_service


@dataclass
class BacktestPosition:
    """回测持仓"""
    stock_code: str
    quantity: int
    avg_cost: float
    entry_date: str


@dataclass
class BacktestState:
    """回测状态"""
    cash: float
    initial_capital: float
    positions: Dict[str, BacktestPosition] = field(default_factory=dict)
    equity_curve: List[EquityPoint] = field(default_factory=list)
    trades: List[BacktestTrade] = field(default_factory=list)
    peak_value: float = 0.0
    max_drawdown: float = 0.0


class BacktestService:
    """回测服务"""

    def __init__(self):
        self.tasks: Dict[str, dict] = {}

    async def run_backtest(
        self,
        task_id: str,
        config: BacktestCreate,
        klines_data: Dict[str, List[KLine]]
    ) -> BacktestResult:
        """运行回测（基于策略引擎真实生成信号并模拟交易）"""
        try:
            logger.info(f"开始回测任务 {task_id}")

            strategy = strategy_engine.strategies.get(config.strategy_id)
            if not strategy:
                raise ValueError(f"策略 {config.strategy_id} 未找到")

            state = BacktestState(
                cash=config.initial_capital,
                initial_capital=config.initial_capital
            )

            # 跟踪未平仓头寸
            open_positions: Dict[str, BacktestPosition] = {}

            # 合并所有股票的K线数据
            all_dates = set()
            for klines in klines_data.values():
                for k in klines:
                    all_dates.add(k.date)
            all_dates = sorted(list(all_dates))

            if not all_dates:
                raise ValueError("没有K线数据")

            # 更新任务状态
            self.tasks[task_id] = {"status": "RUNNING", "progress": 0.0}

            total_days = len(all_dates)
            processed_days = 0

            # 按日期遍历
            for date in all_dates:
                date_str = date if isinstance(date, str) else date.strftime('%Y-%m-%d')

                # 获取当日的行情数据
                day_data = {}
                for stock_code, klines in klines_data.items():
                    for k in klines:
                        k_date = k.date if isinstance(k.date, str) else k.date.strftime('%Y-%m-%d')
                        if k_date == date_str:
                            day_data[stock_code] = k
                            break

                # 基于截至当日的历史数据生成信号并执行
                for stock_code, klines in klines_data.items():
                    if stock_code not in day_data:
                        continue

                    history = [
                        k for k in klines
                        if (k.date if isinstance(k.date, str) else k.date.strftime('%Y-%m-%d')) <= date_str
                    ]
                    if len(history) < 60:
                        continue

                    signals = await strategy_engine.generate_signals(
                        stock_code, history, [config.strategy_id]
                    )
                    if not signals:
                        continue

                    signal = signals[0]
                    current_price = day_data[stock_code].close
                    stock_name = market_data_service._get_stock_name(stock_code)

                    if signal.signal == "BUY" and stock_code not in open_positions:
                        # 使用固定仓位：每只股票最多投入初始资金的20%
                        position_value = state.initial_capital * 0.2
                        quantity = int(position_value / current_price / 100) * 100
                        if quantity >= 100:
                            cost = current_price * quantity * (1 + config.commission + config.slippage)
                            if cost <= state.cash:
                                state.cash -= cost
                                open_positions[stock_code] = BacktestPosition(
                                    stock_code=stock_code,
                                    quantity=quantity,
                                    avg_cost=current_price,
                                    entry_date=date_str
                                )
                                logger.debug(f"{date_str} 买入 {stock_code} {quantity}股 @{current_price}")

                    elif signal.signal == "SELL" and stock_code in open_positions:
                        pos = open_positions[stock_code]
                        sell_amount = current_price * pos.quantity
                        commission = sell_amount * config.commission
                        tax = sell_amount * config.stamp_tax
                        slippage_cost = sell_amount * config.slippage
                        state.cash += sell_amount - commission - tax - slippage_cost

                        profit = (current_price - pos.avg_cost) * pos.quantity - commission - tax - slippage_cost
                        profit_rate = profit / (pos.avg_cost * pos.quantity) if pos.avg_cost > 0 else 0
                        holding_days = self._days_between(pos.entry_date, date_str)

                        state.trades.append(BacktestTrade(
                            stock_code=stock_code,
                            stock_name=stock_name,
                            direction="SELL",
                            entry_date=pos.entry_date,
                            entry_price=pos.avg_cost,
                            exit_date=date_str,
                            exit_price=current_price,
                            quantity=pos.quantity,
                            profit=profit,
                            profit_rate=profit_rate,
                            holding_days=holding_days
                        ))
                        logger.debug(f"{date_str} 卖出 {stock_code} {pos.quantity}股 @{current_price} 盈亏:{profit:.2f}")
                        del open_positions[stock_code]

                # 更新权益曲线
                positions_value = sum(
                    p.quantity * day_data.get(p.stock_code, KLine(
                        code=p.stock_code, date=date_str,
                        open=0, high=0, low=0, close=p.avg_cost, volume=0, amount=0
                    )).close
                    for p in open_positions.values()
                    if p.stock_code in day_data
                )
                total_value = state.cash + positions_value

                # 更新最大回撤
                if total_value > state.peak_value:
                    state.peak_value = total_value
                drawdown = (state.peak_value - total_value) / state.peak_value if state.peak_value > 0 else 0
                state.max_drawdown = max(state.max_drawdown, drawdown)

                state.equity_curve.append(EquityPoint(
                    date=date_str,
                    value=total_value,
                    drawdown=drawdown
                ))

                processed_days += 1
                if processed_days % 10 == 0 or processed_days == total_days:
                    progress = processed_days / total_days
                    self.tasks[task_id]["progress"] = progress

            # 期末强制平仓，计入交易
            if state.equity_curve:
                last_date = state.equity_curve[-1].date
                for stock_code, pos in list(open_positions.items()):
                    last_price = pos.avg_cost
                    for klines in klines_data.values():
                        for k in klines:
                            k_date = k.date if isinstance(k.date, str) else k.date.strftime('%Y-%m-%d')
                            if k_date == last_date:
                                last_price = k.close
                                break
                    sell_amount = last_price * pos.quantity
                    commission = sell_amount * config.commission
                    tax = sell_amount * config.stamp_tax
                    slippage_cost = sell_amount * config.slippage
                    state.cash += sell_amount - commission - tax - slippage_cost

                    profit = (last_price - pos.avg_cost) * pos.quantity - commission - tax - slippage_cost
                    profit_rate = profit / (pos.avg_cost * pos.quantity) if pos.avg_cost > 0 else 0
                    holding_days = self._days_between(pos.entry_date, last_date)
                    stock_name = market_data_service._get_stock_name(stock_code)

                    state.trades.append(BacktestTrade(
                        stock_code=stock_code,
                        stock_name=stock_name,
                        direction="SELL",
                        entry_date=pos.entry_date,
                        entry_price=pos.avg_cost,
                        exit_date=last_date,
                        exit_price=last_price,
                        quantity=pos.quantity,
                        profit=profit,
                        profit_rate=profit_rate,
                        holding_days=holding_days
                    ))
                    state.equity_curve[-1].value = state.cash
                    del open_positions[stock_code]

            # 计算回测指标
            final_capital = state.equity_curve[-1].value if state.equity_curve else config.initial_capital

            metrics = self._calculate_metrics(state, config, final_capital)
            monthly_returns = self._calculate_monthly_returns(state)

            result = BacktestResult(
                task_id=task_id,
                strategy_id=config.strategy_id,
                strategy_name=strategy.name,
                start_date=config.start_date,
                end_date=config.end_date,
                initial_capital=config.initial_capital,
                final_capital=final_capital,
                metrics=metrics,
                equity_curve=state.equity_curve,
                trades=state.trades,
                monthly_returns=monthly_returns,
                completed_at=datetime.now()
            )

            self.tasks[task_id]["status"] = "COMPLETED"
            self.tasks[task_id]["progress"] = 1.0
            self.tasks[task_id]["result"] = result

            logger.info(f"回测任务 {task_id} 完成，最终资金: {final_capital:.2f}")
            return result
        except Exception as e:
            self.tasks[task_id] = {"status": "FAILED", "error": str(e)}
            logger.error(f"回测任务 {task_id} 失败: {e}")

    def _days_between(self, start_date: str, end_date: str) -> int:
        """计算两个日期之间的天数"""
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            return max(0, (end - start).days)
        except Exception:
            return 0

    def _calculate_monthly_returns(self, state: BacktestState) -> List[MonthlyReturn]:
        """根据权益曲线计算月度收益"""
        if not state.equity_curve:
            return []

        monthly_values: Dict[str, List[float]] = {}
        for point in state.equity_curve:
            month = point.date[:7]  # YYYY-MM
            monthly_values.setdefault(month, []).append(point.value)

        months = sorted(monthly_values.keys())
        monthly_returns = []
        for i, month in enumerate(months):
            end_value = monthly_values[month][-1]
            if i == 0:
                start_value = monthly_values[month][0]
            else:
                prev_month = months[i - 1]
                start_value = monthly_values[prev_month][-1]

            if start_value > 0:
                return_pct = (end_value - start_value) / start_value
            else:
                return_pct = 0.0

            monthly_returns.append(MonthlyReturn(month=month, return_pct=return_pct))

        return monthly_returns

    def _calculate_metrics(
        self,
        state: BacktestState,
        config: BacktestCreate,
        final_capital: float
    ) -> BacktestMetrics:
        """计算回测指标"""
        total_return = (final_capital - config.initial_capital) / config.initial_capital

        # 年化收益率
        start_date = datetime.strptime(config.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(config.end_date, '%Y-%m-%d')
        years = (end_date - start_date).days / 365.0
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        # 计算波动率和夏普比率
        returns = []
        for i in range(1, len(state.equity_curve)):
            prev_value = state.equity_curve[i-1].value
            curr_value = state.equity_curve[i].value
            if prev_value > 0:
                returns.append((curr_value - prev_value) / prev_value)

        returns = np.array(returns)
        volatility = np.std(returns) if len(returns) > 0 else 0
        sharpe_ratio = (annualized_return - 0.03) / volatility if volatility > 0 else 0  # 假设无风险利率3%

        # 胜率
        winning_trades = [t for t in state.trades if t.profit > 0]
        win_rate = len(winning_trades) / len(state.trades) if state.trades else 0

        # 盈亏比
        avg_profit = np.mean([t.profit for t in state.trades if t.profit > 0]) if winning_trades else 0
        avg_loss = abs(np.mean([t.profit for t in state.trades if t.profit < 0])) if state.trades else 0
        profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0

        # 平均持仓天数
        holding_days = [t.holding_days for t in state.trades]
        avg_holding_days = np.mean(holding_days) if holding_days else 0

        return BacktestMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=state.max_drawdown,
            win_rate=win_rate,
            profit_loss_ratio=profit_loss_ratio,
            total_trades=len(state.trades),
            avg_holding_days=avg_holding_days
        )

    def simulate_trade(
        self,
        state: BacktestState,
        stock_code: str,
        direction: str,
        price: float,
        quantity: int,
        commission_rate: float,
        stamp_tax_rate: float,
        slippage_rate: float
    ) -> Tuple[float, float]:
        """模拟交易"""
        # 考虑滑点
        actual_price = price * (1 + slippage_rate) if direction == "BUY" else price * (1 - slippage_rate)
        amount = actual_price * quantity

        commission = amount * commission_rate
        tax = amount * stamp_tax_rate if direction == "SELL" else 0
        total_cost = amount + commission + tax

        if direction == "BUY" and total_cost > state.cash:
            # 资金不足，按最大可买量
            max_quantity = int(state.cash / (actual_price * (1 + commission_rate)) / 100) * 100
            if max_quantity < 100:
                return 0, 0
            actual_price = price * (1 + slippage_rate)
            amount = actual_price * max_quantity
            commission = amount * commission_rate
            total_cost = amount + commission
            quantity = max_quantity

        if direction == "BUY":
            state.cash -= total_cost
            if stock_code in state.positions:
                old_pos = state.positions[stock_code]
                new_quantity = old_pos.quantity + quantity
                new_avg_cost = (old_pos.avg_cost * old_pos.quantity + actual_price * quantity) / new_quantity
                state.positions[stock_code] = BacktestPosition(
                    stock_code=stock_code,
                    quantity=new_quantity,
                    avg_cost=new_avg_cost
                )
            else:
                state.positions[stock_code] = BacktestPosition(
                    stock_code=stock_code,
                    quantity=quantity,
                    avg_cost=actual_price
                )
        else:  # SELL
            if stock_code not in state.positions:
                return 0, 0
            pos = state.positions[stock_code]
            if pos.quantity < quantity:
                quantity = pos.quantity

            state.cash += amount - commission - tax
            profit = (actual_price - pos.avg_cost) * quantity
            state.positions[stock_code].quantity -= quantity

            if state.positions[stock_code].quantity <= 0:
                del state.positions[stock_code]

            return profit, quantity

        return 0, quantity

    def get_task_status(self, task_id: str) -> Optional[dict]:
        """获取任务状态"""
        return self.tasks.get(task_id)


# 全局回测服务实例
backtest_service = BacktestService()

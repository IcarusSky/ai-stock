"""
AI Stock - 订单执行服务
"""
import uuid
from typing import Optional, List
from datetime import datetime
from enum import Enum
import asyncio
from loguru import logger

from app.schemas.order import (
    OrderCreate, OrderResponse, OrderStatus, OrderDirection, OrderType,
    AccountInfo, TradeRecord
)


class OrderExecutor:
    """订单执行服务（模拟）"""

    def __init__(self):
        self._orders: dict = {}
        self._account: Optional[AccountInfo] = None
        self._positions: dict = {}
        self._trades: List[TradeRecord] = []

    async def initialize(self, initial_capital: float = 100000.0):
        """初始化账户"""
        self._account = AccountInfo(
            account_id=str(uuid.uuid4())[:8],
            account_name="模拟账户",
            total_assets=initial_capital,
            available_cash=initial_capital,
            market_value=0.0,
            today_profit=0.0,
            today_profit_rate=0.0,
            frozen=0.0
        )
        self._positions = {}
        self._trades = []
        logger.info(f"初始化账户，初始资金: {initial_capital}")

    async def buy(self, order: OrderCreate) -> OrderResponse:
        """买入下单"""
        order_id = str(uuid.uuid4())[:12]

        # 模拟订单验证
        if order.quantity % 100 != 0:
            return OrderResponse(
                id=order_id,
                order_id=f"B{order_id}",
                stock_code=order.stock_code,
                direction=order.direction,
                order_type=order.order_type,
                price=order.price,
                quantity=order.quantity,
                status=OrderStatus.REJECTED,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                message="A股买入数量必须是100的整数倍"
            )

        required_amount = order.price * order.quantity * 1.00025  # 手续费
        if self._account and self._account.available_cash < required_amount:
            return OrderResponse(
                id=order_id,
                order_id=f"B{order_id}",
                stock_code=order.stock_code,
                direction=order.direction,
                order_type=order.order_type,
                price=order.price,
                quantity=order.quantity,
                status=OrderStatus.REJECTED,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                message=f"资金不足，需要{required_amount:.2f}，可用{self._account.available_cash:.2f}"
            )

        # 模拟成交
        response = OrderResponse(
            id=order_id,
            order_id=f"B{order_id}",
            stock_code=order.stock_code,
            stock_name=self._get_stock_name(order.stock_code),
            direction=order.direction,
            order_type=order.order_type,
            price=order.price,
            quantity=order.quantity,
            filled_quantity=order.quantity,
            status=OrderStatus.FILLED,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            message="成交成功"
        )

        self._orders[order_id] = response

        # 更新持仓
        if order.stock_code in self._positions:
            pos = self._positions[order.stock_code]
            new_quantity = pos['quantity'] + order.quantity
            new_avg_cost = (pos['avg_cost'] * pos['quantity'] + order.price * order.quantity) / new_quantity
            self._positions[order.stock_code] = {
                'quantity': new_quantity,
                'avg_cost': new_avg_cost
            }
        else:
            self._positions[order.stock_code] = {
                'quantity': order.quantity,
                'avg_cost': order.price,
                'name': response.stock_name
            }

        # 更新账户
        if self._account:
            self._account.available_cash -= required_amount
            self._account.market_value += order.price * order.quantity

        # 记录成交
        trade = TradeRecord(
            trade_id=str(uuid.uuid4())[:12],
            order_id=response.order_id,
            stock_code=order.stock_code,
            stock_name=response.stock_name,
            direction=OrderDirection.BUY,
            price=order.price,
            quantity=order.quantity,
            amount=order.price * order.quantity,
            commission=order.price * order.quantity * 0.00025,
            trade_time=datetime.now()
        )
        self._trades.append(trade)

        logger.info(f"买入成交: {order.stock_code} {order.quantity}股 @{order.price}")
        return response

    async def sell(self, order: OrderCreate) -> OrderResponse:
        """卖出下单"""
        order_id = str(uuid.uuid4())[:12]

        # 检查持仓
        if order.stock_code not in self._positions:
            return OrderResponse(
                id=order_id,
                order_id=f"S{order_id}",
                stock_code=order.stock_code,
                direction=order.direction,
                order_type=order.order_type,
                price=order.price,
                quantity=order.quantity,
                status=OrderStatus.REJECTED,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                message="没有该股票持仓"
            )

        pos = self._positions[order.stock_code]
        if pos['quantity'] < order.quantity:
            return OrderResponse(
                id=order_id,
                order_id=f"S{order_id}",
                stock_code=order.stock_code,
                direction=order.direction,
                order_type=order.order_type,
                price=order.price,
                quantity=order.quantity,
                status=OrderStatus.REJECTED,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                message=f"持仓不足，当前持仓{pos['quantity']}股"
            )

        # 模拟成交
        response = OrderResponse(
            id=order_id,
            order_id=f"S{order_id}",
            stock_code=order.stock_code,
            stock_name=pos['name'],
            direction=order.direction,
            order_type=order.order_type,
            price=order.price,
            quantity=order.quantity,
            filled_quantity=order.quantity,
            status=OrderStatus.FILLED,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            message="成交成功"
        )

        self._orders[order_id] = response

        # 更新持仓
        pos['quantity'] -= order.quantity
        if pos['quantity'] <= 0:
            del self._positions[order.stock_code]

        # 更新账户
        amount = order.price * order.quantity
        commission = amount * 0.00025
        stamp_tax = amount * 0.001  # 印花税
        net_amount = amount - commission - stamp_tax

        if self._account:
            self._account.available_cash += net_amount
            self._account.market_value -= order.price * order.quantity

        # 记录成交
        trade = TradeRecord(
            trade_id=str(uuid.uuid4())[:12],
            order_id=response.order_id,
            stock_code=order.stock_code,
            stock_name=response.stock_name,
            direction=OrderDirection.SELL,
            price=order.price,
            quantity=order.quantity,
            amount=amount,
            commission=commission + stamp_tax,
            trade_time=datetime.now()
        )
        self._trades.append(trade)

        logger.info(f"卖出成交: {order.stock_code} {order.quantity}股 @{order.price}")
        return response

    async def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        if order_id in self._orders:
            order = self._orders[order_id]
            if order.status == OrderStatus.PENDING:
                order.status = OrderStatus.CANCELLED
                order.updated_at = datetime.now()
                return True
        return False

    async def get_account_info(self) -> Optional[AccountInfo]:
        """获取账户信息"""
        return self._account

    async def get_positions(self) -> dict:
        """获取持仓"""
        return self._positions

    async def get_today_trades(self) -> List[TradeRecord]:
        """获取当日成交"""
        today = datetime.now().date()
        return [t for t in self._trades if t.trade_time.date() == today]

    async def get_order(self, order_id: str) -> Optional[OrderResponse]:
        """获取订单"""
        return self._orders.get(order_id)

    def _get_stock_name(self, code: str) -> str:
        """获取股票名称"""
        names = {
            '000001': '平安银行',
            '000002': '万科A',
            '600000': '浦发银行',
            '600036': '招商银行',
            '600519': '贵州茅台',
            '000858': '五粮液',
            '002594': '比亚迪',
            '300750': '宁德时代',
        }
        return names.get(code, f'股票{code}')


# 全局订单执行器实例
order_executor = OrderExecutor()

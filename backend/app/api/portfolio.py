"""
AI Stock - 持仓/账户API路由
"""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime, timedelta

from app.schemas.market import PortfolioPosition, CapitalCurve
from app.schemas.order import AccountInfo, TradeRecord
from app.core.order_executor import order_executor

router = APIRouter(prefix="/portfolio", tags=["持仓"])


@router.get("/positions", response_model=List[PortfolioPosition])
async def get_positions():
    """获取当前持仓"""
    positions_data = await order_executor.get_positions()

    positions = []
    for code, pos in positions_data.items():
        # 获取当前价格
        quote = {
            '平安银行': 12.50,
            '万科A': 8.20,
            '浦发银行': 7.80,
            '招商银行': 35.60,
            '贵州茅台': 1680.00,
            '五粮液': 145.00,
            '比亚迪': 260.00,
            '宁德时代': 180.00,
        }
        current_price = quote.get(pos['name'], pos['avg_cost'])
        market_value = current_price * pos['quantity']
        profit_loss = (current_price - pos['avg_cost']) * pos['quantity']
        profit_rate = profit_loss / (pos['avg_cost'] * pos['quantity'])

        positions.append(PortfolioPosition(
            code=code,
            name=pos['name'],
            quantity=pos['quantity'],
            avg_cost=pos['avg_cost'],
            current_price=current_price,
            market_value=market_value,
            profit_loss=profit_loss,
            profit_rate=profit_rate,
            today_change_pct=0.0,
            update_time=datetime.now()
        ))

    return positions


@router.get("/capital_curve", response_model=List[CapitalCurve])
async def get_capital_curve(days: int = 30):
    """获取资金曲线"""
    import random
    curve = []
    total_value = 100000.0
    today = datetime.now()

    for i in range(days, 0, -1):
        date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        daily_return = random.uniform(-0.02, 0.03)
        total_value = total_value * (1 + daily_return)
        cash = total_value * 0.3
        positions_value = total_value - cash

        curve.append(CapitalCurve(
            date=date,
            total_value=round(total_value, 2),
            cash=round(cash, 2),
            positions_value=round(positions_value, 2),
            daily_return=daily_return,
            cumulative_return=(total_value - 100000) / 100000
        ))

    return curve


@router.get("/account", response_model=AccountInfo)
async def get_account_info():
    """获取账户信息"""
    account = await order_executor.get_account_info()
    if not account:
        raise HTTPException(status_code=404, detail="账户未初始化")
    return account


@router.get("/trades", response_model=List[TradeRecord])
async def get_today_trades():
    """获取当日成交记录"""
    return await order_executor.get_today_trades()

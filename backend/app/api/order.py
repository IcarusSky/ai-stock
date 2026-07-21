"""
AI Stock - 订单API路由
"""
from fastapi import APIRouter, HTTPException
from typing import List

from app.schemas.order import OrderCreate, OrderResponse, OrderCancel
from app.core.order_executor import order_executor
from app.services.feishu_service import feishu_service

router = APIRouter(prefix="/order", tags=["订单"])


@router.post("/buy", response_model=OrderResponse)
async def buy_stock(order: OrderCreate):
    """买入下单"""
    response = await order_executor.buy(order)

    # 发送飞书通知
    if response.status.value == "FILLED":
        await feishu_service.send_position_change(
            stock_code=response.stock_code,
            stock_name=response.stock_name,
            direction="BUY",
            quantity=response.quantity,
            price=response.price
        )

    return response


@router.post("/sell", response_model=OrderResponse)
async def sell_stock(order: OrderCreate):
    """卖出下单"""
    response = await order_executor.sell(order)

    # 发送飞书通知
    if response.status.value == "FILLED":
        await feishu_service.send_position_change(
            stock_code=response.stock_code,
            stock_name=response.stock_name,
            direction="SELL",
            quantity=response.quantity,
            price=response.price
        )

    return response


@router.post("/cancel")
async def cancel_order(cancel: OrderCancel):
    """撤单"""
    success = await order_executor.cancel_order(cancel.order_id)
    if not success:
        raise HTTPException(status_code=400, detail="撤单失败")
    return {"success": True, "message": "撤单成功"}


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str):
    """查询订单"""
    order = await order_executor.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单未找到")
    return order


@router.get("/")
async def list_orders():
    """查询所有订单"""
    # 实际项目应该返回数据库中的订单列表
    return []

"""
AI Stock - 飞书API路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.feishu_service import feishu_service

router = APIRouter(prefix="/feishu", tags=["飞书"])


class MessageRequest(BaseModel):
    content: str
    msg_type: str = "text"


class WebhookConfig(BaseModel):
    webhook_url: str


class CardRequest(BaseModel):
    title: str
    content: str
    color: str = "blue"


@router.post("/send_message")
async def send_message(request: MessageRequest):
    """发送文本消息"""
    success = await feishu_service.send_message(request.content, request.msg_type)
    if not success:
        raise HTTPException(status_code=500, detail="消息发送失败")
    return {"success": True}


@router.post("/send_card")
async def send_card(request: CardRequest):
    """发送卡片消息"""
    card = feishu_service.build_card_template(request.title, request.content, request.color)
    success = await feishu_service.send_card(card)
    if not success:
        raise HTTPException(status_code=500, detail="卡片发送失败")
    return {"success": True}


@router.post("/set_webhook")
async def set_webhook(request: WebhookConfig):
    """配置Webhook"""
    feishu_service.webhook_url = request.webhook_url
    return {"success": True}


@router.get("/push_logs")
async def get_push_logs():
    """获取推送日志"""
    # 模拟日志数据
    return {
        "logs": [
            {"time": "2024-01-01 10:00:00", "type": "trade_signal", "status": "success"},
            {"time": "2024-01-01 10:30:00", "type": "position_change", "status": "success"},
            {"time": "2024-01-01 14:00:00", "type": "risk_alert", "status": "success"},
        ]
    }


@router.post("/test")
async def test_feishu():
    """测试飞书连接"""
    success = await feishu_service.send_message("🤖 AI量化交易系统连接测试\n时间: 2024-01-01")
    return {"success": success}

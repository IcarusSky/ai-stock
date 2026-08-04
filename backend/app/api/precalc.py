"""
AI Stock - 数据预热管理 API

提供预热服务状态查看与手动触发。
"""
from fastapi import APIRouter

from app.services.precalc_service import precalc_service

router = APIRouter(prefix="/precalc", tags=["数据预热"])


@router.post("/trigger")
async def trigger_precalc():
    """手动触发一次市场数据预热"""
    return await precalc_service.trigger()


@router.get("/status")
async def get_precalc_status():
    """查看预热服务状态"""
    return precalc_service.status()

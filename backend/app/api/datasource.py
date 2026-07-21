"""
AI Stock - 数据源状态与问财选股 API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.datasource.ifind_client import DataSourceError
from app.services.datasource.router import data_source_router
from app.services.datasource.tianyancha_client import tianyancha_client

router = APIRouter(prefix="/datasource", tags=["数据源"])


@router.get("/status")
async def get_datasource_status():
    """获取数据源状态（行情通道、各 token 配置情况、天眼查当日用量）"""
    status = data_source_router.status()
    status["tianyancha"] = {
        "configured": tianyancha_client.configured,
        "today_calls": tianyancha_client.today_calls,
        "daily_limit": tianyancha_client.daily_limit,
    }
    return status


class WencaiRequest(BaseModel):
    """问财选股请求"""
    query: str = Field(..., description="自然语言选股条件，如：市盈率小于20的银行股")


@router.post("/wencai")
async def wencai_stock_picking(req: WencaiRequest):
    """问财自然语言选股（iFinD 智能选股 / pywencai）"""
    try:
        return await data_source_router.wencai(req.query)
    except DataSourceError as e:
        raise HTTPException(status_code=503, detail=str(e))

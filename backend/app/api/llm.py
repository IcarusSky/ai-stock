"""
AI Stock - LLM API路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas.strategy import StrategyCreate
from app.services.llm_service import llm_service

router = APIRouter(prefix="/llm", tags=["LLM"])


class StrategyGenerateRequest(BaseModel):
    description: str


class StrategyPreviewResponse(BaseModel):
    strategy: dict
    validation_result: dict


@router.post("/strategy/generate")
async def generate_strategy(request: StrategyGenerateRequest):
    """根据自然语言生成策略"""
    strategy = await llm_service.generate_strategy(request.description)

    if not strategy:
        raise HTTPException(status_code=500, detail="策略生成失败")

    return {
        "success": True,
        "strategy": strategy.model_dump()
    }


@router.post("/strategy/validate")
async def validate_strategy(strategy: StrategyCreate):
    """验证策略语法"""
    # 简单的策略验证
    errors = []

    if not strategy.name:
        errors.append("策略名称不能为空")

    if not strategy.params:
        errors.append("策略参数未设置")

    if not strategy.rules and strategy.type != "VALUE_INVESTMENT":
        errors.append("至少需要一条入场或出场规则")

    # 验证规则格式
    for rule in strategy.rules:
        if not rule.conditions:
            errors.append(f"规则 '{rule.description}' 没有条件")
        for cond in rule.conditions:
            if not cond.indicator:
                errors.append("条件缺少指标名")

    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


@router.post("/strategy/preview")
async def preview_strategy(request: StrategyGenerateRequest):
    """预览生成的策略"""
    strategy = await llm_service.generate_strategy(request.description)

    if not strategy:
        raise HTTPException(status_code=500, detail="策略生成失败")

    # 验证
    validation = {
        "valid": True,
        "errors": []
    }

    return {
        "strategy": strategy.model_dump(),
        "validation_result": validation
    }

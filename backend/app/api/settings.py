"""
AI Stock - 系统设置 API

管理券商配置、风控参数、飞书通知开关等系统级配置。
配置持久化到 .env 文件（开发环境）或环境变量（生产环境）。
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from app.core.config import settings

router = APIRouter(prefix="/settings", tags=["系统设置"])


# ========== 请求/响应模型 ==========

class BrokerConfig(BaseModel):
    """券商配置"""
    broker_type: str = Field("pingan", description="券商类型")
    app_id: Optional[str] = Field(None, description="券商 App ID")
    app_secret: Optional[str] = Field(None, description="券商 App Secret")


class RiskConfig(BaseModel):
    """风控配置"""
    max_position_ratio: float = Field(0.2, ge=0.0, le=1.0, description="单只股票最大仓位比例")
    max_total_positions: int = Field(5, ge=1, description="最大持仓数量")
    stop_loss_ratio: float = Field(0.05, ge=0.0, le=1.0, description="止损比例")
    daily_loss_limit: float = Field(0.015, ge=0.0, le=1.0, description="每日最大亏损")
    weekly_loss_limit: float = Field(0.05, ge=0.0, le=1.0, description="每周最大亏损")
    min_trade_amount: float = Field(2000.0, ge=0.0, description="最小交易金额")


class FeishuConfig(BaseModel):
    """飞书通知配置"""
    webhook_url: Optional[str] = Field(None, description="飞书 Webhook 地址")
    enable_trade_signal: bool = Field(True, description="交易信号推送")
    enable_position_change: bool = Field(True, description="持仓变动通知")
    enable_risk_alert: bool = Field(True, description="风险预警通知")
    enable_daily_report: bool = Field(True, description="每日报告推送")


class SettingsOut(BaseModel):
    """完整配置输出（不含敏感信息）"""
    broker: dict
    risk: dict
    feishu: dict


# ========== 辅助函数 ==========

def _mask_secret(value: Optional[str]) -> Optional[str]:
    """敏感字段脱敏"""
    if not value:
        return value
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def _update_env_file(key: str, value: str) -> None:
    """更新 .env 文件中的单个配置项"""
    env_path = ".env"
    lines = []
    found = False

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        pass

    new_line = f"{key}={value}\n"
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = new_line
            found = True
            break

    if not found:
        lines.append(new_line)

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def _update_multiple_env(items: dict) -> None:
    """批量更新 .env 文件"""
    for key, value in items.items():
        _update_env_file(key, str(value))


# ========== API 路由 ==========

@router.get("/", response_model=SettingsOut)
async def get_settings():
    """获取当前系统配置（不含敏感信息）"""
    return SettingsOut(
        broker={
            "broker_type": settings.BROKER_TYPE,
            "app_id": settings.FEISHU_APP_ID or "",
            "app_secret": _mask_secret(settings.FEISHU_APP_SECRET),
        },
        risk={
            "max_position_ratio": settings.MAX_POSITION_RATIO,
            "max_total_positions": settings.MAX_TOTAL_POSITIONS,
            "stop_loss_ratio": settings.STOP_LOSS_RATIO,
            "daily_loss_limit": settings.DAILY_LOSS_LIMIT,
            "weekly_loss_limit": settings.WEEKLY_LOSS_LIMIT,
            "min_trade_amount": settings.MIN_TRADE_AMOUNT,
        },
        feishu={
            "webhook_url": settings.FEISHU_WEBHOOK_URL,
            "enable_trade_signal": settings.FEISHU_ENABLE_TRADE_SIGNAL,
            "enable_position_change": settings.FEISHU_ENABLE_POSITION_CHANGE,
            "enable_risk_alert": settings.FEISHU_ENABLE_RISK_ALERT,
            "enable_daily_report": settings.FEISHU_ENABLE_DAILY_REPORT,
        },
    )


@router.post("/broker", response_model=dict)
async def save_broker_config(config: BrokerConfig):
    """保存券商配置"""
    try:
        _update_multiple_env({
            "BROKER_TYPE": config.broker_type or "pingan",
            "BROKER_APP_ID": config.app_id or "",
            "BROKER_APP_SECRET": config.app_secret or "",
        })
        return {
            "success": True,
            "message": "券商配置已保存",
            "broker_type": config.broker_type,
        }
    except Exception as e:
        logger.error(f"保存券商配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存失败: {e}")


@router.post("/risk", response_model=dict)
async def save_risk_config(config: RiskConfig):
    """保存风控配置"""
    try:
        _update_multiple_env({
            "MAX_POSITION_RATIO": config.max_position_ratio,
            "MAX_TOTAL_POSITIONS": config.max_total_positions,
            "STOP_LOSS_RATIO": config.stop_loss_ratio,
            "DAILY_LOSS_LIMIT": config.daily_loss_limit,
            "WEEKLY_LOSS_LIMIT": config.weekly_loss_limit,
            "MIN_TRADE_AMOUNT": config.min_trade_amount,
        })
        return {
            "success": True,
            "message": "风控配置已保存",
            "config": config.model_dump(),
        }
    except Exception as e:
        logger.error(f"保存风控配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存失败: {e}")


@router.post("/feishu", response_model=dict)
async def save_feishu_config(config: FeishuConfig):
    """保存飞书通知配置"""
    try:
        _update_multiple_env({
            "FEISHU_WEBHOOK_URL": config.webhook_url or "",
            "FEISHU_ENABLE_TRADE_SIGNAL": config.enable_trade_signal,
            "FEISHU_ENABLE_POSITION_CHANGE": config.enable_position_change,
            "FEISHU_ENABLE_RISK_ALERT": config.enable_risk_alert,
            "FEISHU_ENABLE_DAILY_REPORT": config.enable_daily_report,
        })
        return {
            "success": True,
            "message": "飞书通知配置已保存",
            "config": config.model_dump(),
        }
    except Exception as e:
        logger.error(f"保存飞书配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存失败: {e}")

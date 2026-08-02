"""
AI Stock - 配置文件
"""
from pydantic import field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""

    @field_validator("LLM_TEMPERATURE", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v):
        """.env 中空字符串按 None 处理（不下发该参数给模型）"""
        if v == "" or v is None:
            return None
        return v

    # 应用
    APP_NAME: str = "AI Stock Trading System"
    DEBUG: bool = True
    API_PREFIX: str = "/api"
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:5173"]

    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://aistock:aistock123@localhost:5432/aistock"
    REDIS_URL: str = "redis://localhost:6379"
    MONGODB_URL: str = "mongodb://localhost:27017/aistock"

    # LLM 配置（OpenAI 兼容协议，kimi/deepseek/openai/anthropic-proxy 通用）
    LLM_BASE_URL: str = "https://api.moonshot.cn/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "kimi-k2.6"
    LLM_TEMPERATURE: float | None = None  # None 表示不下发，由模型用默认值（kimi-k2.6 强制 1）
    LLM_MAX_TOKENS: int = 2048
    LLM_TIMEOUT: int = 120

    # 飞书配置
    FEISHU_WEBHOOK_URL: str = ""
    FEISHU_APP_ID: str = ""
    FEISHU_APP_SECRET: str = ""
    FEISHU_ENABLE_TRADE_SIGNAL: bool = True
    FEISHU_ENABLE_POSITION_CHANGE: bool = True
    FEISHU_ENABLE_RISK_ALERT: bool = True
    FEISHU_ENABLE_DAILY_REPORT: bool = True

    # 券商配置
    BROKER_APP_ID: str = ""
    BROKER_APP_SECRET: str = ""

    # 行情数据源
    MARKET_DATA_SOURCE: str = "tdx"  # tdx | eastmoney | tushare（保留字段，实际走 datasource 适配层）

    # 同花顺 iFinD 官方 HTTP API（配置 refresh_token 后 auto 模式自动启用）
    IFIND_REFRESH_TOKEN: str = ""
    # 行情数据源优先级: auto | ifind | free | mock
    MARKET_DATA_PRIORITY: str = "auto"
    # 问财免费通道 cookie（可选，配置后启用 pywencai 自然语言选股）
    PYWENCAI_COOKIE: str = ""

    # 天眼查开放平台（https://www.tianyancha.com/data 申请，按次计费）
    TIANYANCHA_TOKEN: str = ""
    TIANYANCHA_DAILY_LIMIT: int = 100  # 每日调用上限，防止超额计费

    # 券商配置
    BROKER_TYPE: str = "pingan"  # pingan | tiger | futu

    # 风险控制（10万资金默认配置）
    MAX_POSITION_RATIO: float = 0.2  # 单只股票最大仓位比例
    MAX_TOTAL_POSITIONS: int = 5  # 最大持仓数量
    STOP_LOSS_RATIO: float = 0.05  # 止损比例
    DAILY_LOSS_LIMIT: float = 0.015  # 每日最大亏损
    WEEKLY_LOSS_LIMIT: float = 0.05  # 每周最大亏损
    MIN_TRADE_AMOUNT: float = 2000.0  # 最小交易金额

    # 回测配置
    BACKTEST_COMMISSION: float = 0.00025  # 佣金（万2.5）
    BACKTEST_STAMP_TAX: float = 0.001  # 印花税（千1）
    BACKTEST_SLIPPAGE: float = 0.001  # 滑点（千1）

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

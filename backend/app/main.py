"""
AI Stock - 主应用入口
"""
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import asyncio
import sys

from app.core.config import settings
from app.models.database import (
    init_postgres, close_postgres,
    init_mongodb, close_mongodb,
    init_redis, close_redis,
    async_session_maker,
)
from app.core.order_executor import order_executor
from app.services.guzhang_client import guzhang_client
from app.services.news_ingest_service import news_ingest_service
from app.api import news as news_api_module

from app.services.precalc_service import precalc_service
from app.services import moneyflow_service, lhb_service
from app.api import market, portfolio, strategy, order, backtest, news, llm, feishu, datasource, company, monitor, moneyflow, lhb, patterns, stock_pool, precalc
from app.api import settings as settings_api


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    logger.info("AI Stock 系统启动...")

    # 初始化数据库
    try:
        await init_postgres()
        logger.info("PostgreSQL 初始化完成")
    except Exception as e:
        logger.warning(f"PostgreSQL 初始化失败: {e}")

    try:
        await init_mongodb()
        logger.info("MongoDB 初始化完成")
    except Exception as e:
        logger.warning(f"MongoDB 初始化失败: {e}")

    try:
        await init_redis()
        logger.info("Redis 初始化完成")
    except Exception as e:
        logger.warning(f"Redis 初始化失败: {e}")

    # 初始化模拟账户
    await order_executor.initialize(initial_capital=100000.0)
    logger.info("模拟交易账户初始化完成，初始资金: 100000.0")

    # 启动鼓掌财经实时快讯客户端
    try:
        asyncio.create_task(guzhang_client.start())
        logger.info("鼓掌财经客户端启动任务已创建")
    except Exception as e:
        logger.warning(f"鼓掌财经客户端启动失败: {e}")

    # 启动新闻 Ingest 服务（DB写入 + WebSocket 广播）
    try:
        news_ingest_service._gz = guzhang_client
        news_ingest_service._db_factory = async_session_maker
        news_ingest_service._broadcast = news_api_module.manager.broadcast
        await news_ingest_service.start()
        logger.info("新闻 Ingest 服务已启动")
    except Exception as e:
        logger.warning(f"新闻 Ingest 服务启动失败: {e}")

    # 启动市场数据预热服务
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        precalc_service.register("moneyflow_rank_inflow", lambda: moneyflow_service.get_money_flow_rank(period="today", direction="inflow", limit=100, date=today_str))
        precalc_service.register("moneyflow_rank_outflow", lambda: moneyflow_service.get_money_flow_rank(period="today", direction="outflow", limit=100, date=today_str))
        precalc_service.register("moneyflow_sector_concept", lambda: moneyflow_service.get_sector_money_flow(sector_type="concept", limit=50, date=today_str))
        precalc_service.register("moneyflow_sector_industry", lambda: moneyflow_service.get_sector_money_flow(sector_type="industry", limit=50, date=today_str))
        precalc_service.register("moneyflow_overview", lambda: moneyflow_service.get_market_flow_overview(date=today_str))
        precalc_service.register("lhb_today_all", lambda: lhb_service.get_today_lhb(limit=100, direction="all", date=today_str))
        precalc_service.register("lhb_today_buy", lambda: lhb_service.get_today_lhb(limit=100, direction="buy", date=today_str))
        precalc_service.register("lhb_today_sell", lambda: lhb_service.get_today_lhb(limit=100, direction="sell", date=today_str))
        precalc_service.register("lhb_stats_daily", lambda: lhb_service.get_lhb_daily_stats(days=5))
        precalc_service.start()
        logger.info("市场数据预热服务已启动")
    except Exception as e:
        logger.warning(f"市场数据预热服务启动失败: {e}")

    yield

    # 关闭
    logger.info("AI Stock 系统关闭...")
    try:
        await precalc_service.stop()
        logger.info("市场数据预热服务已关闭")
    except Exception as e:
        logger.warning(f"市场数据预热服务关闭异常: {e}")
    await close_postgres()
    await close_mongodb()
    await close_redis()
    try:
        await news_ingest_service.stop()
        logger.info("新闻 Ingest 服务已关闭")
    except Exception as e:
        logger.warning(f"新闻 Ingest 服务关闭异常: {e}")
    try:
        await guzhang_client.stop()
        logger.info("鼓掌财经客户端已关闭")
    except Exception as e:
        logger.warning(f"鼓掌财经客户端关闭异常: {e}")
    logger.info("AI Stock 系统关闭完成")


# 创建应用
app = FastAPI(
    title="AI Stock Trading System",
    description="""
    AI量化交易系统API

    ## 功能模块
    - **行情服务**: 实时股票行情、K线数据、市场情绪
    - **策略引擎**: 多策略支持、信号生成、每日推荐
    - **订单执行**: 模拟/实盘交易下单
    - **回测服务**: 策略回测、指标分析、参数优化
    - **新闻分析**: 实时新闻、舆情分析、买点判断
    - **LLM服务**: 自然语言策略生成
    - **飞书推送**: 交易信号推送、风险预警
    """,
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(market.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(strategy.router, prefix="/api")
app.include_router(order.router, prefix="/api")
app.include_router(backtest.router, prefix="/api")
app.include_router(news.router, prefix="/api")
app.include_router(llm.router, prefix="/api")
app.include_router(feishu.router, prefix="/api")
app.include_router(datasource.router, prefix="/api")
app.include_router(company.router, prefix="/api")
app.include_router(monitor.router, prefix="/api")
app.include_router(moneyflow.router, prefix="/api")
app.include_router(lhb.router, prefix="/api")
app.include_router(patterns.router, prefix="/api")
app.include_router(stock_pool.router, prefix="/api")
app.include_router(precalc.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "AI Stock Trading System",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


# 配置日志
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)
logger.add(
    "data/logs/app_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    level="DEBUG"
)

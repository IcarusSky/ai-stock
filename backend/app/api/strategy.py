"""
AI Stock - 策略API路由
"""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime
import uuid

from app.schemas.strategy import (
    Strategy, StrategyCreate, StrategyUpdate, StrategySignal,
    MarketEnv, DailyRecommendation
)
from app.services.strategy_engine import strategy_engine
from app.services.market_data_service import market_data_service
from app.services.news_service import news_service

router = APIRouter(prefix="/strategy", tags=["策略"])


# 内存存储（实际项目应使用数据库）
_strategies: dict = {}


@router.get("/list", response_model=List[Strategy])
async def list_strategies():
    """获取策略列表（只在首次访问时初始化默认策略）"""
    global _strategies

    if not _strategies:
        default_strategies = [
            Strategy(
                id="strategy_001",
                name="趋势跟踪策略",
                type="TREND_FOLLOWING",
                description="跟随短期趋势，MA金叉买入，死叉卖出",
                params={"ma_period": 20, "stop_loss": 0.05},
                rules=[],
                created_at=datetime.now(),
                updated_at=datetime.now(),
                status="ACTIVE"
            ),
            Strategy(
                id="strategy_002",
                name="均值回归策略",
                type="MEAN_REVERSION",
                description="价格触及布林带极端位置时反向交易",
                params={"bb_period": 20, "rsi_period": 14},
                rules=[],
                created_at=datetime.now(),
                updated_at=datetime.now(),
                status="ACTIVE"
            ),
            Strategy(
                id="strategy_003",
                name="突破策略",
                type="BREAKTHROUGH",
                description="放量突破20日高点时买入",
                params={"breakout_period": 20, "volume_ratio": 1.5},
                rules=[],
                created_at=datetime.now(),
                updated_at=datetime.now(),
                status="ACTIVE"
            ),
        ]

        for s in default_strategies:
            _strategies[s.id] = s
            strategy_engine.register_strategy(s)

    return list(_strategies.values())


@router.post("/register", response_model=Strategy)
async def register_strategy(strategy: StrategyCreate):
    """注册新策略"""
    strategy_id = str(uuid.uuid4())[:12]
    new_strategy = Strategy(
        id=strategy_id,
        name=strategy.name,
        type=strategy.type,
        description=strategy.description,
        params=strategy.params,
        rules=strategy.rules,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        status="ACTIVE"
    )
    _strategies[strategy_id] = new_strategy
    strategy_engine.register_strategy(new_strategy)
    return new_strategy


@router.put("/{strategy_id}", response_model=Strategy)
async def update_strategy(strategy_id: str, update: StrategyUpdate):
    """更新策略"""
    if strategy_id not in _strategies:
        raise HTTPException(status_code=404, detail="策略未找到")

    strategy = _strategies[strategy_id]
    update_data = update.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(strategy, key, value)

    strategy.updated_at = datetime.now()
    return strategy


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: str):
    """删除策略"""
    if strategy_id not in _strategies:
        raise HTTPException(status_code=404, detail="策略未找到")

    del _strategies[strategy_id]
    strategy_engine.unregister_strategy(strategy_id)
    return {"success": True}


@router.get("/{strategy_id}/signal", response_model=List[StrategySignal])
async def get_strategy_signal(strategy_id: str, stock_code: str):
    """获取策略信号"""
    if strategy_id not in _strategies:
        raise HTTPException(status_code=404, detail="策略未找到")

    # 获取K线数据
    klines = await market_data_service.get_kline_data(stock_code)
    if len(klines) < 60:
        raise HTTPException(status_code=400, detail="K线数据不足")

    # 生成信号
    signals = await strategy_engine.generate_signals(stock_code, klines, [strategy_id])
    return signals


@router.post("/evaluate", response_model=MarketEnv)
async def evaluate_market_env():
    """评估当前市场环境"""
    sentiment = await market_data_service.get_market_sentiment()

    # 根据情绪评分判断市场环境
    score = sentiment.sentiment_score

    if score >= 65:
        trend = "BULL"
        overall = "OPTIMISTIC"
    elif score <= 40:
        trend = "BEAR"
        overall = "PESSIMISTIC"
    else:
        trend = "NEUTRAL"
        overall = "NEUTRAL"

    return MarketEnv(
        trend=trend,
        volatility="MEDIUM",
        volume="HIGH" if sentiment.total_amount > 5000000000 else "MEDIUM",
        sector_rotation="MEDIUM",
        overall=overall,
        score=score,
        description=f"市场情绪评分{score:.0f}，{'偏多' if score > 50 else '偏空'}"
    )


@router.get("/daily/recommend", response_model=DailyRecommendation)
async def get_daily_recommendation():
    """获取每日策略推荐"""
    market_env = await evaluate_market_env()

    # 根据市场环境推荐策略
    if market_env.trend == "BULL":
        recommended = [
            {"strategy_id": "strategy_001", "name": "趋势跟踪策略", "weight": 0.6},
            {"strategy_id": "strategy_003", "name": "突破策略", "weight": 0.4},
        ]
        risk_level = "中等"
    elif market_env.trend == "BEAR":
        recommended = [
            {"strategy_id": "strategy_002", "name": "均值回归策略", "weight": 0.7},
        ]
        risk_level = "较高"
    else:
        recommended = [
            {"strategy_id": "strategy_002", "name": "均值回归策略", "weight": 0.5},
            {"strategy_id": "strategy_003", "name": "突破策略", "weight": 0.3},
        ]
        risk_level = "中等"

    # 根据趋势动态生成仓位建议
    position_advice = {
        "BULL": "5-7成",
        "BEAR": "0-2成",
        "NEUTRAL": "3-5成"
    }.get(market_env.trend, "3-5成")

    # 从市场情绪报告获取热点板块
    try:
        sentiment_report = await news_service.get_market_sentiment_report()
        focus_sectors = [s.get("name") for s in sentiment_report.hot_sectors[:3]]
    except Exception:
        focus_sectors = []

    if not focus_sectors:
        focus_sectors = ["银行板块", "新能源板块"]

    return DailyRecommendation(
        date=datetime.now().strftime('%Y-%m-%d'),
        market_env=market_env,
        recommended_strategies=recommended,
        trading_plan={
            "仓位建议": position_advice,
            "重点关注": focus_sectors,
            "风险提示": "控制仓位，防范回调"
        },
        risk_alert=risk_level
    )

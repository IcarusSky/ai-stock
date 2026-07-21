"""
AI Stock - 策略引擎服务
"""
import pandas as pd
import numpy as np
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import asyncio
from loguru import logger

from app.schemas.strategy import (
    Strategy, StrategySignal, StrategyType, StrategyRule, RuleType
)
from app.schemas.market import KLine


class StrategyEngine:
    """策略引擎"""

    def __init__(self):
        self.strategies: Dict[str, Strategy] = {}
        self._indicators_cache = {}

    def register_strategy(self, strategy: Strategy):
        """注册策略"""
        self.strategies[strategy.id] = strategy
        logger.info(f"注册策略: {strategy.name} ({strategy.id})")

    def unregister_strategy(self, strategy_id: str):
        """注销策略"""
        if strategy_id in self.strategies:
            del self.strategies[strategy_id]
            logger.info(f"注销策略: {strategy_id}")

    async def generate_signals(
        self,
        stock_code: str,
        klines: List[KLine],
        strategy_ids: Optional[List[str]] = None
    ) -> List[StrategySignal]:
        """生成交易信号"""
        signals = []

        if not klines or len(klines) < 60:
            return signals

        df = self._klines_to_dataframe(klines)
        self._calculate_indicators(df)

        strategies_to_check = (
            [self.strategies[sid] for sid in strategy_ids if sid in self.strategies]
            if strategy_ids
            else list(self.strategies.values())
        )

        for strategy in strategies_to_check:
            signal = await self._evaluate_strategy(strategy, stock_code, df)
            if signal:
                signals.append(signal)

        return signals

    def _klines_to_dataframe(self, klines: List[KLine]) -> pd.DataFrame:
        """K线数据转DataFrame"""
        data = [{
            'date': k.date,
            'open': k.open,
            'high': k.high,
            'low': k.low,
            'close': k.close,
            'volume': k.volume
        } for k in klines]
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        return df

    def _calculate_indicators(self, df: pd.DataFrame):
        """计算技术指标"""
        close = df['close']

        # 移动平均线
        df['MA5'] = close.rolling(window=5).mean()
        df['MA10'] = close.rolling(window=10).mean()
        df['MA20'] = close.rolling(window=20).mean()
        df['MA60'] = close.rolling(window=60).mean()

        # 指数移动平均
        df['EMA12'] = close.ewm(span=12, adjust=False).mean()
        df['EMA26'] = close.ewm(span=26, adjust=False).mean()

        # MACD
        df['MACD'] = df['EMA12'] - df['EMA26']
        df['MACD_SIGNAL'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_HIST'] = df['MACD'] - df['MACD_SIGNAL']

        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # 布林带
        df['BB_MID'] = close.rolling(window=20).mean()
        bb_std = close.rolling(window=20).std()
        df['BB_UPPER'] = df['BB_MID'] + 2 * bb_std
        df['BB_LOWER'] = df['BB_MID'] - 2 * bb_std

        # 成交量均线
        df['VOL_MA5'] = df['volume'].rolling(window=5).mean()
        df['VOL_MA10'] = df['volume'].rolling(window=10).mean()

        # KDJ (随机指标)
        low14 = df['low'].rolling(window=14).min()
        high14 = df['high'].rolling(window=14).max()
        df['RSV'] = 100 * (close - low14) / (high14 - low14)
        df['K'] = df['RSV'].ewm(com=2, adjust=False).mean()
        df['D'] = df['K'].ewm(com=2, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']

    async def _evaluate_strategy(
        self,
        strategy: Strategy,
        stock_code: str,
        df: pd.DataFrame
    ) -> Optional[StrategySignal]:
        """评估策略"""
        if len(df) < 2:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # 根据策略类型生成信号
        if strategy.type == StrategyType.TREND_FOLLOWING:
            return self._trend_following_signal(strategy, stock_code, latest, prev, df)
        elif strategy.type == StrategyType.MEAN_REVERSION:
            return self._mean_reversion_signal(strategy, stock_code, latest, prev, df)
        elif strategy.type == StrategyType.BREAKTHROUGH:
            return self._breakthrough_signal(strategy, stock_code, latest, prev, df)
        elif strategy.type == StrategyType.SECTOR_ROTATION:
            return self._sector_rotation_signal(strategy, stock_code, latest, prev, df)

        return None

    def _trend_following_signal(
        self,
        strategy: Strategy,
        stock_code: str,
        latest: pd.Series,
        prev: pd.Series,
        df: pd.DataFrame
    ) -> Optional[StrategySignal]:
        """趋势跟踪策略信号"""
        # 金叉：MA5上穿MA20
        ma5_above_ma20_now = latest['MA5'] > latest['MA20']
        ma5_below_ma20_prev = prev['MA5'] <= prev['MA20']

        # 买入信号：MA5上穿MA20且价格在MA5上方
        if ma5_above_ma20_now and ma5_below_ma20_prev:
            return StrategySignal(
                strategy_id=strategy.id,
                strategy_name=strategy.name,
                stock_code=stock_code,
                signal="BUY",
                confidence=0.7,
                price=latest['close'],
                target_price=latest['close'] * 1.05,
                stop_loss=latest['close'] * 0.97,
                position_ratio=0.2,
                reason="MA5上穿MA20，形成短期上升趋势",
                created_at=datetime.now()
            )

        # 死叉：MA5下穿MA20
        ma5_below_ma20_now = latest['MA5'] < latest['MA20']
        ma5_above_ma20_prev = prev['MA5'] >= prev['MA20']

        if ma5_below_ma20_now and ma5_above_ma20_prev:
            return StrategySignal(
                strategy_id=strategy.id,
                strategy_name=strategy.name,
                stock_code=stock_code,
                signal="SELL",
                confidence=0.7,
                price=latest['close'],
                reason="MA5下穿MA20，趋势转空",
                created_at=datetime.now()
            )

        return StrategySignal(
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            stock_code=stock_code,
            signal="HOLD",
            confidence=0.5,
            price=latest['close'],
            reason="趋势不明显，持仓观察",
            created_at=datetime.now()
        )

    def _mean_reversion_signal(
        self,
        strategy: Strategy,
        stock_code: str,
        latest: pd.Series,
        prev: pd.Series,
        df: pd.DataFrame
    ) -> Optional[StrategySignal]:
        """均值回归策略信号"""
        # 价格触及布林带下轨且RSI超卖
        if latest['close'] < latest['BB_LOWER'] and latest['RSI'] < 30:
            return StrategySignal(
                strategy_id=strategy.id,
                strategy_name=strategy.name,
                stock_code=stock_code,
                signal="BUY",
                confidence=0.75,
                price=latest['close'],
                target_price=latest['BB_MID'],
                stop_loss=latest['BB_LOWER'] * 0.98,
                position_ratio=0.2,
                reason="价格触及布林带下轨且RSI超卖，均值回归概率大",
                created_at=datetime.now()
            )

        # 价格触及布林带上轨且RSI超买
        if latest['close'] > latest['BB_UPPER'] and latest['RSI'] > 70:
            return StrategySignal(
                strategy_id=strategy.id,
                strategy_name=strategy.name,
                stock_code=stock_code,
                signal="SELL",
                confidence=0.75,
                price=latest['close'],
                reason="价格触及布林带上轨且RSI超买，注意回调风险",
                created_at=datetime.now()
            )

        return StrategySignal(
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            stock_code=stock_code,
            signal="HOLD",
            confidence=0.5,
            price=latest['close'],
            reason="价格运行在布林带中轨附近",
            created_at=datetime.now()
        )

    def _breakthrough_signal(
        self,
        strategy: Strategy,
        stock_code: str,
        latest: pd.Series,
        prev: pd.Series,
        df: pd.DataFrame
    ) -> Optional[StrategySignal]:
        """突破策略信号"""
        # 放量突破20日高点
        volume_ratio = latest['volume'] / latest['VOL_MA5'] if latest['VOL_MA5'] > 0 else 0
        high_20 = df['high'].rolling(window=20).max().iloc[-2]  # 昨天的20日最高

        if latest['close'] > high_20 and volume_ratio > 1.5:
            return StrategySignal(
                strategy_id=strategy.id,
                strategy_name=strategy.name,
                stock_code=stock_code,
                signal="BUY",
                confidence=0.7,
                price=latest['close'],
                target_price=latest['close'] * 1.08,
                stop_loss=latest['close'] * 0.95,
                position_ratio=0.25,
                reason=f"放量{volume_ratio:.1f}倍突破20日高点{high_20:.2f}",
                created_at=datetime.now()
            )

        # 跌破20日低点
        low_20 = df['low'].rolling(window=20).min().iloc[-2]

        if latest['close'] < low_20:
            return StrategySignal(
                strategy_id=strategy.id,
                strategy_name=strategy.name,
                stock_code=stock_code,
                signal="SELL",
                confidence=0.65,
                price=latest['close'],
                reason="跌破20日低点，突破失败",
                created_at=datetime.now()
            )

        return StrategySignal(
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            stock_code=stock_code,
            signal="HOLD",
            confidence=0.5,
            price=latest['close'],
            reason="等待突破确认",
            created_at=datetime.now()
        )

    def _sector_rotation_signal(
        self,
        strategy: Strategy,
        stock_code: str,
        latest: pd.Series,
        prev: pd.Series,
        df: pd.DataFrame
    ) -> Optional[StrategySignal]:
        """板块轮动策略信号（简化版）"""
        # 使用MACD金叉死叉判断
        macd_above_signal_now = latest['MACD'] > latest['MACD_SIGNAL']
        macd_below_signal_prev = prev['MACD'] <= prev['MACD_SIGNAL']

        if macd_above_signal_now and macd_below_signal_prev:
            return StrategySignal(
                strategy_id=strategy.id,
                strategy_name=strategy.name,
                stock_code=stock_code,
                signal="BUY",
                confidence=0.6,
                price=latest['close'],
                target_price=latest['close'] * 1.03,
                stop_loss=latest['close'] * 0.98,
                position_ratio=0.15,
                reason="MACD金叉，板块轮动加速",
                created_at=datetime.now()
            )

        return StrategySignal(
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            stock_code=stock_code,
            signal="HOLD",
            confidence=0.5,
            price=latest['close'],
            reason="MACD未发出信号",
            created_at=datetime.now()
        )


# 全局策略引擎实例
strategy_engine = StrategyEngine()

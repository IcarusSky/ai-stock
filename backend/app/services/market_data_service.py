"""
AI Stock - 行情数据服务
"""
import asyncio
from typing import List, Dict, Optional, Callable
from datetime import datetime, time
import pandas as pd
from loguru import logger
import random

from app.schemas.market import StockQuote, KLine, MarketSentiment
from app.services.datasource.router import data_source_router


class MarketDataService:
    """行情数据服务"""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._quotes_cache: Dict[str, StockQuote] = {}
        self._last_update: Dict[str, datetime] = {}
        self._is_market_open = False

    async def get_realtime_quote(self, stock_code: str) -> Optional[StockQuote]:
        """获取实时行情（优先真实数据源，失败回退模拟数据）"""
        try:
            quote = await data_source_router.get_quote(stock_code)
            if quote:
                if not quote.name:
                    quote.name = self._get_stock_name(stock_code)
                self._quotes_cache[stock_code] = quote
                return quote
        except Exception as e:
            logger.warning(f"真实行情获取失败({stock_code})，回退模拟数据: {e}")

        base_price = self._get_base_price(stock_code)
        change_pct = random.uniform(-5, 5)
        change = base_price * change_pct / 100

        quote = StockQuote(
            code=stock_code,
            name=self._get_stock_name(stock_code),
            price=round(base_price, 2),
            change=round(change, 2),
            change_pct=round(change_pct, 2),
            open=round(base_price * random.uniform(0.98, 1.02), 2),
            high=round(base_price * random.uniform(1.0, 1.05), 2),
            low=round(base_price * random.uniform(0.95, 1.0), 2),
            volume=random.randint(1000000, 100000000),
            amount=random.randint(10000000, 1000000000),
            amplitude=round(random.uniform(1, 8), 2),
            turnover=round(random.uniform(0.5, 15), 2),
            pe=round(random.uniform(10, 50), 2),
            pb=round(random.uniform(1, 5), 2),
            market_cap=random.randint(10000000000, 1000000000000),
            timestamp=datetime.now()
        )

        self._quotes_cache[stock_code] = quote
        return quote

    async def get_realtime_quotes(self, stock_codes: List[str]) -> List[StockQuote]:
        """批量获取实时行情"""
        tasks = [self.get_realtime_quote(code) for code in stock_codes]
        quotes = await asyncio.gather(*tasks)
        return [q for q in quotes if q is not None]

    async def get_kline_data(
        self,
        stock_code: str,
        period: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[KLine]:
        """获取K线数据（优先真实数据源，失败回退模拟数据）"""
        try:
            real_klines = await data_source_router.get_kline(stock_code, start_date, end_date)
            if real_klines:
                return real_klines
        except Exception as e:
            logger.warning(f"真实K线获取失败({stock_code})，回退模拟数据: {e}")

        klines = []
        base_price = self._get_base_price(stock_code)
        current_price = base_price

        # 生成最近60个交易日的模拟数据
        dates = pd.date_range(end=datetime.now(), periods=60, freq='B')

        for i, date in enumerate(dates):
            change_pct = random.uniform(-3, 3)
            open_price = current_price
            close_price = current_price * (1 + change_pct / 100)
            high_price = max(open_price, close_price) * random.uniform(1.0, 1.03)
            low_price = min(open_price, close_price) * random.uniform(0.97, 1.0)

            kline = KLine(
                code=stock_code,
                date=date.strftime('%Y-%m-%d'),
                open=round(open_price, 2),
                high=round(high_price, 2),
                low=round(low_price, 2),
                close=round(close_price, 2),
                volume=random.randint(1000000, 50000000),
                amount=random.randint(10000000, 500000000),
                change_pct=round(change_pct, 2)
            )
            klines.append(kline)
            current_price = close_price

        return klines

    async def get_market_sentiment(self) -> MarketSentiment:
        """获取市场情绪"""
        # 模拟市场情绪数据
        return MarketSentiment(
            advance_count=random.randint(1500, 3000),
            decline_count=random.randint(1000, 2500),
            limit_up_count=random.randint(30, 100),
            limit_down_count=random.randint(10, 50),
            total_volume=random.randint(200000000, 500000000),
            total_amount=random.randint(3000000000, 8000000000),
            main_net_inflow=random.randint(-500000000, 500000000),
            sentiment_score=round(random.uniform(40, 80), 2)
        )

    async def subscribe(self, stock_code: str, callback: Callable):
        """订阅行情更新"""
        if stock_code not in self._subscribers:
            self._subscribers[stock_code] = []
        self._subscribers[stock_code].append(callback)

    async def unsubscribe(self, stock_code: str, callback: Callable):
        """取消订阅"""
        if stock_code in self._subscribers:
            self._subscribers[stock_code].remove(callback)

    async def notify_subscribers(self, stock_code: str, quote: StockQuote):
        """通知订阅者"""
        if stock_code in self._subscribers:
            for callback in self._subscribers[stock_code]:
                try:
                    await callback(quote)
                except Exception as e:
                    logger.error(f"通知订阅者失败: {e}")

    def _get_base_price(self, stock_code: str) -> float:
        """根据股票代码返回基准价格"""
        # 模拟不同股票的价格范围
        if stock_code.startswith('6'):
            return random.uniform(10, 100)  # 上证
        elif stock_code.startswith('0'):
            return random.uniform(5, 80)   # 深证
        elif stock_code.startswith('3'):
            return random.uniform(10, 50)  # 创业板
        return 20.0

    def _get_stock_name(self, stock_code: str) -> str:
        """获取股票名称（模拟）"""
        names = {
            '000001': '平安银行',
            '000002': '万科A',
            '600000': '浦发银行',
            '600036': '招商银行',
            '600519': '贵州茅台',
            '000858': '五粮液',
            '002594': '比亚迪',
            '300750': '宁德时代',
        }
        return names.get(stock_code, f'股票{stock_code}')

    def is_market_open(self) -> bool:
        """判断市场是否开盘"""
        now = datetime.now()
        market_time = time(9, 30)
        close_time = time(15, 0)

        if now.weekday() >= 5:  # 周末
            return False

        current_time = now.time()
        return market_time <= current_time <= close_time


# 全局行情服务实例
market_data_service = MarketDataService()

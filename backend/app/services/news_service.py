"""
AI Stock - 新闻分析服务
"""
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
from loguru import logger

from app.schemas.news import NewsItem, NewsAnalysis, MarketSentimentReport
from app.services.llm_service import llm_service
from app.services.guzhang_client import guzhang_client


class NewsService:
    """新闻服务"""

    def __init__(self):
        self._news_cache: Dict[str, NewsItem] = {}
        self._sentiment_report: Optional[MarketSentimentReport] = None

    async def fetch_realtime_news(self) -> List[NewsItem]:
        """获取实时新闻：优先使用鼓掌财经快讯，未就绪则降级到 mock。"""
        realtime = guzhang_client.get_recent(200)
        if realtime:
            for news in realtime:
                self._news_cache[news.id] = news
            logger.info(f"返回 {len(realtime)} 条鼓掌财经实时快讯")
            return realtime

        logger.warning("鼓掌财经快讯未就绪，降级返回 mock 新闻")
        return await self._fetch_mock_news()

    async def _fetch_mock_news(self) -> List[NewsItem]:
        """mock 新闻数据（降级用）。"""
        mock_news = [
            NewsItem(
                id=str(uuid.uuid4())[:12],
                title="央行宣布降准0.5个百分点，释放长期资金约1万亿元",
                content="央行宣布将于近期下调存款准备金率0.5个百分点，预计释放长期资金约1万亿元...",
                source="东方财富",
                url="https://www.eastmoney.com",
                published_at=datetime.now(),
                sentiment="BULLISH",
                sentiment_score=0.8,
                related_stocks=["600000", "600036", "000001"],
                impact_scope="MARKET",
                impact_duration="MEDIUM"
            ),
            NewsItem(
                id=str(uuid.uuid4())[:12],
                title="宁德时代发布超快充电池，充电10分钟续航400公里",
                content="宁德时代今日发布神行PLUS电池，支持4C超快充，充电10分钟可续航400公里...",
                source="同花顺",
                url="https://www.10jqka.com.cn",
                published_at=datetime.now(),
                sentiment="BULLISH",
                sentiment_score=0.9,
                related_stocks=["300750"],
                impact_scope="STOCK",
                impact_duration="LONG"
            ),
            NewsItem(
                id=str(uuid.uuid4())[:12],
                title="比亚迪上半年净利润同比增长超200%",
                content="比亚迪发布业绩预告，上半年净利润同比增长200%-300%，超出市场预期...",
                source="雪球",
                url="https://xueqiu.com",
                published_at=datetime.now(),
                sentiment="BULLISH",
                sentiment_score=0.85,
                related_stocks=["002594"],
                impact_scope="STOCK",
                impact_duration="MEDIUM"
            ),
            NewsItem(
                id=str(uuid.uuid4())[:12],
                title="欧美股市集体大跌，道指暴跌500点",
                content="隔夜美股大幅下跌，科技股普遍承压，纳指跌近2%...",
                source="财联社",
                url="https://www.cls.cn",
                published_at=datetime.now(),
                sentiment="BEARISH",
                sentiment_score=-0.6,
                related_stocks=[],
                impact_scope="MARKET",
                impact_duration="SHORT"
            ),
            NewsItem(
                id=str(uuid.uuid4())[:12],
                title="某知名游资被限制交易，题材股炒作降温",
                content="监管层对涉嫌操纵股价的游资采取限制交易措施，市场题材炒作情绪明显降温...",
                source="东方财富",
                url="https://www.eastmoney.com",
                published_at=datetime.now(),
                sentiment="BEARISH",
                sentiment_score=-0.4,
                related_stocks=[],
                impact_scope="SECTOR",
                impact_duration="SHORT"
            )
        ]

        for news in mock_news:
            self._news_cache[news.id] = news

        return mock_news

    async def analyze_news(self, news_id: str, stock_code: Optional[str] = None) -> Optional[NewsAnalysis]:
        """分析单条新闻"""
        if news_id not in self._news_cache:
            return None

        news = self._news_cache[news_id]

        # 使用LLM分析新闻
        content = news.content or news.title
        analysis_result = await llm_service.analyze_news(content, stock_code)

        return NewsAnalysis(
            news_id=news_id,
            stock_code=stock_code,
            sentiment=analysis_result.get("sentiment", "NEUTRAL"),
            sentiment_score=analysis_result.get("sentiment_score", 0.0),
            is_buy_signal=analysis_result.get("is_buy_signal", False),
            buy_signal_reason=analysis_result.get("buy_signal_reason", ""),
            is_sell_signal=analysis_result.get("is_sell_signal", False),
            sell_signal_reason=analysis_result.get("sell_signal_reason", ""),
            confidence=analysis_result.get("confidence", 0.0),
            impact_analysis=analysis_result.get("impact_analysis", ""),
            related_stocks=analysis_result.get("related_stocks", []),
            recommendation=analysis_result.get("recommendation", "WATCH"),
            analysis_time=datetime.now()
        )

    async def analyze_news_batch(self, news_ids: List[str], stock_code: Optional[str] = None) -> List[NewsAnalysis]:
        """批量分析新闻"""
        tasks = [self.analyze_news(nid, stock_code) for nid in news_ids]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    def _classify_sector(self, stock_code: str) -> str:
        """根据股票代码前缀粗略分类板块"""
        if not stock_code:
            return "其他"
        prefix = stock_code[:3]
        if prefix in ("300", "301"):
            return "创业板"
        if prefix in ("600", "601", "603", "605"):
            return "沪主板"
        if prefix in ("000", "002", "003"):
            return "深主板"
        if prefix == "688":
            return "科创板"
        if stock_code.startswith(("8", "4")):
            return "北交所"
        return "其他"

    def _get_stock_name(self, code: str) -> str:
        """获取股票名称（简化）"""
        names = {
            "000001": "平安银行",
            "000002": "万科A",
            "600000": "浦发银行",
            "600036": "招商银行",
            "600519": "贵州茅台",
            "000858": "五粮液",
            "002594": "比亚迪",
            "300750": "宁德时代",
        }
        return names.get(code, f"股票{code}")

    async def get_market_sentiment_report(self) -> MarketSentimentReport:
        """获取市场情绪报告"""
        news_list = await self.fetch_realtime_news()

        bullish_count = sum(1 for n in news_list if n.sentiment == "BULLISH")
        bearish_count = sum(1 for n in news_list if n.sentiment == "BEARISH")
        neutral_count = sum(1 for n in news_list if n.sentiment == "NEUTRAL")

        # 简单的情绪评分计算
        sentiment_score = (bullish_count - bearish_count) / len(news_list) if news_list else 0

        # 统计缓存新闻中的相关股票频次
        stock_counter: Dict[str, int] = {}
        sector_counter: Dict[str, int] = {}
        stock_sentiment: Dict[str, List[str]] = {}

        for news in self._news_cache.values():
            for code in news.related_stocks:
                stock_counter[code] = stock_counter.get(code, 0) + 1
                sector = self._classify_sector(code)
                sector_counter[sector] = sector_counter.get(sector, 0) + 1
                stock_sentiment.setdefault(code, []).append(news.sentiment)

        # 热点板块
        hot_sectors = [
            {"name": sector, "news_count": count, "sentiment": "BULLISH"}
            for sector, count in sorted(sector_counter.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        # 热点股票
        hot_stocks = []
        for code, count in sorted(stock_counter.items(), key=lambda x: x[1], reverse=True)[:5]:
            sentiments = stock_sentiment.get(code, [])
            bullish = sum(1 for s in sentiments if s == "BULLISH")
            bearish = sum(1 for s in sentiments if s == "BEARISH")
            if bullish > bearish:
                sentiment = "BULLISH"
            elif bearish > bullish:
                sentiment = "BEARISH"
            else:
                sentiment = "NEUTRAL"
            hot_stocks.append({
                "code": code,
                "name": self._get_stock_name(code),
                "sentiment": sentiment
            })

        risk_alerts = []
        if sentiment_score < -0.3:
            risk_alerts.append("市场情绪偏弱，注意控制仓位")
        if bearish_count > bullish_count:
            risk_alerts.append("利空新闻较多，谨慎观望")

        today = datetime.now().strftime('%Y-%m-%d')

        self._sentiment_report = MarketSentimentReport(
            date=today,
            overall_sentiment=sentiment_score,
            sentiment_trend="DETERIORATING" if sentiment_score < 0 else "IMPROVING",
            bullish_news_count=bullish_count,
            bearish_news_count=bearish_count,
            neutral_news_count=neutral_count,
            hot_sectors=hot_sectors,
            hot_stocks=hot_stocks,
            risk_alerts=risk_alerts,
            summary=f"今日共获取{len(news_list)}条新闻，其中利好{bullish_count}条，利空{bearish_count}条"
        )

        return self._sentiment_report

    async def get_stock_related_news(self, stock_code: str) -> List[NewsItem]:
        """获取股票相关新闻"""
        all_news = list(self._news_cache.values())
        return [n for n in all_news if stock_code in n.related_stocks]


# 全局新闻服务实例
news_service = NewsService()

"""
AI Stock - 新闻相关 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime


class NewsItem(BaseModel):
    """新闻条目"""
    id: str
    title: str
    content: Optional[str] = None
    source: str = Field(..., description="来源：东方财富、同花顺、雪球等")
    url: Optional[str] = None
    published_at: datetime
    sentiment: Literal["BULLISH", "BEARISH", "NEUTRAL"] = "NEUTRAL"
    sentiment_score: float = Field(0.0, ge=-1.0, le=1.0, description="情绪评分")
    is_buy_signal: bool = Field(False, description="是否构成买点")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="判断置信度")
    related_stocks: List[str] = Field(default_factory=list, description="相关股票代码")
    impact_scope: Literal["MARKET", "SECTOR", "STOCK"] = "MARKET"
    impact_duration: Literal["SHORT", "MEDIUM", "LONG"] = "SHORT"
    summary: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="原始字段保留（如 categoryId）")


class NewsAnalysisRequest(BaseModel):
    """新闻分析请求"""
    news_id: str
    stock_code: Optional[str] = None  # 可选，指定分析对某只股票的影响


class NewsAnalysis(BaseModel):
    """新闻分析结果"""
    news_id: str
    stock_code: Optional[str] = None
    sentiment: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    sentiment_score: float
    is_buy_signal: bool
    buy_signal_reason: Optional[str] = None
    is_sell_signal: bool = False
    sell_signal_reason: Optional[str] = None
    confidence: float
    impact_analysis: str
    related_stocks: List[str] = []
    recommendation: Literal["BUY", "HOLD", "SELL", "WATCH"] = "WATCH"
    analysis_time: datetime


class MarketSentimentReport(BaseModel):
    """市场情绪报告"""
    date: str
    overall_sentiment: float = Field(0.0, ge=-1.0, le=1.0)
    sentiment_trend: Literal["IMPROVING", "STABLE", "DETERIORATING"]
    bullish_news_count: int = 0
    bearish_news_count: int = 0
    neutral_news_count: int = 0
    hot_sectors: List[dict] = Field(default_factory=list)
    hot_stocks: List[dict] = Field(default_factory=list)
    risk_alerts: List[str] = Field(default_factory=list)
    summary: str

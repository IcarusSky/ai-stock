"""
AI Stock - 新闻API路由
"""
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger
from typing import List, Optional

from app.schemas.news import NewsItem, NewsAnalysis, MarketSentimentReport
from app.services.news_service import news_service
from app.services.guzhang_client import guzhang_client

router = APIRouter(prefix="/news", tags=["新闻"])


@router.get("/realtime", response_model=List[NewsItem])
async def get_realtime_news():
    """获取实时新闻"""
    return await news_service.fetch_realtime_news()


@router.get("/analyze/{news_id}", response_model=NewsAnalysis)
async def analyze_news(news_id: str, stock_code: Optional[str] = None):
    """分析单条新闻"""
    analysis = await news_service.analyze_news(news_id, stock_code)
    if not analysis:
        raise HTTPException(status_code=404, detail="新闻未找到")
    return analysis


@router.post("/analyze/batch", response_model=List[NewsAnalysis])
async def analyze_news_batch(news_ids: List[str], stock_code: Optional[str] = None):
    """批量分析新闻"""
    return await news_service.analyze_news_batch(news_ids, stock_code)


@router.get("/market_sentiment", response_model=MarketSentimentReport)
async def get_market_sentiment_report():
    """获取市场情绪报告"""
    return await news_service.get_market_sentiment_report()


@router.get("/stock_impact/{stock_code}", response_model=List[NewsItem])
async def get_stock_related_news(stock_code: str):
    """获取股票相关新闻"""
    return await news_service.get_stock_related_news(stock_code)


@router.websocket("/ws")
async def news_websocket(websocket: WebSocket):
    """新闻实时 WebSocket：连接后推送最近 50 条，之后实时转发新消息。"""
    await websocket.accept()
    queue = None
    try:
        queue = await guzhang_client.subscribe()
        while True:
            item = await queue.get()
            if item is None:
                break
            await websocket.send_json(item.model_dump(mode="json"))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"新闻 WebSocket 异常: {e}")
    finally:
        if queue:
            guzhang_client.unsubscribe(queue)
        try:
            await websocket.close()
        except Exception:
            pass

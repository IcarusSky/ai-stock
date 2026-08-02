"""
AI Stock - 新闻API路由
"""
import json
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger
from typing import List, Optional

from app.schemas.news import NewsItem, NewsAnalysis, MarketSentimentReport
from app.services.news_service import news_service
from app.services.guzhang_client import guzhang_client

router = APIRouter(prefix="/news", tags=["新闻"])


# ---------------------------------------------------------------------------
# WebSocket 连接管理器
# ---------------------------------------------------------------------------

class ConnectionManager:
    """管理所有活跃的 WebSocket 前端连接。"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket 前端连接已建立，当前 {len(self.active_connections)} 个连接")

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket 前端连接已断开，当前 {len(self.active_connections)} 个连接")

    async def send_text(self, websocket: WebSocket, message: str) -> None:
        try:
            await websocket.send_text(message)
        except Exception:
            self.disconnect(websocket)

    async def broadcast(self, message: NewsItem) -> None:
        """向所有已连接的前端广播消息。"""
        disconnected = []
        payload = json.dumps({"type": "news", "data": message.model_dump(mode="json")})
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# REST 端点
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# WebSocket 端点
# ---------------------------------------------------------------------------

@router.websocket("/ws")
async def news_websocket(websocket: WebSocket):
    """新闻实时 WebSocket（内部订阅模式）：连接后推送最近 50 条，之后实时转发新消息。"""
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


@router.websocket("/ws/realtime")
async def news_realtime_websocket(websocket: WebSocket):
    """
    新闻实时 WebSocket（广播模式）：
    连接后立即推送最近 10 条历史消息，
    之后每次 guzhang_client 收到新消息时主动推送。

    心跳：客户端发送 {"type":"ping"}，服务端回 {"type":"pong"}
    """
    await manager.connect(websocket)

    # 连接时立即推送最近 10 条历史
    try:
        recent = guzhang_client.get_recent(10)
        for item in recent:
            payload = json.dumps({"type": "news", "data": item.model_dump(mode="json")})
            await websocket.send_text(payload)
    except Exception as e:
        logger.warning(f"推送历史消息失败: {e}")

    try:
        while True:
            raw = await websocket.receive_text()
            # 心跳处理
            try:
                msg = json.loads(raw)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    continue
            except (json.JSONDecodeError, KeyError):
                pass  # 非 JSON 消息忽略
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket /ws/realtime 异常: {e}")
        manager.disconnect(websocket)

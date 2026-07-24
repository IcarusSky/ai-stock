"""
AI Stock - 行情API路由
"""
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger
from typing import List, Optional
from datetime import datetime
import asyncio
import json

from app.schemas.market import StockQuote, KLine, WatchlistItem, PortfolioPosition, CapitalCurve, MarketSentiment
from app.services.market_data_service import market_data_service
from app.services.datasource.tencent_ws_client import TencentWSClient
from app.core.order_executor import order_executor

router = APIRouter(prefix="/market", tags=["行情"])


@router.get("/quote/{stock_code}", response_model=StockQuote)
async def get_quote(stock_code: str):
    """获取单只股票实时行情"""
    quote = await market_data_service.get_realtime_quote(stock_code)
    if not quote:
        raise HTTPException(status_code=404, detail="股票未找到")
    return quote


@router.get("/quotes", response_model=List[StockQuote])
async def get_quotes(stock_codes: str):
    """批量获取股票行情，stock_codes用逗号分隔"""
    codes = [c.strip() for c in stock_codes.split(",")]
    if len(codes) > 100:
        raise HTTPException(status_code=400, detail="单次最多查询100只股票")
    return await market_data_service.get_realtime_quotes(codes)


@router.get("/kline/{stock_code}", response_model=List[KLine])
async def get_kline(
    stock_code: str,
    period: str = "daily",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """获取K线数据"""
    return await market_data_service.get_kline_data(stock_code, period, start_date, end_date)


@router.get("/sentiment", response_model=MarketSentiment)
async def get_market_sentiment():
    """获取市场情绪"""
    return await market_data_service.get_market_sentiment()


@router.get("/watchlist", response_model=List[WatchlistItem])
async def get_watchlist():
    """获取自选股列表"""
    # 模拟数据
    return [
        WatchlistItem(code="000001", name="平安银行", tags=["AI推荐", "银行"]),
        WatchlistItem(code="600036", name="招商银行", tags=["价值", "银行"]),
        WatchlistItem(code="600519", name="贵州茅台", tags=["价值", "消费"]),
        WatchlistItem(code="300750", name="宁德时代", tags=["热点", "新能源"]),
        WatchlistItem(code="002594", name="比亚迪", tags=["热点", "汽车"]),
    ]


@router.post("/watchlist")
async def add_to_watchlist(item: WatchlistItem):
    """添加自选股"""
    return {"success": True, "message": f"已添加{item.name}到自选股"}


@router.delete("/watchlist/{stock_code}")
async def remove_from_watchlist(stock_code: str):
    """移除自选股"""
    return {"success": True, "message": f"已从自选股移除{stock_code}"}


# ============================================================
# 实时行情 WebSocket
# ============================================================
class QuoteConnectionManager:
    """行情 WebSocket 连接管理器"""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"行情WS连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"行情WS连接数: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


quote_manager = QuoteConnectionManager()


@router.websocket("/ws/quotes")
async def quotes_websocket(websocket: WebSocket):
    """实时行情 WebSocket

    前端连接后，发送 JSON：{"action":"subscribe","codes":["600000","000001"]}
    服务器持续推送行情数据

    推送格式:
      - {"type": "subscribed", "codes": [...]}  订阅确认
      - {"type": "quote", "data": {...}}         行情数据
      - {"type": "heartbeat", "ts": "..."}       心跳
    """
    await quote_manager.connect(websocket)
    client = TencentWSClient()
    subscribed: set = set()
    push_task = None

    try:
        while True:
            msg = await websocket.receive_text()
            try:
                data = json.loads(msg)
                action = data.get("action")
                if action == "subscribe":
                    codes = data.get("codes", [])
                    for code in codes:
                        normalized = client._normalize(code)
                        subscribed.add(normalized)
                    client.subscribe(codes)
                    await websocket.send_json({
                        "type": "subscribed",
                        "codes": list(subscribed),
                        "count": len(subscribed)
                    })
                    # 启动后台推送任务
                    if push_task is None or push_task.done():
                        push_task = asyncio.create_task(_push_quotes(websocket, client, subscribed, quote_manager))
                elif action == "unsubscribe":
                    codes = data.get("codes", [])
                    for code in codes:
                        normalized = client._normalize(code)
                        subscribed.discard(normalized)
                    client.unsubscribe(codes)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "codes": list(codes)
                    })
                elif action == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        logger.info("行情WS客户端断开")
    except Exception as e:
        logger.warning(f"行情WS异常: {e}")
    finally:
        quote_manager.disconnect(websocket)
        if push_task and not push_task.done():
            push_task.cancel()
        await client.close()


async def _push_quotes(
    ws: WebSocket,
    client: TencentWSClient,
    codes: set,
    manager: QuoteConnectionManager
):
    """后台任务：持续推送行情数据到指定 WebSocket"""
    try:
        async for quote in client.stream():
            # 只推送已订阅的股票
            if quote.get("code") in codes:
                try:
                    await ws.send_json({
                        "type": "quote",
                        "data": quote
                    })
                except WebSocketDisconnect:
                    break
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.warning(f"行情推送任务异常: {e}")

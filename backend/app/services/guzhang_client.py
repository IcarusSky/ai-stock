"""
AI Stock - 鼓掌财经实时快讯 WebSocket 客户端
"""
import asyncio
import json
import re
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import httpx
import websockets
from loguru import logger

from app.schemas.news import NewsItem


GUZHANG_APP_URL = "https://724.guzhang.com/app/"
GUZHANG_WS_URL_TEMPLATE = "wss://swoole2.guzhang.com:443/?token={token}"

# Token 缓存有效期（秒），避免频繁抓取
TOKEN_CACHE_TTL: float = 600.0  # 10 分钟

BULLISH_KEYWORDS = {"涨停", "大涨", "利好", "预增", "中标", "获批", "突破", "创新高", "增持", "回购"}
BEARISH_KEYWORDS = {"跌停", "大跌", "利空", "预减", "处罚", "违规", "风险", "创新低", "减持", "退市"}

# 股票代码正则：6位数字，用于从标题/正文中提取
STOCK_CODE_RE = re.compile(r"\b([0368]\d{5}|9\d{5}|4\d{5})\b")

# 常见板块/概念关键词（用于影响范围判断）
SECTOR_KEYWORDS = {
    "半导体", "芯片", "人工智能", "AI", "新能源", "光伏", "锂电池", "储能",
    "电动车", "汽车", "银行", "证券", "保险", "地产", "医药", "医疗", "白酒",
    "消费", "食品饮料", "传媒", "游戏", "军工", "钢铁", "煤炭", "有色", "稀土",
    "化工", "农业", "猪肉", "养鸡", "航运", "港口", "机场", "旅游", "酒店",
    "机器人", "无人机", "5G", "通信", "计算机", "软件", "互联网", "电商",
}

# 重连参数
RECONNECT_BASE_DELAY: float = 5.0   # 初始等待秒数
RECONNECT_MAX_DELAY: float = 60.0  # 最大等待秒数

# categoryId -> 中文分类映射（用于日志展示）
CATEGORY_NAMES: Dict[int, str] = {
    1: "必看",
    7: "电报",
    10: "港台",
    15: "A股",
    16: "海外",
}


class GuzhangClient:
    """
    鼓掌财经实时快讯 WebSocket 客户端。

    负责：
    1. 动态抓取并刷新 encryptedToken；
    2. 维持 WebSocket 长连接、心跳（ping/pong）；
    3. 接收快讯并做标准化、情绪打标；
    4. 提供内存环形缓冲与订阅者队列，供 REST/WebSocket 使用。
    """

    def __init__(self):
        self._buffer: deque = deque(maxlen=500)
        self._subscribers: Set[asyncio.Queue] = set()
        self._running: bool = False
        self._ws_task: Optional[asyncio.Task] = None
        self._received_count: int = 0
        self._lock = asyncio.Lock()
        # Token 缓存
        self._token: Optional[str] = None
        self._token_fetched_at: float = 0.0
        # 已处理消息 id（去重）
        self._seen_ids: Set[str] = set()

    async def start(self) -> None:
        """启动客户端（幂等）。"""
        async with self._lock:
            if self._running:
                return
            self._running = True

        self._ws_task = asyncio.create_task(self._run_loop())
        logger.info("鼓掌财经客户端已启动")

    async def stop(self) -> None:
        """优雅关闭客户端。"""
        async with self._lock:
            self._running = False

        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

        # 清空订阅者队列，避免前端连接永远挂起
        for q in list(self._subscribers):
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass
        self._subscribers.clear()
        logger.info("鼓掌财经客户端已停止")

    async def _run_loop(self) -> None:
        """核心运行循环：抓 token -> 建连 -> 接收 -> 断线重连（指数退避）。"""
        attempt: int = 0
        while True:
            async with self._lock:
                if not self._running:
                    break

            try:
                token = await self._get_token()
                ws_url = GUZHANG_WS_URL_TEMPLATE.format(token=token)
                logger.info("正在连接鼓掌财经 WebSocket...")
                async with websockets.connect(ws_url, ping_interval=None, close_timeout=10) as ws:
                    logger.info("鼓掌财经 WebSocket 连接成功")
                    attempt = 0  # 重置重试计数
                    await self._receive_loop(ws)
            except asyncio.CancelledError:
                logger.info("鼓掌财经运行循环已取消")
                break
            except Exception as e:
                logger.warning(f"鼓掌财经 WebSocket 异常: {e}")

            # 指数退避重连
            async with self._lock:
                if not self._running:
                    break
            attempt += 1
            delay = min(RECONNECT_BASE_DELAY * (2 ** (attempt - 1)), RECONNECT_MAX_DELAY)
            logger.info(f"第 {attempt} 次重连，{delay:.1f} 秒后尝试...")
            await asyncio.sleep(delay)

        logger.info("鼓掌财经运行循环已退出")

    async def _get_token(self) -> str:
        """返回缓存的 token（10 分钟有效），过期则重新抓取。"""
        now = asyncio.get_event_loop().time()
        if self._token and (now - self._token_fetched_at) < TOKEN_CACHE_TTL:
            return self._token
        self._token = await self._fetch_token()
        self._token_fetched_at = now
        return self._token

    async def _fetch_token(self) -> str:
        """抓取鼓掌财经 APP 页面，提取 encryptedToken。"""
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            resp = await client.get(GUZHANG_APP_URL)
            resp.raise_for_status()
            html = resp.text

        match = re.search(r'var encryptedToken = "(.*?)"', html)
        if not match:
            raise ValueError("无法从鼓掌财经页面提取 encryptedToken")

        token = match.group(1)
        logger.info(f"成功提取鼓掌财经 encryptedToken: {token[:16]}...")
        return token

    async def _receive_loop(self, ws: websockets.WebSocketClientProtocol) -> None:
        """单条连接内的接收循环。"""
        while True:
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=65)
            except asyncio.TimeoutError:
                logger.warning("鼓掌财经 WebSocket 接收超时，准备重连")
                break

            if isinstance(message, bytes):
                message = message.decode("utf-8", errors="ignore")

            if message == "ping":
                await ws.send("pong")
                continue

            if not message or not message.strip():
                continue

            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                logger.debug(f"收到非 JSON 消息: {message[:200]}")
                continue

            await self._handle_message(data)

    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """处理单条业务消息。"""
        aid = data.get("aid")
        title = data.get("title", "")
        comefrom = data.get("comefrom", "")

        # 去重：跳过已处理过的 aid
        if aid:
            if aid in self._seen_ids:
                return
            self._seen_ids.add(str(aid))
            # 防止 seen_ids 无限膨胀
            if len(self._seen_ids) > 10000:
                self._seen_ids = set(list(self._seen_ids)[-5000:])

        # 控制消息
        if title == "refresh" and comefrom == "鼓掌网":
            return

        # 删除消息：需要删除对应 aid
        if title == "delete" and comefrom == "鼓掌网":
            aid_to_delete = str(data.get("content", "")).strip()
            if aid_to_delete:
                await self._remove_by_id(aid_to_delete)
                logger.info(f"删除快讯 aid={aid_to_delete}")
            return

        item = self._normalize(data)
        if item is None:
            return

        await self._append(item)
        self._received_count += 1
        if self._received_count % 20 == 0:
            logger.info(f"已累计接收 {self._received_count} 条鼓掌快讯")

    def _normalize(self, data: Dict[str, Any]) -> Optional[NewsItem]:
        """将鼓掌消息标准化为 NewsItem。"""
        aid = data.get("aid")
        title = data.get("title", "")
        content = data.get("content", "") or ""
        source = data.get("comefrom", "鼓掌财经")
        ptime = data.get("ptime")
        category_id = data.get("categoryId")

        if not aid:
            return None

        # 删除消息的内容字段是 aid，不当作正文
        if title == "delete":
            return None

        # 解析发布时间
        published_at = datetime.now()
        if ptime:
            try:
                published_at = datetime.strptime(str(ptime), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    published_at = datetime.fromtimestamp(int(float(ptime)))
                except (ValueError, TypeError):
                    pass

        sentiment, score = self._tag_sentiment(f"{title} {content}")
        related_stocks = self._extract_stock_codes(f"{title} {content}")
        related_sectors = self._extract_sectors(f"{title} {content}")
        impact_scope = self._infer_impact_scope(title, content, related_stocks, related_sectors)

        return NewsItem(
            id=str(aid),
            title=str(title),
            content=str(content) if content else None,
            source=str(source),
            published_at=published_at,
            sentiment=sentiment,
            sentiment_score=score,
            related_stocks=related_stocks,
            impact_scope=impact_scope,
            metadata={
                "category_id": category_id,
                "category_name": CATEGORY_NAMES.get(category_id, "其他") if isinstance(category_id, int) else "其他",
                "related_sectors": related_sectors,
            },
        )

    def _extract_stock_codes(self, text: str) -> List[str]:
        """从文本中提取股票代码（去重）。"""
        if not text:
            return []
        codes = STOCK_CODE_RE.findall(text)
        seen: Set[str] = set()
        result: List[str] = []
        for code in codes:
            if code not in seen:
                seen.add(code)
                result.append(code)
        return result

    def _extract_sectors(self, text: str) -> List[str]:
        """从文本中提取板块/概念关键词。"""
        if not text:
            return []
        text = text.replace("AI", "人工智能")
        return [kw for kw in SECTOR_KEYWORDS if kw in text]

    def _infer_impact_scope(
        self,
        title: str,
        content: str,
        related_stocks: List[str],
        related_sectors: List[str],
    ) -> str:
        """推断新闻影响范围：MARKET / SECTOR / STOCK。"""
        full_text = f"{title} {content}"
        market_keywords = {"大盘", "沪指", "深成指", "创业板", "A股", "股市", "市场", "指数"}
        if any(kw in full_text for kw in market_keywords):
            return "MARKET"
        if related_stocks:
            return "STOCK"
        if related_sectors:
            return "SECTOR"
        return "MARKET"

    def _tag_sentiment(self, text: str) -> tuple:
        """基于关键词规则进行情绪打标。"""
        text = text or ""
        has_bullish = any(kw in text for kw in BULLISH_KEYWORDS)
        has_bearish = any(kw in text for kw in BEARISH_KEYWORDS)

        if has_bullish and not has_bearish:
            return "BULLISH", 0.6
        if has_bearish and not has_bullish:
            return "BEARISH", -0.6
        if has_bullish and has_bearish:
            return "NEUTRAL", 0.0
        return "NEUTRAL", 0.0

    async def _append(self, item: NewsItem) -> None:
        """向缓冲区和所有订阅者追加消息。"""
        # 去重：若已存在相同 id，先删除旧记录
        existing_ids = {it.id for it in self._buffer}
        if item.id in existing_ids:
            self._buffer = deque([it for it in self._buffer if it.id != item.id], maxlen=500)

        self._buffer.append(item)

        dead_queues = []
        for q in self._subscribers:
            try:
                q.put_nowait(item)
            except asyncio.QueueFull:
                dead_queues.append(q)

        # 移除已满队列（订阅者消费过慢）
        for q in dead_queues:
            self._subscribers.discard(q)

    async def _remove_by_id(self, news_id: str) -> None:
        """从缓冲区中删除指定 id 的快讯。"""
        self._buffer = deque([it for it in self._buffer if it.id != news_id], maxlen=500)

    def get_recent(self, limit: int = 100) -> List[NewsItem]:
        """获取最近 N 条缓冲中的快讯（按时间从新到旧）。"""
        items = list(self._buffer)
        items.reverse()
        return items[:limit]

    async def subscribe(self) -> asyncio.Queue:
        """订阅实时快讯，返回一个 asyncio.Queue。"""
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        # 先把当前最新 50 条塞入队列，让新订阅者立即看到历史
        recent = self.get_recent(50)
        for item in recent:
            try:
                q.put_nowait(item)
            except asyncio.QueueFull:
                break
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """取消订阅。"""
        self._subscribers.discard(q)


# 全局单例
guzhang_client = GuzhangClient()

"""
AI Stock - 新闻 Ingest 服务

消费 guzhang_client 实时快讯 → 写入 DB → WebSocket 广播给前端。

使用方式：
    from app.services.news_ingest_service import news_ingest_service
    from app.services.guzhang_client import guzhang_client

    # 应用启动时
    await news_ingest_service.start()

    # 应用关闭时
    await news_ingest_service.stop()
"""
import asyncio
from typing import Awaitable, Callable, Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.news import NewsItem


class NewsIngestService:
    """
    新闻 ingest 服务。

    负责：
    1. 订阅 guzhang_client 的实时快讯；
    2. 写入数据库（如果提供了 db_session_factory）；
    3. 通过 WebSocket 广播函数推送给所有在线前端。
    """

    def __init__(
        self,
        guzhang_client,
        db_session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
        ws_broadcast_fn: Optional[Callable[[NewsItem], Awaitable[None]]] = None,
    ):
        self._gz = guzhang_client
        self._db_factory = db_session_factory
        self._broadcast = ws_broadcast_fn
        self._task: Optional[asyncio.Task] = None
        self._running: bool = False
        self._lock = asyncio.Lock()
        self._queue: Optional[asyncio.Queue] = None

    async def start(self) -> None:
        """启动 ingest 服务（幂等）。"""
        async with self._lock:
            if self._running:
                return
            self._running = True

        self._queue = await self._gz.subscribe()
        self._task = asyncio.create_task(self._run())
        logger.info("新闻 Ingest 服务已启动")

    async def stop(self) -> None:
        """优雅停止 ingest 服务。"""
        async with self._lock:
            if not self._running:
                return
            self._running = False

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("新闻 Ingest 服务已停止")

    async def _run(self) -> None:
        """核心循环：订阅新消息 → 写 DB → WebSocket 广播。"""
        logger.info("新闻 Ingest 核心循环启动")
        while True:
            try:
                item = await self._queue.get()
                if item is None:
                    break

                # 1. 写数据库（可选）
                if self._db_factory is not None:
                    await self._write_db(item)

                # 2. WebSocket 广播（可选）
                if self._broadcast is not None:
                    try:
                        await self._broadcast(item)
                    except Exception as e:
                        logger.warning(f"WebSocket 广播失败: {e}")

            except asyncio.CancelledError:
                logger.info("新闻 Ingest 核心循环已取消")
                break
            except Exception as e:
                logger.warning(f"新闻 Ingest 核心循环异常: {e}")

        logger.info("新闻 Ingest 核心循环已退出")

    async def _write_db(self, item: NewsItem) -> None:
        """将单条快讯写入数据库。"""
        if self._db_factory is None:
            return

        try:
            async with self._db_factory() as session:
                from app.models.stock import NewsRecord
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                stmt = pg_insert(NewsRecord).values(
                    id=item.id,
                    title=item.title,
                    content=item.content,
                    source=item.source,
                    url=item.url,
                    published_at=item.published_at,
                    sentiment=item.sentiment,
                    sentiment_score=item.sentiment_score,
                    is_buy_signal=item.is_buy_signal,
                    confidence=item.confidence,
                    related_stocks=item.related_stocks or [],
                    related_sectors=item.metadata.get("related_sectors", []) if item.metadata else [],
                    impact_scope=item.impact_scope,
                    impact_duration=item.impact_duration,
                    summary=item.summary,
                    extra_metadata=item.metadata,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "title": stmt.excluded.title,
                        "content": stmt.excluded.content,
                        "source": stmt.excluded.source,
                        "sentiment": stmt.excluded.sentiment,
                        "sentiment_score": stmt.excluded.sentiment_score,
                        "related_stocks": stmt.excluded.related_stocks,
                        "related_sectors": stmt.excluded.related_sectors,
                        "extra_metadata": stmt.excluded.extra_metadata,
                    },
                )
                await session.execute(stmt)
                await session.commit()
                logger.debug(f"DB 写入: {item.id} - {item.title[:20]}")
        except Exception as e:
            logger.warning(f"DB 写入失败: {e}")


# 全局单例（延迟初始化，start 时传入真实依赖）
news_ingest_service = NewsIngestService(
    guzhang_client=None,  # type: ignore
    db_session_factory=None,
    ws_broadcast_fn=None,
)

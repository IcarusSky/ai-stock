"""
AI Stock - 股票池同步服务

数据源：
- 行业板块：akshare stock_board_industry_name_ths（同花顺，90 个）
- 概念板块：akshare stock_board_concept_name_ths（同花顺，375 个）
- 全市场股票：akshare stock_zh_a_spot（新浪，5500+ 只）
- 板块成分股：暂不同步（同花顺/新浪公开接口均未提供成分股列表；东财 push2 在当前网络下 TLS 断连不可用）

同步策略：
- 全量同步：板块列表 + 全市场股票
- 板块成分后续通过其它渠道补齐
"""
import asyncio
from datetime import datetime
from typing import Any, Optional

import akshare as ak
import pandas as pd
from loguru import logger
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import async_session_maker
from app.models.stock import Sector, SectorMember, StockBasic


# akshare 在并发 thread 下不稳定（同花顺接口的 V8 初始化），用全局锁串行化
_AK_LOCK = asyncio.Lock()


async def _run_ak_sync(fn, *args, **kwargs):
    """
    在线程池中串行调用 akshare。

    为什么不能用 asyncio.gather 并发多个 akshare 调用：
    - akshare 同花顺接口依赖 py_mini_racer（V8 引擎）
    - 多个线程同时初始化 V8 会触发 partition_address_space 检查失败导致进程崩溃
    - 串行 to_thread 调用是安全的（已实测）
    """
    async with _AK_LOCK:
        return await asyncio.to_thread(fn, *args, **kwargs)


class StockPoolSyncService:
    """股票池同步服务（同花顺 + 新浪 -> PostgreSQL）"""

    def __init__(self):
        self._running = False
        self._progress: dict[str, Any] = {
            "status": "idle",
            "started_at": None,
            "finished_at": None,
            "steps": [],
            "error": None,
        }

    @property
    def is_running(self) -> bool:
        return self._running

    def get_progress(self) -> dict[str, Any]:
        return self._progress

    async def sync_all(self) -> dict[str, Any]:
        """全量同步：行业 + 概念 + 全市场股票"""
        self._running = True
        self._progress = {
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": None,
            "steps": [],
            "error": None,
        }

        try:
            await self._sync_sectors()
            await self._sync_stocks()
            await self._sync_sector_members_placeholder()

            self._progress["status"] = "done"
            self._progress["finished_at"] = datetime.utcnow().isoformat()
            logger.info("股票池全量同步完成")
        except Exception as e:
            self._progress["status"] = "failed"
            self._progress["error"] = str(e)
            logger.exception("股票池全量同步失败")
        finally:
            self._running = False

        return self._progress

    async def _sync_sectors(self):
        """同步同花顺行业/概念板块列表"""
        logger.info("开始同步板块列表（同花顺）...")
        step = {"step": "sectors", "count": 0, "message": ""}

        try:
            # 串行调用，避免 thread pool 并发初始化 V8 崩溃（见 _run_ak_sync docstring）
            industries = await _run_ak_sync(ak.stock_board_industry_name_ths)
            concepts = await _run_ak_sync(ak.stock_board_concept_name_ths)

            sectors = []
            now = datetime.utcnow()

            if industries is not None and not industries.empty:
                for _, row in industries.iterrows():
                    name = str(row.get("name", "")).strip()
                    code = str(row.get("code", "")).strip()
                    if not name:
                        continue
                    sectors.append({
                        "code": f"ind-{code}" if code else f"ind-{name}",
                        "name": name,
                        "type": "industry",
                        "source": "tonghuashun",
                        "updated_at": now,
                    })

            if concepts is not None and not concepts.empty:
                for _, row in concepts.iterrows():
                    name = str(row.get("name", "")).strip()
                    code = str(row.get("code", "")).strip()
                    if not name:
                        continue
                    sectors.append({
                        "code": f"cpt-{code}" if code else f"cpt-{name}",
                        "name": name,
                        "type": "concept",
                        "source": "tonghuashun",
                        "updated_at": now,
                    })

            if sectors:
                async with async_session_maker() as session:
                    await self._bulk_upsert_sectors(session, sectors)

            step["count"] = len(sectors)
            step["message"] = f"板块列表同步完成，共 {len(sectors)} 条"
            logger.info(step["message"])
        except Exception as e:
            step["message"] = f"板块列表同步失败: {e}"
            logger.warning(step["message"])
            step["count"] = 0

        self._progress["steps"].append(step)

    async def _bulk_upsert_sectors(self, session: AsyncSession, sectors: list[dict]):
        if not sectors:
            return
        stmt = pg_insert(Sector).values(sectors)
        update_dict = {
            "name": stmt.excluded.name,
            "type": stmt.excluded.type,
            "source": stmt.excluded.source,
            "updated_at": stmt.excluded.updated_at,
        }
        stmt = stmt.on_conflict_do_update(index_elements=["code"], set_=update_dict)
        await session.execute(stmt)
        await session.commit()

    async def _sync_stocks(self):
        """同步全市场股票（新浪数据源）"""
        logger.info("开始同步全市场股票（新浪）...")
        step = {"step": "stocks", "count": 0, "message": ""}

        try:
            df = await _run_ak_sync(ak.stock_zh_a_spot)
            if df is None or df.empty:
                raise ValueError("ak.stock_zh_a_spot 返回空数据")

            df = df.copy()
            df["code_str"] = df["代码"].astype(str).str.replace(r"^(sh|sz|bj)", "", regex=True)
            df["price_f"] = pd.to_numeric(df["最新价"], errors="coerce")

            rows = []
            now = datetime.utcnow()
            for _, row in df.iterrows():
                code = str(row.get("code_str", "")).strip()
                name = str(row.get("名称", "")).strip()
                if not code or not name:
                    continue

                rows.append({
                    "code": code,
                    "name": name,
                    "market": _infer_market(code),
                    "board": _infer_board(code),
                    "is_st": _is_st(name),
                    "is_suspended": False,
                    "total_share": None,
                    "float_share": None,
                    "updated_at": now,
                })

            if rows:
                async with async_session_maker() as session:
                    await self._bulk_upsert_stocks(session, rows)

            step["count"] = len(rows)
            step["message"] = f"全市场股票同步完成，共 {len(rows)} 条"
            logger.info(step["message"])
        except Exception as e:
            step["message"] = f"全市场股票同步失败: {e}"
            logger.warning(step["message"])
            step["count"] = 0

        self._progress["steps"].append(step)

    async def _bulk_upsert_stocks(self, session: AsyncSession, rows: list[dict]):
        if not rows:
            return
        # asyncpg 单条 SQL 参数上限 32767，按 9 列计算每批最多约 3600 行，安全取 1000
        batch_size = 1000
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            stmt = pg_insert(StockBasic).values(batch)
            update_dict = {
                "name": stmt.excluded.name,
                "market": stmt.excluded.market,
                "board": stmt.excluded.board,
                "is_st": stmt.excluded.is_st,
                "is_suspended": stmt.excluded.is_suspended,
                "total_share": stmt.excluded.total_share,
                "float_share": stmt.excluded.float_share,
                "updated_at": stmt.excluded.updated_at,
            }
            stmt = stmt.on_conflict_do_update(index_elements=["code"], set_=update_dict)
            await session.execute(stmt)
        await session.commit()

    async def _sync_sector_members_placeholder(self):
        """板块成分股：当前免费数据源（同花顺/新浪）未提供成分列表，
        东财 push2 在当前网络下 TLS 断连不可用。
        保留占位，待有可用数据源后补齐。
        """
        step = {
            "step": "members",
            "count": 0,
            "message": "板块成分股同步已跳过：当前数据源不提供成分列表（东财 push2 不可用）",
        }
        logger.warning(step["message"])
        self._progress["steps"].append(step)

    async def sync_stock_concepts(self, stock_code: str) -> list[dict]:
        """查询某只股票的概念板块列表"""
        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(Sector)
                    .join(SectorMember, SectorMember.sector_code == Sector.code)
                    .where(SectorMember.stock_code == stock_code, Sector.type == "concept")
                    .order_by(Sector.name)
                )
                sectors = result.scalars().all()
                return [
                    {"code": s.code, "name": s.name, "type": s.type}
                    for s in sectors
                ]
        except Exception as e:
            logger.warning(f"查询股票概念失败 {stock_code}: {e}")
            return []


# ---------- 辅助函数 ----------

def _infer_market(code: str) -> str:
    if code.startswith("6"):
        return "SH"
    if code.startswith("0") or code.startswith("3"):
        return "SZ"
    if code.startswith("8") or code.startswith("4") or code.startswith("920"):
        return "BJ"
    return "SZ"


def _infer_board(code: str) -> str:
    if code.startswith("60"):
        return "沪主板"
    if code.startswith("00"):
        return "深主板"
    if code.startswith("30"):
        return "创业板"
    if code.startswith("68"):
        return "科创板"
    if code.startswith("8") or code.startswith("4") or code.startswith("920"):
        return "北交所"
    return "其他"


def _is_st(name: str) -> bool:
    return "ST" in name or "退市" in name


def _to_float(value: Any) -> Optional[float]:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


# ---------- 单例 ----------

stock_pool_sync_service = StockPoolSyncService()

"""
AI Stock - 股票池同步服务

数据源：
- 行业板块：akshare stock_board_industry_name_ths（同花顺，90 个）+ stock_sector_spot（新浪，49 个，含成分股）
- 概念板块：akshare stock_board_concept_name_ths（同花顺，375 个）
- 全市场股票：akshare stock_zh_a_spot（新浪，5500+ 只）
- 板块成分股：akshare stock_sector_detail（新浪，49 个行业）

说明：
- 同花顺行业列表无成分股公开接口，因此额外引入新浪 49 个行业作为可筛选的行业维度
- 同花顺概念板块同样没有公开成分接口，本次同步仅保留列表
- 东财 push2 在当前网络下 TLS 断连不可用
"""
import asyncio
import re
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


from app.services.sector_sync_service import sector_sync_service


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
            await sector_sync_service.sync_all()

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
        """同步板块列表：同花顺行业 + 概念 + 新浪行业（用于成分股关联）"""
        logger.info("开始同步板块列表（同花顺 + 新浪）...")
        step = {"step": "sectors", "count": 0, "message": ""}

        try:
            # 串行调用，避免 thread pool 并发初始化 V8 崩溃（见 _run_ak_sync docstring）
            industries = await _run_ak_sync(ak.stock_board_industry_name_ths)
            concepts = await _run_ak_sync(ak.stock_board_concept_name_ths)
            sina_industries = await _run_ak_sync(ak.stock_sector_spot, indicator="新浪行业")

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

            if sina_industries is not None and not sina_industries.empty:
                for _, row in sina_industries.iterrows():
                    name = str(row.get("板块", "")).strip()
                    label = str(row.get("label", "")).strip()
                    if not name or not label:
                        continue
                    sectors.append({
                        "code": f"sina-{label}",
                        "name": name,
                        "type": "industry",
                        "source": "sina",
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
        """同步全市场股票（多数据源合并，确保覆盖沪深京全量 A 股）

        单一数据源覆盖不全的问题：
        - 新浪 stock_zh_a_spot 偶尔缺北交所/新上市股票
        - 东财 stock_zh_a_spot_em 在部分网络下 TLS 断连不可用
        因此按 新浪 -> 东财 -> 交易所代码表 的顺序合并去重，能取到几个用几个。
        """
        logger.info("开始同步全市场股票（多源合并）...")
        step = {"step": "stocks", "count": 0, "message": ""}

        try:
            merged = await self._fetch_all_a_shares()
            if not merged:
                raise ValueError("所有股票列表数据源均不可用")

            rows = []
            now = datetime.utcnow()
            for code, name in merged.items():
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

    async def _fetch_all_a_shares(self) -> dict[str, str]:
        """多数据源合并全市场 A 股 {code: name}，按 6 位代码去重"""
        merged: dict[str, str] = {}

        def _add(code: Any, name: Any):
            code = str(code or "").strip()
            name = str(name or "").strip()
            if not re.match(r"^\d{6}$", code) or not name:
                return
            if code not in merged:
                merged[code] = name

        # 数据源 1：新浪全市场快照（代码带 sh/sz/bj 前缀）
        try:
            df = await _run_ak_sync(ak.stock_zh_a_spot)
            if df is not None and not df.empty:
                codes = df["代码"].astype(str).str.replace(r"^(sh|sz|bj)", "", regex=True)
                for c, n in zip(codes, df["名称"].astype(str)):
                    _add(c, n)
                logger.info(f"新浪全市场快照获取 {len(df)} 条，合并后 {len(merged)} 条")
        except Exception as e:
            logger.warning(f"新浪全市场快照获取失败: {e}")

        # 数据源 2：东财全市场快照（部分网络不可用，失败可忽略）
        try:
            df_em = await _run_ak_sync(ak.stock_zh_a_spot_em)
            if df_em is not None and not df_em.empty:
                for c, n in zip(df_em["代码"].astype(str), df_em["名称"].astype(str)):
                    _add(c, n)
                logger.info(f"东财全市场快照获取 {len(df_em)} 条，合并后 {len(merged)} 条")
        except Exception as e:
            logger.warning(f"东财全市场快照获取失败（网络受限可忽略）: {e}")

        # 数据源 3：沪深京 A 股代码名称表（兜底补齐缺漏）
        try:
            df_info = await _run_ak_sync(ak.stock_info_a_code_name)
            if df_info is not None and not df_info.empty:
                for c, n in zip(df_info["code"].astype(str), df_info["name"].astype(str)):
                    _add(c, n)
                logger.info(f"交易所代码表获取 {len(df_info)} 条，合并后 {len(merged)} 条")
        except Exception as e:
            logger.warning(f"交易所代码表获取失败: {e}")

        return merged

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
        """同步板块成分股：仅同步新浪行业（49 个，ak.stock_sector_detail 可获取成分）。

        同花顺行业/概念板块暂无公开成分接口，跳过。
        """
        step = {"step": "members", "count": 0, "message": ""}
        logger.info("开始同步板块成分股（新浪行业）...")

        try:
            sina_industries = await _run_ak_sync(ak.stock_sector_spot, indicator="新浪行业")
            if sina_industries is None or sina_industries.empty:
                raise ValueError("ak.stock_sector_spot 返回空数据")

            total_members = 0
            async with async_session_maker() as session:
                # 预先拉取 stock_basic 中全部 code，用于过滤掉未入库的成分股
                result = await session.execute(select(StockBasic.code))
                valid_codes = {row[0] for row in result.all()}
                logger.info(f"stock_basic 共 {len(valid_codes)} 条，开始逐板块同步成分")

                for _, row in sina_industries.iterrows():
                    label = str(row.get("label", "")).strip()
                    name = str(row.get("板块", "")).strip()
                    if not label:
                        continue
                    sector_code = f"sina-{label}"

                    detail = None
                    last_err: Exception | None = None
                    for attempt in range(3):
                        try:
                            detail = await _run_ak_sync(ak.stock_sector_detail, sector=label)
                            last_err = None
                            break
                        except Exception as e:
                            last_err = e
                            await asyncio.sleep(2 * (attempt + 1))
                    if last_err is not None:
                        logger.warning(f"获取板块成分失败 {name}({label}): {last_err}")
                        continue

                    if detail is None or detail.empty:
                        continue

                    members = []
                    now = datetime.utcnow()
                    for _, drow in detail.iterrows():
                        code = str(drow.get("code", "")).strip().zfill(6)
                        if not code or code not in valid_codes:
                            continue
                        members.append({
                            "sector_code": sector_code,
                            "stock_code": code,
                            "weight": None,
                            "updated_at": now,
                        })

                    if members:
                        await self._bulk_upsert_sector_members(session, members)
                        total_members += len(members)
                        logger.debug(f"板块 {name}({sector_code}) 成分 {len(members)} 条")

            step["count"] = total_members
            step["message"] = f"板块成分股同步完成，共 {total_members} 条"
            logger.info(step["message"])
        except Exception as e:
            step["message"] = f"板块成分股同步失败: {e}"
            logger.warning(step["message"])
            step["count"] = 0

        self._progress["steps"].append(step)

    async def _bulk_upsert_sector_members(self, session: AsyncSession, rows: list[dict]):
        if not rows:
            return
        # 先清空该板块的旧成分，再批量插入，避免残留已调出的股票
        sector_code = rows[0]["sector_code"]
        await session.execute(
            text("DELETE FROM sector_member WHERE sector_code = :code"),
            {"code": sector_code},
        )
        stmt = pg_insert(SectorMember).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["sector_code", "stock_code"])
        await session.execute(stmt)
        await session.commit()

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

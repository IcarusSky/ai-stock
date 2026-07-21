"""
AI Stock - 股票池同步服务

通过 akshare 同步 A 股全市场基础信息、行业/概念/地域板块及其成分股。
所有 akshare 调用均通过 asyncio.to_thread 包装，避免阻塞事件循环。
"""
import asyncio
from datetime import datetime
from typing import Any, Optional

import akshare as ak
import pandas as pd
from loguru import logger
from sqlalchemy import func, insert, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import async_session_maker
from app.models.stock import Sector, SectorMember, StockBasic


class _SyncState:
    """内存同步状态（重启后重置）"""

    def __init__(self):
        self.running: bool = False
        self.last_sync_at: Optional[datetime] = None
        self.total_stocks: int = 0
        self.total_sectors: int = 0
        self.total_members: int = 0
        self.message: str = "未开始同步"


sync_state = _SyncState()


def _infer_market(code: str) -> str:
    """根据股票代码推断市场"""
    if code.startswith("6"):
        return "SH"
    if code.startswith("0") or code.startswith("3"):
        return "SZ"
    if code.startswith("8") or code.startswith("4") or code.startswith("920"):
        return "BJ"
    return "SZ"


def _infer_board(code: str) -> str:
    """根据股票代码推断板块类型"""
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
    """判断是否 ST/*ST/退市"""
    return "ST" in name or "退市" in name


def _to_int(value: Any) -> Optional[int]:
    """安全转换为整数"""
    if value is None or pd.isna(value):
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _to_float(value: Any) -> Optional[float]:
    """安全转换为浮点数"""
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


class StockSyncService:
    """股票池同步服务"""

    async def sync_all_stocks(self) -> dict:
        """全量同步 A 股基础信息（约 5000+ 只）"""
        logger.info("开始同步全市场 A 股基础信息...")
        sync_state.running = True
        sync_state.message = "正在同步股票基础信息"

        try:
            df = await asyncio.to_thread(ak.stock_zh_a_spot_em)
            if df is None or df.empty:
                raise ValueError("ak.stock_zh_a_spot_em 返回空数据")

            # 标准化列名
            df = df.rename(
                columns={
                    "代码": "code",
                    "名称": "name",
                    "最新价": "price",
                    "总市值": "total_market_cap",
                    "流通市值": "float_market_cap",
                }
            )

            rows = []
            for _, row in df.iterrows():
                code = str(row.get("code", "")).strip()
                name = str(row.get("name", "")).strip()
                if not code or not name:
                    continue

                market = _infer_market(code)
                board = _infer_board(code)
                price = _to_float(row.get("price"))
                total_market_cap = _to_float(row.get("total_market_cap"))
                float_market_cap = _to_float(row.get("float_market_cap"))

                # 由市值/价格反推股本（价格可能为 None，则股本留空）
                total_share = None
                float_share = None
                if price and price > 0:
                    if total_market_cap:
                        total_share = int(total_market_cap / price)
                    if float_market_cap:
                        float_share = int(float_market_cap / price)

                rows.append(
                    {
                        "code": code,
                        "name": name,
                        "market": market,
                        "board": board,
                        "is_st": _is_st(name),
                        "is_suspended": False,
                        "total_share": total_share,
                        "float_share": float_share,
                        "updated_at": datetime.utcnow(),
                    }
                )

            async with async_session_maker() as session:
                await self._bulk_upsert_stock_basic(session, rows)
                count_result = await session.execute(
                    select(func.count()).select_from(StockBasic)
                )
                total = count_result.scalar() or 0

            sync_state.last_sync_at = datetime.utcnow()
            sync_state.total_stocks = total
            sync_state.message = f"股票基础信息同步完成，共 {len(rows)} 条"
            logger.info(sync_state.message)
            return {"success": True, "count": len(rows), "total": total}
        except Exception as e:
            sync_state.message = f"股票基础信息同步失败: {e}"
            logger.exception(sync_state.message)
            return {"success": False, "error": str(e)}
        finally:
            sync_state.running = False

    async def _bulk_upsert_stock_basic(
        self, session: AsyncSession, rows: list[dict]
    ) -> None:
        """批量 upsert stock_basic"""
        if not rows:
            return
        stmt = pg_insert(StockBasic).values(rows)
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

    async def sync_sectors(self) -> dict:
        """同步行业/概念/地域板块列表"""
        logger.info("开始同步板块列表...")
        sync_state.running = True
        sync_state.message = "正在同步板块列表"

        try:
            industries = await asyncio.to_thread(ak.stock_board_industry_name_em)
            concepts = await asyncio.to_thread(ak.stock_board_concept_name_em)
            try:
                regions = await asyncio.to_thread(ak.stock_board_region_name_em)
            except Exception as e:
                logger.warning(f"地域板块同步不可用: {e}")
                regions = pd.DataFrame()

            sectors = []

            def _extract_board_code(row: pd.Series) -> str:
                # 优先使用板块代码字段，否则用名称生成唯一 code
                for key in ("板块代码", "代码", "code"):
                    val = row.get(key)
                    if pd.notna(val):
                        return str(val).strip()
                return ""

            # 行业板块
            if industries is not None and not industries.empty:
                for _, row in industries.iterrows():
                    name = str(row.get("板块名称", row.get("名称", ""))).strip()
                    if not name:
                        continue
                    board_code = _extract_board_code(row)
                    code = f"ind-{board_code}" if board_code else f"ind-{name}"
                    sectors.append(
                        {
                            "code": code,
                            "name": name,
                            "type": "industry",
                            "source": "eastmoney",
                            "updated_at": datetime.utcnow(),
                        }
                    )

            # 概念板块
            if concepts is not None and not concepts.empty:
                for _, row in concepts.iterrows():
                    name = str(row.get("板块名称", row.get("名称", ""))).strip()
                    if not name:
                        continue
                    board_code = _extract_board_code(row)
                    code = f"cpt-{board_code}" if board_code else f"cpt-{name}"
                    sectors.append(
                        {
                            "code": code,
                            "name": name,
                            "type": "concept",
                            "source": "eastmoney",
                            "updated_at": datetime.utcnow(),
                        }
                    )

            # 地域板块
            if regions is not None and not regions.empty:
                for _, row in regions.iterrows():
                    name = str(row.get("板块名称", row.get("名称", ""))).strip()
                    if not name:
                        continue
                    board_code = _extract_board_code(row)
                    code = f"reg-{board_code}" if board_code else f"reg-{name}"
                    sectors.append(
                        {
                            "code": code,
                            "name": name,
                            "type": "region",
                            "source": "eastmoney",
                            "updated_at": datetime.utcnow(),
                        }
                    )

            async with async_session_maker() as session:
                await self._bulk_upsert_sectors(session, sectors)
                count_result = await session.execute(
                    select(func.count()).select_from(Sector)
                )
                total = count_result.scalar() or 0

            sync_state.last_sync_at = datetime.utcnow()
            sync_state.total_sectors = total
            sync_state.message = f"板块列表同步完成，共 {len(sectors)} 条"
            logger.info(sync_state.message)
            return {"success": True, "count": len(sectors), "total": total}
        except Exception as e:
            sync_state.message = f"板块列表同步失败: {e}"
            logger.exception(sync_state.message)
            return {"success": False, "error": str(e)}
        finally:
            sync_state.running = False

    async def _bulk_upsert_sectors(
        self, session: AsyncSession, sectors: list[dict]
    ) -> None:
        """批量 upsert sector"""
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

    async def sync_sector_members(self, sector_name: str, sector_type: str) -> dict:
        """同步单个板块成分股"""
        try:
            if sector_type == "industry":
                df = await asyncio.to_thread(
                    ak.stock_board_industry_cons_em, symbol=sector_name
                )
            elif sector_type == "concept":
                df = await asyncio.to_thread(
                    ak.stock_board_concept_cons_em, symbol=sector_name
                )
            elif sector_type == "region":
                df = await asyncio.to_thread(
                    ak.stock_board_region_cons_em, symbol=sector_name
                )
            else:
                return {"success": False, "error": f"未知板块类型: {sector_type}"}

            if df is None or df.empty:
                return {"success": True, "count": 0}

            # 标准化列名
            df = df.rename(
                columns={
                    "代码": "code",
                    "名称": "name",
                    "权重": "weight",
                }
            )

            sector_code = None
            async with async_session_maker() as session:
                result = await session.execute(
                    select(Sector.code).where(
                        Sector.name == sector_name, Sector.type == sector_type
                    )
                )
                sector_code = result.scalar()
                if not sector_code:
                    return {"success": False, "error": f"板块不存在: {sector_name}"}

                members = []
                for _, row in df.iterrows():
                    code = str(row.get("code", "")).strip()
                    if not code:
                        continue
                    weight = _to_float(row.get("weight"))
                    members.append(
                        {
                            "sector_code": sector_code,
                            "stock_code": code,
                            "weight": weight,
                            "updated_at": datetime.utcnow(),
                        }
                    )

                # 先清空旧成分
                await session.execute(
                    text(
                        "DELETE FROM sector_member WHERE sector_code = :sector_code"
                    ).bindparams(sector_code=sector_code)
                )

                if members:
                    stmt = pg_insert(SectorMember).values(members)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["sector_code", "stock_code"],
                        set_={"weight": stmt.excluded.weight, "updated_at": stmt.excluded.updated_at},
                    )
                    await session.execute(stmt)
                await session.commit()

            return {"success": True, "count": len(members)}
        except Exception as e:
            logger.warning(f"同步板块成分失败 [{sector_type}] {sector_name}: {e}")
            return {"success": False, "error": str(e)}

    async def sync_all_sector_members(self, max_concurrent: int = 1) -> dict:
        """全量同步所有板块成分股，串行 + 0.3s 限速，失败重试 3 次"""
        logger.info("开始同步全部板块成分股...")
        sync_state.running = True
        sync_state.message = "正在同步板块成分股"

        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(Sector.code, Sector.name, Sector.type).order_by(Sector.code)
                )
                sectors = result.all()

            total = len(sectors)
            success_count = 0
            fail_count = 0
            total_members = 0

            for idx, (code, name, sector_type) in enumerate(sectors):
                for attempt in range(3):
                    res = await self.sync_sector_members(name, sector_type)
                    if res.get("success"):
                        success_count += 1
                        total_members += res.get("count", 0)
                        break
                    else:
                        wait = 2 ** attempt
                        logger.warning(
                            f"板块成分同步重试 [{name}] 第 {attempt + 1} 次，等待 {wait}s"
                        )
                        await asyncio.sleep(wait)
                else:
                    fail_count += 1
                    logger.error(f"板块成分同步最终失败: {name}")

                if (idx + 1) % 50 == 0 or idx == total - 1:
                    logger.info(
                        f"板块成分同步进度: {idx + 1}/{total}，成功 {success_count}，失败 {fail_count}"
                    )

                await asyncio.sleep(0.3)

            async with async_session_maker() as session:
                count_result = await session.execute(
                    select(func.count()).select_from(SectorMember)
                )
                total_member_rows = count_result.scalar() or 0

            sync_state.last_sync_at = datetime.utcnow()
            sync_state.total_members = total_member_rows
            sync_state.message = (
                f"板块成分同步完成：{success_count} 成功，{fail_count} 失败，"
                f"共 {total_member_rows} 条成分记录"
            )
            logger.info(sync_state.message)
            return {
                "success": True,
                "total": total,
                "success_count": success_count,
                "fail_count": fail_count,
                "total_members": total_member_rows,
            }
        except Exception as e:
            sync_state.message = f"板块成分同步失败: {e}"
            logger.exception(sync_state.message)
            return {"success": False, "error": str(e)}
        finally:
            sync_state.running = False

    async def sync_daily(self) -> dict:
        """每日增量：基础信息 + ST/停牌状态"""
        logger.info("开始每日股票信息同步...")
        return await self.sync_all_stocks()

    async def sync_all(self) -> dict:
        """全量同步：股票 + 板块 + 成分"""
        logger.info("开始全量同步股票池数据...")
        results = {"stocks": {}, "sectors": {}, "members": {}}
        results["stocks"] = await self.sync_all_stocks()
        if not results["stocks"].get("success"):
            return results

        results["sectors"] = await self.sync_sectors()
        if not results["sectors"].get("success"):
            return results

        results["members"] = await self.sync_all_sector_members()
        return results

    def get_status(self) -> dict:
        """获取当前同步状态"""
        return {
            "running": sync_state.running,
            "last_sync_at": sync_state.last_sync_at,
            "total_stocks": sync_state.total_stocks,
            "total_sectors": sync_state.total_sectors,
            "total_members": sync_state.total_members,
            "message": sync_state.message,
        }


stock_sync_service = StockSyncService()


async def ensure_stock_basic_synced() -> None:
    """启动时若 stock_basic 为空，后台自动同步基础信息"""
    try:
        async with async_session_maker() as session:
            count_result = await session.execute(
                select(func.count()).select_from(StockBasic)
            )
            count = count_result.scalar() or 0
            if count == 0:
                logger.info("stock_basic 为空，后台自动同步 A 股基础信息...")
                asyncio.create_task(stock_sync_service.sync_all_stocks())
    except Exception as e:
        logger.warning(f"启动自动同步检查失败: {e}")

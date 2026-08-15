"""
AI Stock - 板块成分同步服务（同花顺行业/概念）

背景：
- 股票池同步服务只同步了新浪 49 个行业的成分股
- 同花顺行业（90 个）和概念（375+ 个）板块缺少成分关联
- akshare >= 1.18 移除了 stock_board_*_cons_ths 接口
- 本服务直接抓取同花顺板块成分分页接口（q.10jqka.com.cn ajax），
  复用 akshare 内置的 hexin-v 令牌算法（py_mini_racer + ths.js）

说明：
- py_mini_racer（V8）多线程并发初始化会崩溃，所有抓取串行进行
- 同花顺有限流/反爬，逐板块串行 + 间隔 sleep，失败仅告警跳过
"""
import asyncio
from datetime import datetime
from io import StringIO
from typing import Any, Optional

import pandas as pd
import requests
from loguru import logger
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import async_session_maker
from app.models.stock import Sector, SectorMember, StockBasic

# 每个板块请求间隔，避免触发同花顺限流
_REQUEST_INTERVAL = 0.8

_THS_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36"
)

# 同花顺板块成分 ajax 分页地址（行业 / 概念）
_THS_CONS_URL = {
    "industry": "https://q.10jqka.com.cn/thshy/detail/field/199112/order/desc/page/{page}/ajax/1/code/{code}",
    "concept": "https://q.10jqka.com.cn/gn/detail/field/264648/order/desc/page/{page}/ajax/1/code/{code}",
}

# 单板块最多翻页数（每页通常数十条，50 页足够覆盖最大概念板块）
_MAX_PAGES = 50


def _ths_v_token() -> str:
    """用 akshare 内置 ths.js 计算 hexin-v 反爬令牌"""
    from py_mini_racer import py_mini_racer
    from akshare.datasets import get_ths_js

    js = py_mini_racer.MiniRacer()
    with open(get_ths_js("ths.js"), encoding="utf-8") as f:
        js.eval(f.read())
    return js.call("v")


def _fetch_ths_cons(sector_type: str, sector_code: str) -> pd.DataFrame:
    """抓取同花顺板块成分（分页直到无更多数据），返回含 代码/名称 列的 DataFrame"""
    url_tpl = _THS_CONS_URL[sector_type]
    frames = []
    page_size = None

    for page in range(1, _MAX_PAGES + 1):
        headers = {"User-Agent": _THS_UA, "Cookie": f"v={_ths_v_token()}"}
        r = requests.get(
            url_tpl.format(page=page, code=sector_code),
            headers=headers,
            timeout=15,
        )
        r.raise_for_status()
        try:
            df = pd.read_html(StringIO(r.text))[0]
        except ValueError:
            # 无表格 = 已到末页或被限流
            break
        if df is None or df.empty or "代码" not in df.columns:
            break
        frames.append(df)
        if page_size is None:
            page_size = len(df)
        if len(df) < page_size:
            # 不足一页 = 末页
            break

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


class SectorSyncService:
    """同花顺行业/概念板块成分股同步"""

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
        """同步全部同花顺行业 + 概念板块的成分股"""
        if self._running:
            return self._progress

        self._running = True
        self._progress = {
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": None,
            "steps": [],
            "error": None,
        }

        try:
            await self._sync_sector_members(sector_type="industry")
            await self._sync_sector_members(sector_type="concept")
            self._progress["status"] = "done"
            logger.info("同花顺板块成分同步完成")
        except Exception as e:
            self._progress["status"] = "failed"
            self._progress["error"] = str(e)
            logger.exception("同花顺板块成分同步失败")
        finally:
            self._progress["finished_at"] = datetime.utcnow().isoformat()
            self._running = False

        return self._progress

    async def _sync_sector_members(self, sector_type: str):
        """按板块类型同步成分股"""
        step = {"step": f"ths_{sector_type}_members", "count": 0, "message": ""}
        logger.info(f"开始同步同花顺{sector_type}板块成分...")

        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(Sector).where(
                        Sector.type == sector_type,
                        Sector.source == "tonghuashun",
                    )
                )
                sectors = result.scalars().all()

                result = await session.execute(select(StockBasic.code))
                valid_codes = {row[0] for row in result.all()}

                if not sectors:
                    step["message"] = "无同花顺板块记录，跳过（请先运行股票池全量同步）"
                    self._progress["steps"].append(step)
                    return

                total_members = 0
                failed_sectors = 0
                for sector in sectors:
                    # Sector.code 形如 ind-881121 / cpt-301558，抓取时需要纯数字代码
                    raw_code = sector.code.split("-", 1)[-1]
                    if not raw_code.isdigit():
                        continue

                    try:
                        detail = await asyncio.to_thread(
                            _fetch_ths_cons, sector_type, raw_code
                        )
                    except Exception as e:
                        failed_sectors += 1
                        logger.warning(f"获取板块成分失败 {sector.name}({raw_code}): {e}")
                        await asyncio.sleep(_REQUEST_INTERVAL)
                        continue

                    await asyncio.sleep(_REQUEST_INTERVAL)

                    if detail is None or detail.empty:
                        continue

                    members = []
                    now = datetime.utcnow()
                    for _, drow in detail.iterrows():
                        code = str(drow.get("代码", "") or "").strip().zfill(6)
                        if not code or code not in valid_codes:
                            continue
                        members.append({
                            "sector_code": sector.code,
                            "stock_code": code,
                            "weight": None,
                            "updated_at": now,
                        })

                    if members:
                        await self._replace_members(session, sector.code, members)
                        total_members += len(members)
                        logger.debug(f"板块 {sector.name}({sector.code}) 成分 {len(members)} 条")

                step["count"] = total_members
                step["message"] = (
                    f"同花顺{sector_type}板块成分同步完成，共 {total_members} 条"
                    + (f"，{failed_sectors} 个板块抓取失败" if failed_sectors else "")
                )
                logger.info(step["message"])
        except Exception as e:
            step["message"] = f"同花顺{sector_type}板块成分同步失败: {e}"
            logger.warning(step["message"])

        self._progress["steps"].append(step)

    async def _replace_members(self, session: AsyncSession, sector_code: str, rows: list[dict]):
        """先清空该板块旧成分再批量插入，避免残留已调出股票"""
        if not rows:
            return
        await session.execute(
            text("DELETE FROM sector_member WHERE sector_code = :code"),
            {"code": sector_code},
        )
        # asyncpg 单条 SQL 参数上限 32767，按 4 列计算分批插入
        batch_size = 1000
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            stmt = pg_insert(SectorMember).values(batch)
            stmt = stmt.on_conflict_do_nothing(index_elements=["sector_code", "stock_code"])
            await session.execute(stmt)
        await session.commit()


# ---------- 单例 ----------

sector_sync_service = SectorSyncService()

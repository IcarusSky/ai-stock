"""
AI Stock - 板块与全市场股票 API
"""
import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.stock import Sector, SectorMember, StockBasic, StockPool, StockPoolItem
from app.schemas.stock import (
    SectorOut,
    SectorStockOut,
    SectorTreeOut,
    StockBasicOut,
    StockListOut,
    SyncStatusOut,
    SyncTrigger,
)
from app.services.stock_sync_service import stock_sync_service

router = APIRouter(prefix="/sector", tags=["板块"])


async def _get_sector_member_count(session: AsyncSession, sector_code: str) -> int:
    result = await session.execute(
        select(func.count()).where(SectorMember.sector_code == sector_code)
    )
    return result.scalar() or 0


@router.get("/tree", response_model=SectorTreeOut)
async def get_sector_tree(session: AsyncSession = Depends(get_db)):
    """获取按类型分组的板块树"""
    result = await session.execute(select(Sector).order_by(Sector.type, Sector.name))
    sectors = result.scalars().all()

    tree: dict[str, list[dict[str, Any]]] = {"industry": [], "concept": [], "region": []}
    for sector in sectors:
        member_count = await _get_sector_member_count(session, sector.code)
        data = SectorOut.model_validate(sector).model_dump()
        data["member_count"] = member_count
        tree.setdefault(sector.type, []).append(data)

    # 确保三个 key 都存在
    for key in ("industry", "concept", "region"):
        tree.setdefault(key, [])

    return tree


@router.get("/{code}/stocks", response_model=list[SectorStockOut])
async def get_sector_stocks(code: str, session: AsyncSession = Depends(get_db)):
    """获取板块成分股"""
    sector = await session.get(Sector, code)
    if not sector:
        raise HTTPException(status_code=404, detail="板块不存在")

    result = await session.execute(
        select(StockBasic, SectorMember.weight)
        .join(SectorMember, SectorMember.stock_code == StockBasic.code)
        .where(SectorMember.sector_code == code)
        .order_by(StockBasic.code)
    )
    rows = result.all()

    items = []
    for stock, weight in rows:
        data = StockBasicOut.model_validate(stock).model_dump()
        data["weight"] = float(weight) if weight is not None else None
        items.append(SectorStockOut(**data))
    return items


@router.post("/{code}/create-pool", response_model=dict)
async def create_pool_from_sector(
    code: str, pool_name: Optional[str] = None, session: AsyncSession = Depends(get_db)
):
    """将板块成分股一键转存为用户股票池"""
    sector = await session.get(Sector, code)
    if not sector:
        raise HTTPException(status_code=404, detail="板块不存在")

    name = pool_name or f"{sector.name}"
    # 检查重名
    existing = await session.execute(select(StockPool).where(StockPool.name == name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"股票池 {name} 已存在")

    pool = StockPool(
        name=name,
        description=f"由板块 {sector.name}({sector.type}) 一键创建",
        type="sector",
    )
    session.add(pool)
    await session.flush()

    result = await session.execute(
        select(SectorMember.stock_code).where(SectorMember.sector_code == code)
    )
    codes = [r[0] for r in result.all()]

    for stock_code in codes:
        session.add(StockPoolItem(pool_id=pool.id, stock_code=stock_code))

    await session.commit()
    return {"success": True, "pool_id": pool.id, "name": name, "count": len(codes)}


# ---------- 全市场股票浏览 ----------

stock_router = APIRouter(prefix="/stock", tags=["股票"])


@stock_router.get("/list", response_model=StockListOut)
async def list_stocks(
    market: Optional[str] = Query(None, description="市场 SH/SZ/BJ"),
    board: Optional[str] = Query(None, description="板块类型"),
    keyword: Optional[str] = Query(None, description="代码/名称关键字"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
):
    """全市场股票分页列表"""
    stmt = select(StockBasic)
    count_stmt = select(func.count()).select_from(StockBasic)

    filters = []
    if market:
        filters.append(StockBasic.market == market.upper())
    if board:
        filters.append(StockBasic.board == board)
    if keyword:
        like = f"%{keyword}%"
        filters.append(
            (StockBasic.code.ilike(like)) | (StockBasic.name.ilike(like))
        )

    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    total_result = await session.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(StockBasic.code).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    items = [StockBasicOut.model_validate(row) for row in result.scalars().all()]

    return {"total": total, "page": page, "page_size": page_size, "items": items}


@stock_router.get("/{code}/sectors", response_model=list[SectorOut])
async def get_stock_sectors(code: str, session: AsyncSession = Depends(get_db)):
    """反查股票所属板块"""
    stock = await session.get(StockBasic, code)
    if not stock:
        raise HTTPException(status_code=404, detail="股票不存在")

    result = await session.execute(
        select(Sector)
        .join(SectorMember, SectorMember.sector_code == Sector.code)
        .where(SectorMember.stock_code == code)
        .order_by(Sector.type, Sector.name)
    )
    return [SectorOut.model_validate(row) for row in result.scalars().all()]


# ---------- 同步管理 ----------

sync_router = APIRouter(prefix="/stock-pool/sync", tags=["同步管理"])


@sync_router.post("/trigger")
async def trigger_sync(payload: SyncTrigger):
    """触发同步任务"""
    if stock_sync_service.get_status()["running"]:
        return {"success": False, "message": "已有同步任务在运行"}

    scope = payload.scope
    if scope == "stocks":
        asyncio.create_task(stock_sync_service.sync_all_stocks())
    elif scope == "sectors":
        asyncio.create_task(stock_sync_service.sync_sectors())
    elif scope == "members":
        asyncio.create_task(stock_sync_service.sync_all_sector_members())
    elif scope == "all":
        asyncio.create_task(stock_sync_service.sync_all())
    else:
        raise HTTPException(status_code=400, detail="scope 必须是 stocks|sectors|members|all")

    return {"success": True, "scope": scope, "message": "同步任务已启动"}


@sync_router.get("/status", response_model=SyncStatusOut)
async def get_sync_status():
    """获取同步状态"""
    return SyncStatusOut(**stock_sync_service.get_status())

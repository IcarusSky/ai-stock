"""
AI Stock - 股票池 API（自定义股票池管理 + 行业/概念板块查询）
"""
import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import get_db
from app.models.stock import (
    Sector,
    SectorMember,
    StockBasic,
    StockPool,
    StockPoolItem,
)
from app.schemas.stock import (
    StockBasicOut,
    StockPoolCreate,
    StockPoolOut,
    StockPoolItemOut,
    StockPoolUpdate,
    StockPoolAddRemove,
    SectorOut,
)
from app.services.stock_pool_sync_service import stock_pool_sync_service

router = APIRouter(prefix="/stock-pool", tags=["股票池"])


# ========== Pydantic models ==========

class StockPoolItemAdd(BaseModel):
    """向池内添加股票"""

    stock_code: str = Field(..., description="股票代码")
    added_reason: Optional[str] = Field(None, description="添加原因")
    tags: Optional[str] = Field(None, description="标签，逗号分隔")


class IndustryNode(BaseModel):
    """行业树节点"""

    code: str
    name: str
    type: str = "industry"
    member_count: int = 0
    children: list["IndustryNode"] = []


class StockListItem(BaseModel):
    """股票列表项（支持行业/概念筛选）"""

    code: str
    name: str
    market: str
    board: str
    is_st: bool = False
    is_suspended: bool = False
    weight: Optional[float] = None

    class Config:
        from_attributes = True


class SyncProgressOut(BaseModel):
    """同步进度输出"""

    status: str = "idle"
    started_at: Optional[Any] = None
    finished_at: Optional[Any] = None
    steps: list[dict] = []
    error: Optional[str] = None


class StockSectorsOut(BaseModel):
    """股票所属板块输出"""

    code: str
    name: str
    industries: list[str]
    concepts: list[str]


# ========== 行业/概念板块查询 ==========

@router.get("/industries", response_model=list[IndustryNode])
async def get_industries(session: AsyncSession = Depends(get_db)):
    """行业分类列表（一级），含成分股数量"""
    result = await session.execute(
        select(Sector, func.count(SectorMember.stock_code).label("cnt"))
        .outerjoin(SectorMember, SectorMember.sector_code == Sector.code)
        .where(Sector.type == "industry")
        .group_by(Sector.code)
        .order_by(Sector.name)
    )
    rows = result.all()
    return [
        IndustryNode(
            code=sec.code,
            name=sec.name,
            type="industry",
            member_count=cnt or 0,
            children=[],
        )
        for sec, cnt in rows
    ]


@router.get("/concepts", response_model=list[SectorOut])
async def get_concepts(
    keyword: Optional[str] = Query(None, description="名称关键字"),
    limit: int = Query(50, le=200, description="返回数量"),
    session: AsyncSession = Depends(get_db),
):
    """概念板块列表，支持搜索"""
    stmt = select(Sector, func.count(SectorMember.stock_code).label("cnt")).outerjoin(
        SectorMember, SectorMember.sector_code == Sector.code
    ).where(Sector.type == "concept")

    if keyword:
        stmt = stmt.where(Sector.name.ilike(f"%{keyword}%"))

    stmt = stmt.group_by(Sector.code).order_by(Sector.name).limit(limit)

    result = await session.execute(stmt)
    rows = result.all()
    return [
        SectorOut(
            code=sec.code,
            name=sec.name,
            type=sec.type,
            source=sec.source,
            parent_code=sec.parent_code,
            updated_at=sec.updated_at,
            member_count=cnt or 0,
        )
        for sec, cnt in rows
    ]


# ========== 股票列表（按池/行业/概念筛选） ==========

@router.get("/list", response_model=dict)
async def list_stocks(
    pool_id: Optional[int] = Query(None, description="股票池ID"),
    industry_code: Optional[str] = Query(None, description="行业板块代码"),
    concept_code: Optional[str] = Query(None, description="概念板块代码"),
    keyword: Optional[str] = Query(None, description="代码/名称关键字"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    session: AsyncSession = Depends(get_db),
):
    """股票列表，支持按池/行业/概念筛选（优先级：pool_id > industry_code > concept_code）"""
    count = 0
    items: list[StockBasicOut] = []

    # 按股票池筛选
    if pool_id is not None:
        pool = await session.get(StockPool, pool_id, options=[selectinload(StockPool.items)])
        if not pool:
            raise HTTPException(status_code=404, detail="股票池不存在")

        # 分页
        codes_in_pool = [item.stock_code for item in pool.items]
        total = len(codes_in_pool)
        paginated = codes_in_pool[(page - 1) * page_size : page * page_size]

        if paginated:
            stmt = select(StockBasic).where(StockBasic.code.in_(paginated))
            if keyword:
                like = f"%{keyword}%"
                stmt = stmt.where(
                    (StockBasic.code.ilike(like)) | (StockBasic.name.ilike(like))
                )
            result = await session.execute(stmt.order_by(StockBasic.code))
            items = [StockBasicOut.model_validate(row) for row in result.scalars().all()]
        else:
            items = []

        return {"total": total, "page": page, "page_size": page_size, "items": items}

    # 按行业筛选
    if industry_code and industry_code != "all":
        sector = await session.get(Sector, industry_code)
        if not sector:
            raise HTTPException(status_code=404, detail="行业板块不存在")

        stmt = (
            select(StockBasic, SectorMember.weight)
            .join(SectorMember, SectorMember.stock_code == StockBasic.code)
            .where(SectorMember.sector_code == industry_code)
        )
        count_stmt = select(func.count()).select_from(SectorMember).where(
            SectorMember.sector_code == industry_code
        )

        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(
                (StockBasic.code.ilike(like)) | (StockBasic.name.ilike(like))
            )
            count_stmt = count_stmt.join(
                StockBasic, StockBasic.code == SectorMember.stock_code
            ).where(
                (StockBasic.code.ilike(like)) | (StockBasic.name.ilike(like))
            )

        count_result = await session.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = stmt.order_by(StockBasic.code).offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        items = []
        for stock, weight in result.all():
            data = StockBasicOut.model_validate(stock).model_dump()
            data["weight"] = float(weight) if weight is not None else None
            items.append(StockBasicOut(**data))

        return {"total": total, "page": page, "page_size": page_size, "items": items}

    # 按概念筛选
    if concept_code and concept_code != "all":
        sector = await session.get(Sector, concept_code)
        if not sector:
            raise HTTPException(status_code=404, detail="概念板块不存在")

        stmt = (
            select(StockBasic, SectorMember.weight)
            .join(SectorMember, SectorMember.stock_code == StockBasic.code)
            .where(SectorMember.sector_code == concept_code)
        )
        count_stmt = select(func.count()).select_from(SectorMember).where(
            SectorMember.sector_code == concept_code
        )

        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(
                (StockBasic.code.ilike(like)) | (StockBasic.name.ilike(like))
            )
            count_stmt = count_stmt.join(
                StockBasic, StockBasic.code == SectorMember.stock_code
            ).where(
                (StockBasic.code.ilike(like)) | (StockBasic.name.ilike(like))
            )

        count_result = await session.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = stmt.order_by(StockBasic.code).offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        items = []
        for stock, weight in result.all():
            data = StockBasicOut.model_validate(stock).model_dump()
            data["weight"] = float(weight) if weight is not None else None
            items.append(StockBasicOut(**data))

        return {"total": total, "page": page, "page_size": page_size, "items": items}

    # 无筛选条件时返回全市场
    stmt = select(StockBasic)
    count_stmt = select(func.count()).select_from(StockBasic)

    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            (StockBasic.code.ilike(like)) | (StockBasic.name.ilike(like))
        )
        count_stmt = count_stmt.where(
            (StockBasic.code.ilike(like)) | (StockBasic.name.ilike(like))
        )

    count_result = await session.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = stmt.order_by(StockBasic.code).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    rows = result.scalars().all()

    # 批量获取当前页股票的行业/概念
    stock_codes = [r.code for r in rows]
    sector_map = {}
    if stock_codes:
        sector_result = await session.execute(
            select(SectorMember.stock_code, Sector.name, Sector.type)
            .join(Sector, Sector.code == SectorMember.sector_code)
            .where(SectorMember.stock_code.in_(stock_codes))
            .order_by(Sector.type, Sector.name)
        )
        for scode, sname, stype in sector_result.all():
            sector_map.setdefault(scode, {"industries": [], "concepts": []})
            if stype == "industry":
                sector_map[scode]["industries"].append(sname)
            elif stype == "concept":
                sector_map[scode]["concepts"].append(sname)

    items = []
    for row in rows:
        data = StockBasicOut.model_validate(row).model_dump()
        data.update(sector_map.get(row.code, {"industries": [], "concepts": []}))
        items.append(StockBasicOut(**data))

    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/stock/{code}/sectors", response_model=StockSectorsOut)
async def get_stock_sectors(code: str, session: AsyncSession = Depends(get_db)):
    """获取股票所属的行业/概念板块列表"""
    stock = await session.get(StockBasic, code)
    if not stock:
        raise HTTPException(status_code=404, detail="股票不存在")

    result = await session.execute(
        select(Sector)
        .join(SectorMember, SectorMember.sector_code == Sector.code)
        .where(SectorMember.stock_code == code)
        .order_by(Sector.type, Sector.name)
    )
    sectors = result.scalars().all()

    industries = [s.name for s in sectors if s.type == "industry"]
    concepts = [s.name for s in sectors if s.type == "concept"]

    return StockSectorsOut(
        code=stock.code,
        name=stock.name,
        industries=industries,
        concepts=concepts,
    )


# ========== 自定义股票池 CRUD ==========

@router.get("/", response_model=list[StockPoolOut])
async def list_pools(
    keyword: Optional[str] = Query(None, description="池名称关键字"),
    session: AsyncSession = Depends(get_db),
):
    """股票池列表"""
    stmt = (
        select(StockPool, func.count(StockPoolItem.stock_code).label("cnt"))
        .outerjoin(StockPoolItem, StockPoolItem.pool_id == StockPool.id)
        .group_by(StockPool.id)
        .order_by(StockPool.updated_at.desc())
    )

    if keyword:
        stmt = stmt.where(StockPool.name.ilike(f"%{keyword}%"))

    result = await session.execute(stmt)
    rows = result.all()
    return [
        StockPoolOut(
            id=pool.id,
            name=pool.name,
            description=pool.description,
            type=pool.type,
            filter_rule=pool.filter_rule,
            created_at=pool.created_at,
            updated_at=pool.updated_at,
            stock_count=cnt or 0,
        )
        for pool, cnt in rows
    ]


@router.get("/{pool_id}", response_model=StockPoolOut)
async def get_pool(pool_id: int, session: AsyncSession = Depends(get_db)):
    """获取股票池详情"""
    result = await session.execute(
        select(StockPool, func.count(StockPoolItem.stock_code).label("cnt"))
        .outerjoin(StockPoolItem, StockPoolItem.pool_id == StockPool.id)
        .where(StockPool.id == pool_id)
        .group_by(StockPool.id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="股票池不存在")
    pool, cnt = row
    return StockPoolOut(
        id=pool.id,
        name=pool.name,
        description=pool.description,
        type=pool.type,
        filter_rule=pool.filter_rule,
        created_at=pool.created_at,
        updated_at=pool.updated_at,
        stock_count=cnt or 0,
    )


@router.post("/create", response_model=StockPoolOut)
async def create_pool(body: StockPoolCreate, session: AsyncSession = Depends(get_db)):
    """创建自定义股票池"""
    existing = await session.execute(
        select(StockPool).where(StockPool.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"股票池 {body.name} 已存在")

    pool = StockPool(
        name=body.name,
        description=body.description,
        type=body.type,
        filter_rule=body.filter_rule,
    )
    session.add(pool)
    await session.commit()
    await session.refresh(pool)

    return StockPoolOut(
        id=pool.id,
        name=pool.name,
        description=pool.description,
        type=pool.type,
        filter_rule=pool.filter_rule,
        created_at=pool.created_at,
        updated_at=pool.updated_at,
        stock_count=0,
    )


@router.patch("/{pool_id}", response_model=StockPoolOut)
async def update_pool(
    pool_id: int, body: StockPoolUpdate, session: AsyncSession = Depends(get_db)
):
    """更新股票池"""
    pool = await session.get(StockPool, pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="股票池不存在")

    if body.name is not None:
        existing = await session.execute(
            select(StockPool).where(StockPool.name == body.name, StockPool.id != pool_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"股票池 {body.name} 已存在")
        pool.name = body.name

    if body.description is not None:
        pool.description = body.description
    if body.type is not None:
        pool.type = body.type
    if body.filter_rule is not None:
        pool.filter_rule = body.filter_rule

    await session.commit()
    await session.refresh(pool)

    # 获取股票数量
    count_result = await session.execute(
        select(func.count()).select_from(StockPoolItem).where(StockPoolItem.pool_id == pool_id)
    )
    stock_count = count_result.scalar() or 0

    return StockPoolOut(
        id=pool.id,
        name=pool.name,
        description=pool.description,
        type=pool.type,
        filter_rule=pool.filter_rule,
        created_at=pool.created_at,
        updated_at=pool.updated_at,
        stock_count=stock_count,
    )


@router.delete("/{pool_id}")
async def delete_pool(pool_id: int, session: AsyncSession = Depends(get_db)):
    """删除股票池（级联删除成分）"""
    pool = await session.get(StockPool, pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="股票池不存在")

    await session.delete(pool)
    await session.commit()
    return {"success": True, "message": f"股票池 {pool_id} 已删除"}


# ========== 股票池成分管理 ==========

@router.get("/{pool_id}/items", response_model=list[StockPoolItemOut])
async def get_pool_items(
    pool_id: int,
    keyword: Optional[str] = Query(None, description="代码/名称关键字"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    session: AsyncSession = Depends(get_db),
):
    """获取池内股票列表"""
    pool = await session.get(StockPool, pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="股票池不存在")

    stmt = (
        select(StockPoolItem)
        .where(StockPoolItem.pool_id == pool_id)
        .options(selectinload(StockPoolItem.stock))
    )
    count_stmt = select(func.count()).select_from(StockPoolItem).where(
        StockPoolItem.pool_id == pool_id
    )

    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.join(
            StockBasic, StockBasic.code == StockPoolItem.stock_code
        ).where(
            (StockBasic.code.ilike(like)) | (StockBasic.name.ilike(like))
        )
        count_stmt = count_stmt.join(
            StockBasic, StockBasic.code == StockPoolItem.stock_code
        ).where(
            (StockBasic.code.ilike(like)) | (StockBasic.name.ilike(like))
        )

    total_result = await session.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(StockPoolItem.added_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    items = result.scalars().all()

    out_items = []
    for item in items:
        out_items.append(
            StockPoolItemOut(
                pool_id=item.pool_id,
                stock_code=item.stock_code,
                added_at=item.added_at,
                note=item.note,
                stock=StockBasicOut.model_validate(item.stock) if item.stock else None,
            )
        )
    return out_items


@router.post("/{pool_id}/add", response_model=dict)
async def add_to_pool(
    pool_id: int, body: StockPoolItemAdd, session: AsyncSession = Depends(get_db)
):
    """向池内添加股票"""
    pool = await session.get(StockPool, pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="股票池不存在")

    # 验证股票是否存在
    stock = await session.get(StockBasic, body.stock_code)
    stock_name = stock.name if stock else body.stock_code

    # 检查是否已在池中
    existing = await session.execute(
        select(StockPoolItem).where(
            StockPoolItem.pool_id == pool_id,
            StockPoolItem.stock_code == body.stock_code,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"股票 {body.stock_code} 已在池中")

    item = StockPoolItem(
        pool_id=pool_id,
        stock_code=body.stock_code,
        note=body.added_reason,
    )
    session.add(item)
    await session.commit()

    return {"success": True, "stock_code": body.stock_code, "stock_name": stock_name}


@router.post("/{pool_id}/remove", response_model=dict)
async def remove_from_pool(
    pool_id: int, body: StockPoolAddRemove, session: AsyncSession = Depends(get_db)
):
    """从池内移除股票"""
    pool = await session.get(StockPool, pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="股票池不存在")

    result = await session.execute(
        select(StockPoolItem).where(
            StockPoolItem.pool_id == pool_id,
            StockPoolItem.stock_code.in_(body.codes),
        )
    )
    items = result.scalars().all()

    if not items:
        return {"success": True, "removed": 0, "message": "没有匹配的股票"}

    for item in items:
        await session.delete(item)
    await session.commit()

    return {"success": True, "removed": len(items)}


@router.post("/{pool_id}/import-sector", response_model=dict)
async def import_sector_to_pool(
    pool_id: int,
    sector_code: str,
    session: AsyncSession = Depends(get_db),
):
    """将板块成分批量导入股票池（去重）"""
    pool = await session.get(StockPool, pool_id)
    if not pool:
        raise HTTPException(status_code=404, detail="股票池不存在")

    sector = await session.get(Sector, sector_code)
    if not sector:
        raise HTTPException(status_code=404, detail="板块不存在")

    result = await session.execute(
        select(SectorMember.stock_code).where(SectorMember.sector_code == sector_code)
    )
    codes = [r[0] for r in result.all()]

    if not codes:
        return {"success": True, "added": 0, "message": "板块无成分股"}

    # 获取池中已有股票
    existing_result = await session.execute(
        select(StockPoolItem.stock_code).where(StockPoolItem.pool_id == pool_id)
    )
    existing_codes = set(r[0] for r in existing_result.all())

    new_codes = [c for c in codes if c not in existing_codes]
    added_count = 0

    for code in new_codes:
        session.add(StockPoolItem(pool_id=pool_id, stock_code=code))
        added_count += 1

    await session.commit()

    return {
        "success": True,
        "sector_name": sector.name,
        "total_in_sector": len(codes),
        "already_in_pool": len(codes) - added_count,
        "added": added_count,
    }


# ========== 同步管理 ==========

@router.post("/sync", response_model=dict)
async def trigger_sync(background_tasks: BackgroundTasks):
    """触发全量同步（后台运行）"""
    if stock_pool_sync_service.is_running:
        return {"success": False, "message": "已有同步任务在运行"}

    background_tasks.add_task(stock_pool_sync_service.sync_all)
    return {"success": True, "message": "全量同步任务已启动"}


@router.get("/sync/status", response_model=SyncProgressOut)
async def sync_status():
    """同步状态"""
    return SyncProgressOut(**stock_pool_sync_service.get_progress())

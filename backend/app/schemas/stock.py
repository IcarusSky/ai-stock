"""
AI Stock - 股票池与板块 Pydantic 模型
"""
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class StockBasicOut(BaseModel):
    """股票基础信息输出"""

    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    market: str = Field(..., description="市场 SH/SZ/BJ")
    board: str = Field(..., description="板块类型")
    list_date: Optional[date] = Field(None, description="上市日期")
    is_st: bool = Field(False, description="是否 ST")
    is_suspended: bool = Field(False, description="是否停牌")
    total_share: Optional[int] = Field(None, description="总股本")
    float_share: Optional[int] = Field(None, description="流通股本")
    industries: list[str] = Field(default_factory=list, description="所属行业")
    concepts: list[str] = Field(default_factory=list, description="所属概念")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


class SectorOut(BaseModel):
    """板块输出"""

    code: str = Field(..., description="板块代码")
    name: str = Field(..., description="板块名称")
    type: str = Field(..., description="industry/concept/region")
    source: str = Field("eastmoney", description="数据源")
    parent_code: Optional[str] = Field(None, description="父板块代码")
    updated_at: datetime = Field(..., description="更新时间")
    member_count: Optional[int] = Field(None, description="成分股数量（可选）")

    class Config:
        from_attributes = True


class SectorStockOut(StockBasicOut):
    """板块成分股输出"""

    weight: Optional[float] = Field(None, description="权重")


class StockPoolCreate(BaseModel):
    """创建股票池"""

    name: str = Field(..., min_length=1, max_length=64, description="池名称")
    description: Optional[str] = Field(None, description="描述")
    type: str = Field("custom", description="custom/sector/dynamic")
    filter_rule: Optional[dict] = Field(None, description="动态筛选规则")


class StockPoolUpdate(BaseModel):
    """更新股票池"""

    name: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = None
    type: Optional[str] = None
    filter_rule: Optional[dict] = None


class StockPoolOut(BaseModel):
    """股票池输出"""

    id: int
    name: str
    description: Optional[str]
    type: str
    filter_rule: Optional[dict]
    created_at: datetime
    updated_at: datetime
    stock_count: Optional[int] = Field(None, description="股票数量")

    class Config:
        from_attributes = True


class StockPoolItemOut(BaseModel):
    """股票池成分输出"""

    pool_id: int
    stock_code: str
    added_at: datetime
    note: Optional[str]
    stock: Optional[StockBasicOut] = None

    class Config:
        from_attributes = True


class StockPoolAddRemove(BaseModel):
    """股票池增删股票"""

    codes: list[str] = Field(..., min_length=1, description="股票代码列表")


class SyncTrigger(BaseModel):
    """触发同步"""

    scope: str = Field(..., description="stocks|sectors|members|all")


class SyncStatusOut(BaseModel):
    """同步状态"""

    running: bool = Field(False, description="是否正在同步")
    last_sync_at: Optional[datetime] = Field(None, description="最后同步时间")
    total_stocks: int = Field(0, description="股票总数")
    total_sectors: int = Field(0, description="板块总数")
    total_members: int = Field(0, description="成分股关系总数")
    message: Optional[str] = Field(None, description="状态描述")


class StockListOut(BaseModel):
    """股票列表分页输出"""

    total: int
    page: int
    page_size: int
    items: list[StockBasicOut]


class SectorTreeOut(BaseModel):
    """板块树"""

    industry: list[SectorOut]
    concept: list[SectorOut]
    region: list[SectorOut]

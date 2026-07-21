"""
AI Stock - 股票池与板块 ORM 模型
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class StockBasic(Base):
    """A 股基础信息"""

    __tablename__ = "stock_basic"
    __table_args__ = (
        Index("ix_stock_basic_market_board", "market", "board"),
        Index("ix_stock_basic_name", "name"),
    )

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)  # SH / SZ / BJ
    board: Mapped[str] = mapped_column(String(16), nullable=False)  # 主板 / 创业板 / 科创板 / 北交所
    list_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    is_st: Mapped[bool] = mapped_column(Boolean, default=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    total_share: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    float_share: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Sector(Base):
    """板块（行业 / 概念 / 地域）"""

    __tablename__ = "sector"
    __table_args__ = (
        Index("ix_sector_type", "type"),
        Index("ix_sector_parent_code", "parent_code"),
    )

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # industry / concept / region
    source: Mapped[str] = mapped_column(String(16), default="eastmoney")
    parent_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class SectorMember(Base):
    """板块成分股"""

    __tablename__ = "sector_member"
    __table_args__ = (
        Index("ix_sector_member_stock_code", "stock_code"),
    )

    sector_code: Mapped[str] = mapped_column(
        String(20), ForeignKey("sector.code", ondelete="CASCADE"), primary_key=True
    )
    stock_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("stock_basic.code", ondelete="CASCADE"), primary_key=True
    )
    weight: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class StockPool(Base):
    """用户股票池"""

    __tablename__ = "stock_pool"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(16), default="custom")  # custom / sector / dynamic
    filter_rule: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class StockPoolItem(Base):
    """股票池成分"""

    __tablename__ = "stock_pool_item"
    __table_args__ = (
        Index("ix_stock_pool_item_stock_code", "stock_code"),
    )

    pool_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("stock_pool.id", ondelete="CASCADE"),
        primary_key=True,
    )
    stock_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

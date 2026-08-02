"""AI Stock - 信号监控台 API"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
import uuid

router = APIRouter(prefix="/monitor", tags=["信号监控"])


class Signal(BaseModel):
    """交易信号模型"""
    id: str
    code: str
    name: str
    signal_type: str  # buy | sell | alert
    message: str
    price: float
    created_at: datetime
    is_read: bool = False


# 内存存储（后续替换为 PostgreSQL）
_signals: List[Signal] = []


@router.get("/signals", response_model=List[Signal])
async def get_signals(
    code: Optional[str] = None,
    signal_type: Optional[str] = None,
    unread_only: bool = False,
    limit: int = Query(50, le=200),
):
    """获取信号列表，支持过滤"""
    results = _signals
    if code:
        results = [s for s in results if s.code == code]
    if signal_type:
        results = [s for s in results if s.signal_type == signal_type]
    if unread_only:
        results = [s for s in results if not s.is_read]
    # 按时间倒序
    return list(reversed(results))[:limit]


@router.post("/signals")
async def create_signal(
    code: str,
    name: str,
    signal_type: str,
    message: str,
    price: float,
):
    """创建新信号（供内部策略调用）"""
    signal = Signal(
        id=str(uuid.uuid4()),
        code=code,
        name=name,
        signal_type=signal_type,
        message=message,
        price=price,
        created_at=datetime.now(),
        is_read=False,
    )
    _signals.append(signal)
    return {"ok": True, "signal_id": signal.id}


@router.post("/signals/mark-read")
async def mark_signal_read(signal_id: str):
    """标记单条信号已读"""
    for s in _signals:
        if s.id == signal_id:
            s.is_read = True
    return {"ok": True}


@router.post("/signals/mark-all-read")
async def mark_all_read():
    """标记所有信号已读"""
    for s in _signals:
        s.is_read = True
    return {"ok": True}


@router.get("/signals/unread-count")
async def unread_count():
    """获取未读信号数量"""
    return {"count": sum(1 for s in _signals if not s.is_read)}

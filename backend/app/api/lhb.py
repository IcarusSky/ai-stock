"""
AI Stock - 龙虎榜 API

数据源：akshare 东财 datacenter（stock_lhb_detail_em / stock_lhb_stock_statistic_em）
原因：东财 push2 实时快照在当前网络下 TLS 断连不可用，但 datacenter-web 域名可通。

核心数据获取逻辑已下沉到 app.services.lhb_service，供 API 和后台预热复用。
"""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

import akshare as ak

from app.services import lhb_service

router = APIRouter(prefix="/lhb", tags=["龙虎榜"])


class LHBStockItem(BaseModel):
    code: str
    name: str
    close_price: float
    change_pct: float
    turnover_rate: float = 0.0
    main_net_buy: float = 0.0
    main_buy_rate: float = 0.0
    reason: str = ""
    buy_seats: int = 0
    sell_seats: int = 0


class LHBResponse(BaseModel):
    items: List[LHBStockItem]
    total: int
    date: str
    updated_at: str


@router.get("/today", response_model=LHBResponse)
async def get_today_lhb(
    limit: int = Query(100, ge=1, le=200),
    direction: str = Query("all", description="all | buy | sell"),
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD，为空则取今天"),
):
    """获取龙虎榜（若指定日期无数据自动回退到最近一个交易日）"""
    try:
        data = await lhb_service.get_today_lhb(limit=limit, direction=direction, date=date)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"龙虎榜接口异常: {e}")
    return LHBResponse(**data)


@router.get("/history", response_model=LHBResponse)
async def get_lhb_history(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=500),
):
    """获取历史龙虎榜（按日期范围）"""
    end = end_date or datetime.now().strftime("%Y-%m-%d")

    start_fmt = start_date.replace("-", "")
    end_fmt = end.replace("-", "")

    try:
        df = await lhb_service.run_ak_sync(
            ak.stock_lhb_detail_em,
            start_date=start_fmt,
            end_date=end_fmt,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"龙虎榜历史数据接口异常: {e}")

    if df is None or df.empty:
        return LHBResponse(items=[], total=0, date=f"{start_date} ~ {end}",
                           updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    items = [it for it in (lhb_service.row_to_item(r) for _, r in df.iterrows()) if it]
    items.sort(key=lambda x: abs(x["main_net_buy"]), reverse=True)

    return LHBResponse(
        items=items[:limit],
        total=len(items),
        date=f"{start_date} ~ {end}",
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@router.get("/stock/{code}", response_model=dict)
async def get_stock_lhb_history(
    code: str,
    limit: int = Query(20, ge=1, le=100),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD，默认近1年"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD，默认今天"),
):
    """获取单只股票龙虎榜记录"""
    end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
    start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else (end - timedelta(days=365))

    try:
        df = await lhb_service.run_ak_sync(
            ak.stock_lhb_detail_em,
            start_date=lhb_service.to_date_str(start),
            end_date=lhb_service.to_date_str(end),
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"龙虎榜接口异常: {e}")

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"未找到股票 {code} 的龙虎榜记录")

    code_str = str(code).lstrip("shsz").zfill(6)
    df = df.copy()
    df["code_str"] = df["代码"].astype(str).str.zfill(6)
    matched = df[df["code_str"] == code_str]

    if matched.empty:
        raise HTTPException(status_code=404, detail=f"未找到股票 {code} 的龙虎榜记录")

    records = []
    for _, row in matched.head(limit).iterrows():
        records.append({
            "date": str(row.get("上榜日", "")),
            "close_price": float(row.get("收盘价", 0) or 0),
            "change_pct": float(row.get("涨跌幅", 0) or 0),
            "turnover_rate": float(row.get("换手率", 0) or 0),
            "main_net_buy": float(row.get("龙虎榜净买额", 0) or 0),
            "main_buy_rate": float(row.get("净买额占总成交比", 0) or 0),
            "reason": str(row.get("上榜原因", "") or ""),
        })

    return {
        "code": code_str,
        "name": str(matched.iloc[0].get("名称", "")),
        "total": len(matched),
        "records": records,
    }


@router.get("/stats/daily", response_model=dict)
async def get_lhb_daily_stats(
    days: int = Query(5, ge=1, le=30, description="统计近N个交易日"),
):
    """龙虎榜统计（近 N 日上榜次数 + 资金）"""
    try:
        return await lhb_service.get_lhb_daily_stats(days=days)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"龙虎榜统计接口异常: {e}")

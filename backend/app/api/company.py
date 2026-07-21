"""
AI Stock - 企业数据 API（天眼查）

未配置 TIANYANCHA_TOKEN 时返回 503 及配置指引；
当日调用超过 TIANYANCHA_DAILY_LIMIT 时返回 429（按次计费的预算保护）。
"""
import asyncio
from fastapi import APIRouter, HTTPException

from app.services.datasource.ifind_client import DataSourceError
from app.services.datasource.tianyancha_client import tianyancha_client, TianyanchaQuotaExceeded

router = APIRouter(prefix="/company", tags=["企业数据"])


def _handle_error(e: Exception):
    if isinstance(e, TianyanchaQuotaExceeded):
        return HTTPException(status_code=429, detail=str(e))
    return HTTPException(status_code=503, detail=str(e))


@router.get("/{keyword}/profile")
async def get_company_profile(keyword: str):
    """企业画像：工商基本信息 + 股东 + 主要人员"""
    try:
        baseinfo, holders, staff = await asyncio.gather(
            tianyancha_client.baseinfo(keyword),
            tianyancha_client.holders(keyword),
            tianyancha_client.staff(keyword),
        )
        return {"keyword": keyword, "baseinfo": baseinfo, "holders": holders, "staff": staff}
    except (DataSourceError, TianyanchaQuotaExceeded) as e:
        raise _handle_error(e)


@router.get("/{keyword}/risk")
async def get_company_risk(keyword: str):
    """企业风险：经营异常 + 行政处罚 + 法律诉讼"""
    try:
        abnormal, punishment, lawsuits = await asyncio.gather(
            tianyancha_client.abnormal(keyword),
            tianyancha_client.punishment(keyword),
            tianyancha_client.lawsuits(keyword),
        )
        return {
            "keyword": keyword,
            "abnormal": abnormal,
            "punishment": punishment,
            "lawsuits": lawsuits,
        }
    except (DataSourceError, TianyanchaQuotaExceeded) as e:
        raise _handle_error(e)


@router.get("/{keyword}/news")
async def get_company_news(keyword: str):
    """企业新闻舆情"""
    try:
        news = await tianyancha_client.news(keyword)
        return {"keyword": keyword, "news": news}
    except (DataSourceError, TianyanchaQuotaExceeded) as e:
        raise _handle_error(e)

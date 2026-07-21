"""
AI Stock - 天眼查开放平台客户端

文档: https://open.tianyancha.com （控制台: https://www.tianyancha.com/data）
认证: Authorization 头直接放 token（无 Bearer 前缀）
注意: 接口按次计费，内置每日调用上限保护；keyword 由 httpx 自动 URLEncode。
"""
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.services.datasource.ifind_client import DataSourceError


class TianyanchaQuotaExceeded(Exception):
    """天眼查每日调用超限"""


class TianyanchaClient:
    """天眼查开放平台客户端"""

    BASE_URL = "http://open.api.tianyancha.com"

    def __init__(self, token: str = "", daily_limit: int = 100):
        self._token = token
        self._daily_limit = daily_limit
        self._client = httpx.AsyncClient(timeout=10.0)
        self._call_date: str = ""
        self._call_count: int = 0

    @property
    def configured(self) -> bool:
        return bool(self._token)

    @property
    def today_calls(self) -> int:
        self._roll_date()
        return self._call_count

    @property
    def daily_limit(self) -> int:
        return self._daily_limit

    def _roll_date(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if self._call_date != today:
            self._call_date = today
            self._call_count = 0

    async def _get(self, path: str, keyword: str, **params) -> Dict[str, Any]:
        if not self.configured:
            raise DataSourceError("天眼查未配置 TIANYANCHA_TOKEN，请在 backend/.env 中配置")
        self._roll_date()
        if self._call_count >= self._daily_limit:
            raise TianyanchaQuotaExceeded(f"天眼查当日调用已达上限 {self._daily_limit} 次")
        try:
            resp = await self._client.get(
                f"{self.BASE_URL}{path}",
                headers={"Authorization": self._token},
                params={"keyword": keyword, "pageNum": 1, "pageSize": 20, **params},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            raise DataSourceError(f"天眼查请求失败({path}): {e}")
        except ValueError as e:
            raise DataSourceError(f"天眼查响应解析失败({path}): {e}")

        if data.get("errorCode") != 0:
            raise DataSourceError(f"天眼查返回错误({path}): {data.get('reason') or data}")
        self._call_count += 1
        return data.get("result") or {}

    async def baseinfo(self, keyword: str) -> Dict[str, Any]:
        """工商基本信息"""
        return await self._get("/services/open/ic/baseinfo/normal", keyword)

    async def holders(self, keyword: str) -> Dict[str, Any]:
        """企业股东"""
        return await self._get("/services/open/ic/holder/2.0", keyword)

    async def staff(self, keyword: str) -> Dict[str, Any]:
        """主要人员"""
        return await self._get("/services/open/ic/staff/2.0", keyword)

    async def abnormal(self, keyword: str) -> Dict[str, Any]:
        """经营异常"""
        return await self._get("/services/open/mr/abnormal/2.0", keyword)

    async def punishment(self, keyword: str) -> Dict[str, Any]:
        """行政处罚"""
        return await self._get("/services/open/mr/punishmentInfo/3.0", keyword)

    async def lawsuits(self, keyword: str) -> Dict[str, Any]:
        """法律诉讼"""
        return await self._get("/services/open/jr/lawSuit/3.0", keyword)

    async def news(self, keyword: str) -> Dict[str, Any]:
        """新闻舆情"""
        return await self._get("/services/open/ps/news/2.0", keyword)

    async def close(self):
        await self._client.aclose()


# 全局天眼查客户端实例
tianyancha_client = TianyanchaClient(
    token=settings.TIANYANCHA_TOKEN,
    daily_limit=settings.TIANYANCHA_DAILY_LIMIT,
)

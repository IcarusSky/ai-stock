"""
AI Stock - 同花顺 iFinD 官方 HTTP API 客户端

文档: https://ftwc.51ifind.com/gwstatic/static/ds_web/quantapi-web/
认证流程:
  1. POST /api/v1/get_access_token  (header: refresh_token) -> access_token（7 天有效）
  2. 数据请求统一 POST /api/v1/<endpoint> (header: access_token)

注意: 指标名/参数名以官方手册为准（help-center/manual.html），
     本客户端按已确认的结构防御性解析，缺字段时降级不报错。
"""
import asyncio
import time
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger


class DataSourceError(Exception):
    """数据源调用异常"""


def to_ifind_code(stock_code: str) -> str:
    """A股代码转 iFinD 格式: 600036 -> 600036.SH, 000001 -> 000001.SZ"""
    code = stock_code.strip().upper()
    if "." in code:
        return code
    if code[0] in ("6", "9"):
        return f"{code}.SH"
    if code[0] in ("0", "2", "3"):
        return f"{code}.SZ"
    if code[0] in ("4", "8"):
        return f"{code}.BJ"
    return f"{code}.SH"


def from_ifind_code(ifind_code: str) -> str:
    """iFinD 代码转纯数字: 600036.SH -> 600036"""
    return ifind_code.split(".")[0]


class IFindClient:
    """同花顺 iFinD HTTP API 客户端"""

    BASE_URL = "https://quantapi.51ifind.com/api/v1"
    TOKEN_TTL = 6 * 24 * 3600  # access_token 官方 7 天有效，缓存 6 天后主动换新

    # 实时行情指标（如需更多字段，按官方手册添加）
    QUOTE_INDICATORS = "latest,open,high,low,volume,amount,change,changeRatio"
    KLINE_INDICATORS = "open,high,low,close,volume,amount,changeRatio"

    def __init__(self, refresh_token: str):
        self._refresh_token = refresh_token
        self._access_token: Optional[str] = None
        self._token_fetched_at: float = 0.0
        self._lock = asyncio.Lock()
        self._client = httpx.AsyncClient(timeout=10.0)

    async def _get_access_token(self) -> str:
        """获取 access_token（带缓存与并发保护）"""
        async with self._lock:
            if self._access_token and (time.time() - self._token_fetched_at) < self.TOKEN_TTL:
                return self._access_token
            try:
                resp = await self._client.post(
                    f"{self.BASE_URL}/get_access_token",
                    headers={"Content-Type": "application/json", "refresh_token": self._refresh_token},
                )
                data = resp.json()
            except Exception as e:
                raise DataSourceError(f"iFinD access_token 请求失败: {e}")
            token = (data.get("data") or {}).get("access_token")
            if not token:
                raise DataSourceError(f"iFinD access_token 获取失败: {data}")
            self._access_token = token
            self._token_fetched_at = time.time()
            logger.info("iFinD access_token 获取成功")
            return token

    async def _post(self, endpoint: str, payload: Dict[str, Any], retry: bool = True) -> Dict[str, Any]:
        """统一 POST 请求，token 失效自动刷新重试一次"""
        token = await self._get_access_token()
        try:
            resp = await self._client.post(
                f"{self.BASE_URL}/{endpoint}",
                json=payload,
                headers={"Content-Type": "application/json", "access_token": token},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            raise DataSourceError(f"iFinD 请求失败({endpoint}): {e}")
        except ValueError as e:
            raise DataSourceError(f"iFinD 响应解析失败({endpoint}): {e}")

        error_code = data.get("errorcode", data.get("errorCode", 0)) or 0
        if error_code != 0:
            # token 相关错误：清缓存重试一次（错误码以官方手册为准，这里做模糊匹配）
            msg = str(data.get("errmsg") or data.get("message") or "")
            if retry and ("token" in msg.lower() or str(error_code) in ("-20001", "-20002", "401")):
                logger.warning(f"iFinD token 失效(code={error_code})，刷新后重试")
                self._access_token = None
                return await self._post(endpoint, payload, retry=False)
            raise DataSourceError(f"iFinD 返回错误({endpoint}): code={error_code}, msg={msg}")
        return data

    @staticmethod
    def _extract_tables(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        tables = data.get("tables")
        return tables if isinstance(tables, list) else []

    async def real_time_quotation(self, codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """实时行情，返回 {纯数字代码: {指标: 值}}"""
        payload = {
            "codes": ",".join(to_ifind_code(c) for c in codes),
            "indicators": self.QUOTE_INDICATORS,
        }
        data = await self._post("real_time_quotation", payload)
        result: Dict[str, Dict[str, Any]] = {}
        for item in self._extract_tables(data):
            thscode = item.get("thscode") or item.get("code") or ""
            table = item.get("table")
            if thscode and isinstance(table, dict):
                # table 的值可能是标量或单元素数组，统一拍平
                flat = {k: (v[0] if isinstance(v, list) and v else v) for k, v in table.items()}
                result[from_ifind_code(thscode)] = flat
        if not result:
            raise DataSourceError(f"iFinD 实时行情无数据: {codes}")
        return result

    async def history_quotation(
        self, stock_code: str, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """历史日K，返回原始 table 结构（time 数组 + table 列数组）"""
        payload = {
            "codes": to_ifind_code(stock_code),
            "indicators": self.KLINE_INDICATORS,
            "startdate": start_date,
            "enddate": end_date,
        }
        data = await self._post("cmd_history_quotation", payload)
        tables = self._extract_tables(data)
        if not tables:
            raise DataSourceError(f"iFinD 历史行情无数据: {stock_code}")
        return tables[0]

    async def smart_stock_picking(self, query: str) -> Dict[str, Any]:
        """问财智能选股（参数名以官方手册为准）"""
        return await self._post("smart_stock_picking", {"searchstring": query, "searchtype": "stock"})

    async def close(self):
        await self._client.aclose()

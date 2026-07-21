"""
AI Stock - 腾讯财经行情通道（qt.gtimg.cn 网页快照接口）

注意: 非官方接口，无 SLA，仅建议个人研究使用。
     返回字段为位置序号，无字段名，字段含义参考：
     https://web.ifzq.gtimg.cn/appstock/app/minute/query 等腾讯系接口的通用约定。
"""
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from app.services.datasource.ifind_client import DataSourceError


# qt.gtimg.cn 返回字段索引（v_sh600000="1~名称~代码~现价~昨收~今开~成交量~外盘~内盘~买一~买一量~...~时间~涨跌~涨跌%~最高~最低~价格/成交量(手)/成交额~成交量~成交额~换手率~PE~...~最高~最低~振幅~流通市值~总市值~PB~涨停价~跌停价~...")
class _Field:
    NAME = 1
    CODE = 2
    PRICE = 3
    PREV_CLOSE = 4
    OPEN = 5
    VOLUME = 6          # 成交量(手)
    TIME = 30
    CHANGE = 31
    CHANGE_PCT = 32
    HIGH = 33
    LOW = 34
    VOLUME_2 = 36       # 成交量(手)，与 6 相同
    AMOUNT = 37         # 成交额(万)
    TURNOVER = 38       # 换手率 %
    PE = 39
    AMPLITUDE = 43
    CIRCULATING_CAP = 44  # 流通市值(亿)
    TOTAL_CAP = 45        # 总市值(亿)
    PB = 46


def _to_tencent_code(stock_code: str) -> str:
    """600000 → sh600000，000001 → sz000001，430047 → bj430047"""
    code = stock_code.strip().lower()
    if code.startswith(("sh", "sz", "bj")):
        return code
    if code.startswith(("60", "68", "51", "52", "56", "58", "11", "13")):
        return f"sh{code}"
    if code.startswith(("00", "30", "15", "16", "12")):
        return f"sz{code}"
    if code.startswith(("4", "8", "92")):
        return f"bj{code}"
    return f"sz{code}"


def _f(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
    try:
        if value is None or value == "" or value != value:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


class TencentChannelClient:
    """腾讯财经行情通道"""

    BASE_URL = "https://qt.gtimg.cn/q="
    TIMEOUT = 5.0

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        async with self._lock:
            if self._client is None:
                self._client = httpx.AsyncClient(
                    timeout=self.TIMEOUT,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Referer": "https://gu.qq.com/",
                    },
                )
            return self._client

    async def get_quote(self, stock_code: str) -> Dict[str, Any]:
        """单票实时行情"""
        tx_code = _to_tencent_code(stock_code)
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.BASE_URL}{tx_code}")
            resp.raise_for_status()
            # 腾讯接口返回 GBK 编码
            text = resp.content.decode("gbk", errors="ignore")
        except Exception as e:
            raise DataSourceError(f"腾讯行情请求失败({tx_code}): {e}")

        # v_sh600000="1~浦发银行~600000~...";
        if '="' not in text:
            raise DataSourceError(f"腾讯行情无数据({tx_code}): {text[:100]}")
        try:
            payload = text.split('="', 1)[1].rsplit('"', 1)[0]
            fields = payload.split("~")
        except Exception as e:
            raise DataSourceError(f"腾讯行情解析失败({tx_code}): {e}")

        if len(fields) < 40:
            raise DataSourceError(f"腾讯行情字段不足({tx_code}): {len(fields)}")

        volume_hand = _f(fields[_Field.VOLUME]) or 0.0       # 手
        amount_wan = _f(fields[_Field.AMOUNT]) or 0.0        # 万元

        return {
            "code": stock_code,
            "name": fields[_Field.NAME],
            "price": _f(fields[_Field.PRICE]),
            "change": _f(fields[_Field.CHANGE]),
            "change_pct": _f(fields[_Field.CHANGE_PCT]),
            "open": _f(fields[_Field.OPEN]),
            "high": _f(fields[_Field.HIGH]),
            "low": _f(fields[_Field.LOW]),
            "volume": volume_hand * 100,         # 手 → 股
            "amount": amount_wan * 10000,        # 万元 → 元
            "amplitude": _f(fields[_Field.AMPLITUDE]),
            "turnover": _f(fields[_Field.TURNOVER]),
            "pe": _f(fields[_Field.PE], None),
            "pb": _f(fields[_Field.PB], None) if len(fields) > _Field.PB else None,
            "market_cap": (_f(fields[_Field.TOTAL_CAP], None) or 0) * 1e8 if len(fields) > _Field.TOTAL_CAP else None,
            "timestamp": datetime.now(),
        }

    async def close(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None

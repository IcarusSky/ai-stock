"""
AI Stock - 行情数据源路由（多通道自动降级）

优先级 MARKET_DATA_PRIORITY:
  auto       - 配置了 IFIND_REFRESH_TOKEN 走 iFinD，然后 tencent → eastmoney
  ifind      - 仅 iFinD
  tencent    - 仅腾讯财经
  eastmoney  - 仅东方财富（akshare）
  free       - tencent → eastmoney（免费通道组合）
  mock       - 不使用真实数据（上层回退模拟数据）

当前通道失败时自动降级到下一通道，全部失败抛 DataSourceError 由上层回退 mock。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.config import settings
from app.schemas.market import StockQuote, KLine
from app.services.datasource.ifind_client import IFindClient, DataSourceError
from app.services.datasource.free_client import FreeChannelClient
from app.services.datasource.tencent_client import TencentChannelClient


def _f(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
    """安全转 float"""
    try:
        if value is None or value != value:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


class DataSourceRouter:
    """行情数据源路由器"""

    def __init__(self):
        self._ifind: Optional[IFindClient] = (
            IFindClient(settings.IFIND_REFRESH_TOKEN) if settings.IFIND_REFRESH_TOKEN else None
        )
        self._tencent = TencentChannelClient()
        self._eastmoney = FreeChannelClient()
        self._last_channel: str = "mock"

    def _channel_chain(self) -> List[str]:
        priority = settings.MARKET_DATA_PRIORITY.lower()
        if priority == "ifind":
            return ["ifind"] if self._ifind else []
        if priority == "tencent":
            return ["tencent"]
        if priority == "eastmoney":
            return ["eastmoney"]
        if priority == "free":
            return ["tencent", "eastmoney"]
        if priority == "mock":
            return []
        # auto: ifind → tencent → eastmoney
        return (["ifind"] if self._ifind else []) + ["tencent", "eastmoney"]

    # ---------- 实时行情 ----------

    async def get_quote(self, stock_code: str) -> StockQuote:
        last_err: Optional[Exception] = None
        for channel in self._channel_chain():
            try:
                if channel == "ifind":
                    quote = await self._quote_via_ifind(stock_code)
                elif channel == "tencent":
                    quote = await self._quote_via_tencent(stock_code)
                else:
                    quote = await self._quote_via_eastmoney(stock_code)
                self._last_channel = channel
                return quote
            except Exception as e:
                last_err = e
                logger.warning(f"行情通道[{channel}]获取 {stock_code} 失败: {e}")
        raise DataSourceError(f"所有行情通道均失败({stock_code}): {last_err}")

    async def _quote_via_ifind(self, stock_code: str) -> StockQuote:
        assert self._ifind is not None
        tables = await self._ifind.real_time_quotation([stock_code])
        t = tables.get(stock_code) or {}
        price = _f(t.get("latest"))
        change_pct = _f(t.get("changeRatio"))
        change = _f(t.get("change"), None)
        if change is None and price and change_pct is not None:
            change = round(price * change_pct / (100 + change_pct), 2) if change_pct != -100 else 0.0
        return StockQuote(
            code=stock_code,
            name="",  # iFinD 实时接口不含名称，由上层补全
            price=price or 0.0,
            change=change or 0.0,
            change_pct=change_pct or 0.0,
            open=_f(t.get("open")) or 0.0,
            high=_f(t.get("high")) or 0.0,
            low=_f(t.get("low")) or 0.0,
            volume=_f(t.get("volume")) or 0.0,
            amount=_f(t.get("amount")) or 0.0,
            amplitude=0.0,   # 未请求该指标，可按需在 QUOTE_INDICATORS 中补充
            turnover=0.0,
            timestamp=datetime.now(),
        )

    async def _quote_via_tencent(self, stock_code: str) -> StockQuote:
        data = await self._tencent.get_quote(stock_code)
        return StockQuote(**data)

    async def _quote_via_eastmoney(self, stock_code: str) -> StockQuote:
        data = await self._eastmoney.get_quote(stock_code)
        return StockQuote(**data)

    # ---------- K线 ----------

    async def get_kline(
        self,
        stock_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[KLine]:
        last_err: Optional[Exception] = None
        for channel in self._channel_chain():
            try:
                if channel == "ifind":
                    klines = await self._kline_via_ifind(stock_code, start_date, end_date)
                elif channel == "tencent":
                    # 腾讯免费通道无 K 线接口，跳过
                    raise DataSourceError("tencent 通道不支持K线")
                else:
                    klines = await self._kline_via_eastmoney(stock_code, start_date, end_date)
                self._last_channel = channel
                return klines
            except Exception as e:
                last_err = e
                logger.warning(f"K线通道[{channel}]获取 {stock_code} 失败: {e}")
        raise DataSourceError(f"所有K线通道均失败({stock_code}): {last_err}")

    async def _kline_via_ifind(
        self, stock_code: str, start_date: Optional[str], end_date: Optional[str]
    ) -> List[KLine]:
        assert self._ifind is not None
        end = end_date or datetime.now().strftime("%Y-%m-%d")
        start = start_date or "1990-01-01"
        table = await self._ifind.history_quotation(stock_code, start, end)
        times = table.get("time") or []
        columns = table.get("table") or {}

        def col(name: str) -> list:
            v = columns.get(name)
            return v if isinstance(v, list) else []

        opens, highs, lows = col("open"), col("high"), col("low")
        closes, volumes, amounts = col("close"), col("volume"), col("amount")
        changes = col("changeRatio")

        klines = []
        for i, date in enumerate(times):
            def at(arr, idx):
                return arr[idx] if idx < len(arr) else None
            klines.append(KLine(
                code=stock_code,
                date=str(date),
                open=_f(at(opens, i)) or 0.0,
                high=_f(at(highs, i)) or 0.0,
                low=_f(at(lows, i)) or 0.0,
                close=_f(at(closes, i)) or 0.0,
                volume=_f(at(volumes, i)) or 0.0,
                amount=_f(at(amounts, i)) or 0.0,
                change_pct=_f(at(changes, i)) or 0.0,
            ))
        if not klines:
            raise DataSourceError(f"iFinD K线为空: {stock_code}")
        return klines

    async def _kline_via_eastmoney(
        self, stock_code: str, start_date: Optional[str], end_date: Optional[str]
    ) -> List[KLine]:
        rows = await self._eastmoney.get_kline(stock_code, start_date, end_date)
        return [KLine(**r) for r in rows]

    # ---------- 问财选股 ----------

    async def wencai(self, query: str) -> Dict[str, Any]:
        """自然语言选股：优先 iFinD 智能选股，其次 pywencai"""
        if self._ifind:
            try:
                data = await self._ifind.smart_stock_picking(query)
                return {"channel": "ifind", "query": query, "data": data}
            except Exception as e:
                logger.warning(f"iFinD 问财选股失败: {e}")
        if settings.PYWENCAI_COOKIE:
            try:
                rows = await self._eastmoney.wencai(query, settings.PYWENCAI_COOKIE)
                return {"channel": "pywencai", "query": query, "data": rows}
            except Exception as e:
                logger.warning(f"pywencai 问财选股失败: {e}")
        raise DataSourceError("问财选股无可用通道（配置 IFIND_REFRESH_TOKEN 或 PYWENCAI_COOKIE 后启用）")

    def wencai_status(self) -> Dict[str, Any]:
        if self._ifind:
            return {"available": True, "channel": "ifind"}
        if settings.PYWENCAI_COOKIE:
            return {"available": True, "channel": "pywencai"}
        return {"available": False, "channel": None}

    # ---------- 状态 ----------

    def status(self) -> Dict[str, Any]:
        chain = self._channel_chain()
        return {
            "priority": settings.MARKET_DATA_PRIORITY,
            "market_channel": chain[0] if chain else "mock",
            "channel_chain": chain,
            "last_channel": self._last_channel,
            "ifind": {"configured": self._ifind is not None},
            "tencent": {"available": True},
            "eastmoney": {"available": True},
            "wencai": self.wencai_status(),
        }


# 全局数据源路由器实例
data_source_router = DataSourceRouter()

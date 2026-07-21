"""
AI Stock - 免费行情通道（akshare 东财公开数据）

注意: akshare 为网页抓取接口，无 SLA，仅建议个人研究使用。
     所有同步调用统一用 asyncio.to_thread 包装，避免阻塞事件循环。
"""
import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from app.services.datasource.ifind_client import DataSourceError


class FreeChannelClient:
    """akshare 免费行情通道"""

    SPOT_TTL = 15  # 全市场快照缓存秒数（快照接口较重，必须缓存）

    def __init__(self):
        self._spot_df: Optional[Any] = None  # pandas DataFrame
        self._spot_fetched_at: float = 0.0
        self._spot_lock = asyncio.Lock()

    async def _get_spot_df(self):
        """获取东财全市场快照（带 15s 缓存与并发保护）"""
        import akshare as ak  # 延迟导入：akshare 加载较慢，避免拖慢启动

        async with self._spot_lock:
            if self._spot_df is not None and (time.time() - self._spot_fetched_at) < self.SPOT_TTL:
                return self._spot_df
            df = await asyncio.to_thread(ak.stock_zh_a_spot_em)
            self._spot_df = df
            self._spot_fetched_at = time.time()
            return df

    @staticmethod
    def _f(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
        """安全转 float，NaN/None/非法值返回 default"""
        try:
            if value is None or value != value:  # None 或 NaN
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    async def get_quote(self, stock_code: str) -> Dict[str, Any]:
        """单票实时行情（东财全市场快照过滤）"""
        try:
            df = await self._get_spot_df()
        except Exception as e:
            raise DataSourceError(f"akshare 快照获取失败: {e}")

        row = df[df["代码"] == stock_code]
        if row.empty:
            raise DataSourceError(f"akshare 无该股票数据: {stock_code}")
        r = row.iloc[0]
        f = self._f
        return {
            "code": stock_code,
            "name": str(r.get("名称", stock_code)),
            "price": f(r.get("最新价")),
            "change": f(r.get("涨跌额")),
            "change_pct": f(r.get("涨跌幅")),
            "open": f(r.get("今开")),
            "high": f(r.get("最高")),
            "low": f(r.get("最低")),
            "volume": f(r.get("成交量")),
            "amount": f(r.get("成交额")),
            "amplitude": f(r.get("振幅")),
            "turnover": f(r.get("换手率")),
            "pe": f(r.get("市盈率-动态"), None),
            "pb": f(r.get("市净率"), None),
            "market_cap": f(r.get("总市值"), None),
            "timestamp": datetime.now(),
        }

    async def get_kline(
        self,
        stock_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "qfq",
    ) -> List[Dict[str, Any]]:
        """日K线（前复权），日期格式 YYYY-MM-DD"""
        import akshare as ak

        end = (end_date or datetime.now().strftime("%Y-%m-%d")).replace("-", "")
        start = (start_date or "1990-01-01").replace("-", "")
        try:
            df = await asyncio.to_thread(
                ak.stock_zh_a_hist,
                symbol=stock_code, period="daily",
                start_date=start, end_date=end, adjust=adjust,
            )
        except Exception as e:
            raise DataSourceError(f"akshare K线获取失败: {e}")
        if df is None or df.empty:
            raise DataSourceError(f"akshare 无K线数据: {stock_code}")

        f = self._f
        klines = []
        for _, r in df.iterrows():
            klines.append({
                "code": stock_code,
                "date": str(r.get("日期")),
                "open": f(r.get("开盘")),
                "high": f(r.get("最高")),
                "low": f(r.get("最低")),
                "close": f(r.get("收盘")),
                "volume": f(r.get("成交量")),
                "amount": f(r.get("成交额")),
                "change_pct": f(r.get("涨跌幅")),
            })
        return klines

    async def wencai(self, query: str, cookie: str) -> List[Dict[str, Any]]:
        """问财自然语言选股（pywencai，需 cookie；非官方接口，有风控风险）"""
        try:
            import pywencai
        except ImportError:
            raise DataSourceError("pywencai 未安装（pip install pywencai）")
        try:
            df = await asyncio.to_thread(
                pywencai.get, query=query, query_type="stock", cookie=cookie
            )
        except Exception as e:
            raise DataSourceError(f"问财查询失败: {e}")
        if df is None or df.empty:
            return []
        return df.head(50).to_dict(orient="records")

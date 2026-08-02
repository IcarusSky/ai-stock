"""腾讯财经 WebSocket 实时行情客户端

用法:
    client = TencentWSClient()
    client.subscribe(["sh600000", "sz000001"])
    async for quote in client.stream():
        print(quote)  # {'code': '600000', 'price': 10.5, 'change_pct': 0.5, ...}
"""
import asyncio
import json
import re
from typing import Dict, List, AsyncGenerator, Optional
import websockets
from loguru import logger

class TencentWSClient:
    """腾讯财经 WebSocket 实时行情

    腾讯 WS 接口：wss://qt.gtimg.cn/ws
    订阅格式：pktype: subscribe / unsubscribe
    数据格式：v_sh600000="1~名称~代码~现价~..."
    """

    WS_URL = "wss://qt.gtimg.cn/ws"

    def __init__(self):
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._subscribed: set[str] = set()
        self._lock = asyncio.Lock()
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    def subscribe(self, codes: List[str]):
        """订阅股票（内部维护列表）"""
        for code in codes:
            normalized = self._normalize(code)
            self._subscribed.add(normalized)

    def unsubscribe(self, codes: List[str]):
        """取消订阅"""
        for code in codes:
            normalized = self._normalize(code)
            self._subscribed.discard(normalized)
        if self._ws and not self._ws.closed:
            codes_param = "~".join(codes)
            asyncio.create_task(self._ws.send(f'{{"mtype":"unsubscribe","codes":["{codes_param}"]}}'))

    def _normalize(self, code: str) -> str:
        """600000 → sh600000"""
        code = code.strip().lower()
        if code.startswith(("sh", "sz", "bj")):
            return code
        if code.startswith(("60", "68", "51", "52", "56", "58")):
            return f"sh{code}"
        if code.startswith(("00", "30", "15", "16", "12")):
            return f"sz{code}"
        if code.startswith(("4", "8", "92")):
            return f"bj{code}"
        return f"sz{code}"

    def _parse_tencent_payload(self, text: str) -> Optional[Dict]:
        """解析 v_sh600000="1~名称~代码~..." 格式"""
        if '="' not in text:
            return None
        try:
            # v_sh600000="..."
            key_part, payload_part = text.split('="', 1)
            code_raw = key_part.strip()
            # 去掉 v_ 前缀得到 sh600000
            code = code_raw[2:] if code_raw.startswith("v_") else code_raw

            fields = payload_part.rstrip('"; \n').split("~")
            if len(fields) < 32:
                return None

            def f(idx, default=0.0):
                try:
                    v = fields[idx]
                    return float(v) if v not in ("", None) else default
                except:
                    return default

            return {
                "code": code,
                "name": fields[1],
                "price": f(3),
                "prev_close": f(4),
                "open": f(5),
                "volume": f(6) * 100,  # 手→股
                "change": f(31),
                "change_pct": f(32),
                "high": f(33),
                "low": f(34),
                "amount": f(37) * 10000,  # 万元→元
                "timestamp": fields[30] if len(fields) > 30 else "",
            }
        except Exception as e:
            logger.debug(f"解析失败: {e}")
            return None

    async def _ensure_connected(self):
        if self._ws is None or self._ws.closed:
            self._ws = await websockets.connect(self.WS_URL, ping_interval=25, close_timeout=5)
            # 发送订阅
            if self._subscribed:
                await self._ws.send(f'{{"mtype":"subscribe","codes":["{"~".join(self._subscribed)}"]}}')

    async def stream(self) -> AsyncGenerator[Dict, None]:
        """生成器：持续产出行情数据"""
        self._running = True
        last_ping = asyncio.get_event_loop().time()

        while self._running:
            try:
                await self._ensure_connected()

                # 带超时接收，避免永久阻塞
                msg = await asyncio.wait_for(self._ws.recv(), timeout=30)

                # 处理心跳
                if msg == "ping":
                    await self._ws.send("pong")
                    continue

                # 解析行情数据
                # 腾讯 WS 可能返回多条，用换行分隔
                for line in msg.strip().split("\n"):
                    if not line.strip():
                        continue
                    parsed = self._parse_tencent_payload(line)
                    if parsed:
                        yield parsed

                last_ping = asyncio.get_event_loop().time()

            except asyncio.TimeoutError:
                # 30秒无消息，发送心跳保活
                try:
                    await self._ws.send("ping")
                except:
                    self._ws = None  # 强制重连
            except Exception as e:
                logger.warning(f"腾讯WS异常: {e}，2秒后重连")
                self._ws = None
                await asyncio.sleep(2)

    async def close(self):
        self._running = False
        if self._ws:
            await self._ws.close()

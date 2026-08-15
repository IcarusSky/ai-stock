"""
AI Stock - 统一缓存层

优先使用 Redis；Redis 不可用时自动降级为进程内内存缓存，
保证在缓存服务异常时业务接口仍可正常运行。
"""
import json
import time
from datetime import datetime, timedelta
from typing import Any, Optional

from loguru import logger

# 进程内降级缓存：key -> (过期时间戳, JSON 字符串)
_mem_cache: dict = {}


def cache_key(prefix: str, *parts, **kwargs) -> str:
    """生成统一格式的缓存 key：prefix:part1:part2:k1=v1:k2=v2"""
    keys = [prefix]
    keys.extend(str(p) for p in parts)
    for k in sorted(kwargs):
        keys.append(f"{k}={kwargs[k]}")
    return ":".join(keys)


def ttl_until_tomorrow() -> int:
    """距离次日 0 点的秒数，用于按交易日缓存的每日固定数据"""
    now = datetime.now()
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(int((tomorrow - now).total_seconds()), 60)


async def _get_redis():
    from app.models.database import get_redis
    return await get_redis()


def _mem_get(key: str) -> Optional[Any]:
    item = _mem_cache.get(key)
    if not item:
        return None
    expire_at, raw = item
    if expire_at <= time.time():
        _mem_cache.pop(key, None)
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _mem_set(key: str, raw: str, expire: int) -> None:
    # 简单防膨胀：超过 1000 条时清理过期项
    if len(_mem_cache) > 1000:
        now = time.time()
        for k in [k for k, v in _mem_cache.items() if v[0] <= now]:
            _mem_cache.pop(k, None)
    _mem_cache[key] = (time.time() + expire, raw)


async def get_cache(key: str) -> Optional[Any]:
    """读取缓存，未命中返回 None"""
    try:
        r = await _get_redis()
        raw = await r.get(key)
        if raw is not None:
            return json.loads(raw)
        return None
    except Exception as e:
        logger.debug(f"Redis 读取失败，降级内存缓存: {e}")
        return _mem_get(key)


async def set_cache(key: str, value: Any, expire: int = 3600) -> None:
    """写入缓存，value 需可 JSON 序列化"""
    try:
        raw = json.dumps(value, ensure_ascii=False, default=str)
    except Exception as e:
        logger.warning(f"缓存序列化失败({key}): {e}")
        return
    try:
        r = await _get_redis()
        await r.set(key, raw, ex=expire)
    except Exception as e:
        logger.debug(f"Redis 写入失败，降级内存缓存: {e}")
        _mem_set(key, raw, expire)


async def delete_cache(key: str) -> None:
    """删除缓存"""
    _mem_cache.pop(key, None)
    try:
        r = await _get_redis()
        await r.delete(key)
    except Exception as e:
        logger.debug(f"Redis 删除失败: {e}")

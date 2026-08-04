"""
AI Stock - 市场数据预热服务

在每日开盘前/收盘后自动预计算主力资金、龙虎榜等数据并写入 Redis，
使用户点击时几乎秒开。同时提供手动触发接口用于测试。
"""
import asyncio
from datetime import datetime, timedelta
from typing import Callable, List

from loguru import logger

# 需要预热的数据项，每项是一个 (名称, 异步函数) 元组
PrecalcJob = tuple[str, Callable[[], None]]


class PrecalcService:
    """后台预热服务：每日定时 + 手动触发"""

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._jobs: List[PrecalcJob] = []
        self._last_run: str | None = None
        self._last_result: dict = {"success": [], "failed": []}

    def register(self, name: str, fn: Callable[[], None]):
        """注册一个预热任务"""
        self._jobs.append((name, fn))

    async def _run_once(self, triggered_by: str = "schedule") -> dict:
        """执行一次预热"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._last_run = now_str
        success, failed = [], []
        logger.info(f"开始预热市场数据 ({triggered_by})，共 {len(self._jobs)} 项")

        for name, fn in self._jobs:
            try:
                await fn()
                success.append(name)
                logger.info(f"预热完成: {name}")
            except Exception as e:
                failed.append({"name": name, "error": str(e)})
                logger.warning(f"预热失败: {name}, 错误: {e}")

        self._last_result = {"success": success, "failed": failed}
        logger.info(f"市场数据预热结束，成功 {len(success)} 项，失败 {len(failed)} 项")
        return {
            "triggered_by": triggered_by,
            "run_at": now_str,
            "success_count": len(success),
            "failed_count": len(failed),
            "success": success,
            "failed": failed,
        }

    async def trigger(self) -> dict:
        """手动触发一次预热（不阻塞调度器主循环）"""
        # 在后台运行，避免接口长时间等待
        asyncio.create_task(self._run_once("manual"))
        return {"success": True, "message": "预热任务已启动"}

    async def _loop(self):
        """主循环：每天 9:30 和 15:05 执行预热"""
        # 启动时立即跑一次（若 Redis 为空则填充缓存）
        try:
            await self._run_once("startup")
        except Exception as e:
            logger.warning(f"启动时预热失败: {e}")

        while not self._stop_event.is_set():
            now = datetime.now()
            targets = [
                now.replace(hour=9, minute=30, second=0, microsecond=0),
                now.replace(hour=15, minute=5, second=0, microsecond=0),
            ]
            # 若目标时刻已过，则安排到明天
            future_targets = [t + timedelta(days=1) if t <= now else t for t in targets]
            next_run = min(future_targets)
            wait_seconds = (next_run - now).total_seconds()

            logger.info(f"下次市场数据预热时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}，距今 {int(wait_seconds)} 秒")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=wait_seconds)
            except asyncio.TimeoutError:
                pass

            if self._stop_event.is_set():
                break
            await self._run_once("schedule")

    def start(self):
        """启动后台调度任务"""
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._task = asyncio.create_task(self._loop())
            logger.info("市场数据预热服务已启动")

    async def stop(self):
        """停止后台调度任务"""
        self._stop_event.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("市场数据预热服务已停止")

    def status(self) -> dict:
        """返回服务状态"""
        return {
            "running": self._task is not None and not self._task.done(),
            "job_count": len(self._jobs),
            "last_run": self._last_run,
            "last_result": self._last_result,
        }


# 全局单例
precalc_service = PrecalcService()

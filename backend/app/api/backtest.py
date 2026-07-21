"""
AI Stock - 回测API路由
"""
from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime, timedelta
import uuid

from app.schemas.backtest import (
    BacktestCreate, BacktestResult, BacktestTask,
    BacktestCompare, OptimizationResult
)
from app.services.backtest_service import backtest_service
from app.services.market_data_service import market_data_service

router = APIRouter(prefix="/backtest", tags=["回测"])


@router.post("/run", response_model=BacktestTask)
async def run_backtest(config: BacktestCreate):
    """发起回测任务"""
    task_id = str(uuid.uuid4())[:12]

    # 模拟获取K线数据
    klines_data = {
        "000001": await market_data_service.get_kline_data("000001"),
        "600036": await market_data_service.get_kline_data("600036"),
        "600519": await market_data_service.get_kline_data("600519"),
    }

    # 启动回测任务
    import asyncio
    asyncio.create_task(
        backtest_service.run_backtest(task_id, config, klines_data)
    )

    return BacktestTask(task_id=task_id, status="PENDING", progress=0.0, created_at=datetime.now())


@router.get("/{task_id}/result", response_model=BacktestResult)
async def get_backtest_result(task_id: str):
    """获取回测结果"""
    status = backtest_service.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="回测任务未找到")

    if status["status"] in ("PENDING", "RUNNING"):
        raise HTTPException(status_code=202, detail="回测进行中")

    if status["status"] == "FAILED":
        raise HTTPException(status_code=500, detail=status.get("error", "回测失败"))

    return status["result"]


@router.get("/{task_id}/status")
async def get_backtest_status(task_id: str):
    """获取回测任务状态"""
    status = backtest_service.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="回测任务未找到")
    return status


@router.get("/compare")
async def compare_strategies(strategy_ids: str, start_date: str, end_date: str):
    """策略对比：对每个策略真实跑一次回测并汇总对比"""
    ids = [s.strip() for s in strategy_ids.split(",") if s.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="至少需要选择一个策略")

    results = []
    for strategy_id in ids:
        config = BacktestCreate(
            strategy_id=strategy_id,
            start_date=start_date,
            end_date=end_date,
            initial_capital=100000.0
        )
        klines_data = {
            "000001": await market_data_service.get_kline_data("000001", start_date=start_date, end_date=end_date),
            "600036": await market_data_service.get_kline_data("600036", start_date=start_date, end_date=end_date),
            "600519": await market_data_service.get_kline_data("600519", start_date=start_date, end_date=end_date),
        }
        result = await backtest_service.run_backtest(str(uuid.uuid4())[:12], config, klines_data)
        results.append(result)

    if not results:
        raise HTTPException(status_code=500, detail="回测结果为空")

    best_by_return = max(results, key=lambda r: r.metrics.total_return).strategy_id
    best_by_sharpe = max(results, key=lambda r: r.metrics.sharpe_ratio).strategy_id
    best_by_drawdown = min(results, key=lambda r: r.metrics.max_drawdown).strategy_id

    return {
        "results": [r.model_dump() for r in results],
        "best_by_return": best_by_return,
        "best_by_sharpe": best_by_sharpe,
        "best_by_drawdown": best_by_drawdown
    }


@router.post("/optimize")
async def optimize_parameters(strategy_id: str, param_name: str):
    """策略参数优化：网格搜索指定参数"""
    from app.services.strategy_engine import strategy_engine

    strategy = strategy_engine.strategies.get(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略未找到")

    param_values = [5, 10, 15, 20, 25, 30]
    results = []
    original_value = strategy.params.get(param_name)

    for value in param_values:
        strategy.params[param_name] = value
        config = BacktestCreate(
            strategy_id=strategy_id,
            start_date=(datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d'),
            end_date=datetime.now().strftime('%Y-%m-%d'),
            initial_capital=100000.0
        )
        klines_data = {
            "000001": await market_data_service.get_kline_data("000001", start_date=config.start_date, end_date=config.end_date),
            "600036": await market_data_service.get_kline_data("600036", start_date=config.start_date, end_date=config.end_date),
            "600519": await market_data_service.get_kline_data("600519", start_date=config.start_date, end_date=config.end_date),
        }
        result = await backtest_service.run_backtest(str(uuid.uuid4())[:12], config, klines_data)
        results.append(result.metrics)

    # 恢复原始参数
    if original_value is not None:
        strategy.params[param_name] = original_value
    else:
        strategy.params.pop(param_name, None)

    best_idx = max(range(len(results)), key=lambda i: results[i].sharpe_ratio)
    best_value = param_values[best_idx]
    best_metrics = results[best_idx]

    return {
        "param_name": param_name,
        "param_values": param_values,
        "results": [m.model_dump() for m in results],
        "best_value": best_value,
        "best_metrics": best_metrics.model_dump()
    }

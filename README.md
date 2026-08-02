# AI 量化交易系统 - 当前设计与未来计划

> 版本：V3
> 最后更新：2026-07-26
> 说明：本文档整合了原 TODO.md / SPEC.md / PLAN_V2.md / DESIGN.md 的核心内容，只保留当前有效设计和未来计划。

---

## 一、项目定位

基于 AI 的实时量化交易系统，面向 10 万资金规模的个人投资者，支持实时行情、策略管理、回测分析、新闻舆情、股票池维护、信号监控和飞书推送。

---

## 二、技术栈

- **前端**：React + TypeScript + Vite + Ant Design + ECharts
- **后端**：Python 3.13 + FastAPI + SQLAlchemy 2.x + Pydantic 2.x
- **数据库**：PostgreSQL + Redis + MongoDB
- **实时通信**：WebSocket
- **数据源**：同花顺 iFinD / akshare（东财）/ 腾讯财经 WS / 天眼查 / 鼓掌财经
- **LLM**：Kimi / OpenAI / Anthropic（OpenAI 兼容协议）
- **消息推送**：飞书 Webhook

---

## 三、当前已实现功能

### 3.1 行情与交易
- 实时行情查询（单股/批量）
- 腾讯财经 WebSocket 实时行情订阅
- 模拟交易账户（买入/卖出/撤单）
- 持仓、资金曲线、成交记录

### 3.2 策略
- 策略 CRUD（趋势跟踪/均值回归/突破/板块轮动/价值投资）
- 市场环境评估
- 每日策略推荐

### 3.3 回测
- 发起回测任务
- 查询回测结果/状态
- 策略对比、参数优化（接口已存在）

### 3.4 新闻
- 鼓掌财经实时快讯 WebSocket 接入
- 新闻列表、AI 分析、市场情绪报告
- WebSocket 实时推送（待修复广播链路）

### 3.5 数据服务
- 数据源状态查看
- 问财选股
- 天眼查企业数据

### 3.6 股票池（后端已就绪，前端待补齐）
- 全市场 A 股基础信息同步
- 行业/概念/地域板块同步
- 板块成分股同步
- 自定义股票池 CRUD

### 3.7 监控与特色数据（后端已就绪，前端待补齐）
- 信号监控台
- 主力资金流排名
- 龙虎榜
- 技术形态扫描

---

## 四、第一阶段计划（当前执行中）

### 4.1 文档整合
- 合并原 TODO.md / SPEC.md / PLAN_V2.md / DESIGN.md 到本文档
- 删除旧的重复/过期文档

### 4.2 环境修复
- 修复 Python 3.13 下 `pip install -r requirements.txt` 失败问题
- 替换不兼容的 `empyrical==0.5.5` 为 `empyrical-reloaded`
- 更新其他依赖到兼容 Python 3.13 的版本

### 4.3 Settings 配置接口
- 新建 `backend/app/api/settings.py`
- 实现：
  - `GET /api/settings`
  - `POST /api/settings/broker`
  - `POST /api/settings/risk`
  - `POST /api/settings/feishu`
- 在 `main.py` 注册路由
- 前端 Settings 页面加载时回填，保存时发送完整字段

### 4.4 新闻系统修复
- 新增 `NewsRecord` ORM 模型
- 修复 `news_ingest_service` 广播类型不匹配
- 改为事件订阅驱动，避免重复广播
- 实现真实 DB 写入
- 前端接入 `/api/news/ws/realtime` 广播端点
- 从标题/内容提取关联股票代码和板块

### 4.5 新增前端页面
- **市场监控**（MarketMonitor）：集成信号、资金流、龙虎榜、形态扫描
- **股票池**（StockPool）：行业/概念树、全市场股票列表、自定义池管理

### 4.6 验证与通知
- 启动后端/前端，验证第一阶段功能
- 发送飞书通知到用户配置的 Webhook

---

## 五、第二阶段计划

1. **股票池定时同步**
   - APScheduler 每日 08:30 / 15:30 自动同步
   - 新增 `sync_job_log` 表持久化同步状态
   - 同步进度 WebSocket 推送

2. **回测真实化**
   - 前端轮询 `/backtest/{task_id}/status` 和 `/backtest/{task_id}/result`
   - 策略对比调用 `/backtest/compare`
   - 参数优化传入正确 `strategy_id`

3. **AI 策略生成修复**
   - Strategy 页 AI 生成按钮先调 LLM，再注册策略

4. **自选股持久化**
   - 将 `POST /market/watchlist` 接入真实数据库

---

## 六、第三阶段计划（超越对标：小宇量化）

对标产品核心优势：多市场 K 线、专业画线工具、策略市场、雷达扫描、每日必看。

我方超越方向：

1. **实时快讯与舆情**：鼓掌财经秒级快讯 + AI 买点分析
2. **智能盯盘/预警**：价格、涨跌幅、成交量、技术指标、新闻情绪多维度预警
3. **AI Agent 策略闭环**：自然语言 → 代码 → 回测 → 报告
4. **可视化策略编辑器**：低代码/拖拽构建经典策略
5. **回测评估深度化**：夏普、最大回撤、年化、胜率、Calmar、Sortino、参数敏感性热力图
6. **多因子选股雷达**：财务、技术、资金、新闻情绪、机构持仓
7. **组合与仓位管理**：组合回测、仓位再平衡
8. **多屏对比与关联分析**：多股同屏、板块联动、相关性矩阵
9. **指标与画图模板市场**
10. **模拟/实盘交易接入**
11. **AI 可解释性**
12. **社区与策略众测**
13. **移动端同步**

---

## 七、配置清单

核心配置在 `backend/.env`：

```env
# 数据库
DATABASE_URL=postgresql+asyncpg://aistock:aistock123@localhost:5432/aistock
REDIS_URL=redis://localhost:6379
MONGODB_URL=mongodb://localhost:27017/aistock

# LLM
LLM_BASE_URL=https://api.moonshot.cn/v1
LLM_API_KEY=
LLM_MODEL=kimi-k2.6

# 飞书
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/e6b9ad79-b308-4ecb-82f2-97643b82aaa9

# 同花顺 iFinD
IFIND_REFRESH_TOKEN=
MARKET_DATA_PRIORITY=auto

# 问财
PYWENCAI_COOKIE=

# 天眼查
TIANYANCHA_TOKEN=
TIANYANCHA_DAILY_LIMIT=100

# 风控（10 万资金默认）
MAX_POSITION_RATIO=0.2
MAX_TOTAL_POSITIONS=5
STOP_LOSS_RATIO=0.05
DAILY_LOSS_LIMIT=0.015
WEEKLY_LOSS_LIMIT=0.05
MIN_TRADE_AMOUNT=2000

# 回测
BACKTEST_COMMISSION=0.00025
BACKTEST_STAMP_TAX=0.001
BACKTEST_SLIPPAGE=0.001
```

---

## 八、快速启动

```bash
# 后端
cd backend
py -3.13 -m uvicorn app.main:app --port 8000

# 前端
cd frontend
npm run dev
```

访问：
- 前端：http://localhost:3000
- API 文档：http://localhost:8000/docs

---

## 九、风险提示

- 本系统仅供辅助参考，不构成投资建议
- 实盘交易前请充分回测和评估风险
- 初始资金建议从小资金开始，逐步增加
- 数据来源包含第三方公开接口，存在可用性和准确性风险

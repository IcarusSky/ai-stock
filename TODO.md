  # AI 量化交易系统 - 待办任务清单

> 生成时间：2026-07-20
> 当前状态：前后端均可正常启动，核心接口可用；外部服务均未配置（自动降级运行中）。

## 一、配置类任务（需要账号/密钥，只能本人操作）

按优先级排序，全部配置在 `backend/.env` 文件中。

### 1. 配置同花顺 iFinD 行情 token（最重要）
- [ ] 注册 iFinD 账号：https://quantapi.51ifind.com （注册即有免费额度）
- [ ] 获取 refresh_token：iFinD SDK 包 →「超级命令 → 工具 → refresh_token 查询」
- [ ] 填入 `.env` 的 `IFIND_REFRESH_TOKEN=`
- 现状：未配置时行情走 akshare 免费通道（网页抓取，无 SLA，偶发回退 mock 假数据），实测已出现 `last_channel: "mock"`
- 验证：配置后访问 `GET /api/datasource/status`，`market_channel` 应变为 `ifind`

### 2. 配置 LLM API 密钥
- [ ] 填入 `.env` 的 `ANTHROPIC_API_KEY=sk-ant-xxxxx`（或改用 OpenAI：`LLM_PROVIDER=openai` + `OPENAI_API_KEY`）
- 影响功能：LLM 策略生成（`/api/llm/strategy/generate`）、新闻智能分析

### 3. 配置飞书推送
- [ ] 在飞书群 →「群机器人」创建自定义机器人，复制 Webhook 地址
- [ ] 填入 `.env` 的 `FEISHU_WEBHOOK_URL=`
- 影响功能：交易信号、风险预警、每日报告推送
- 验证：前端「设置」页有测试推送入口（或调用 `/api/feishu/test`）

### 4. （可选）配置天眼查 token
- [ ] 申请地址：https://www.tianyancha.com/data （按次计费）
- [ ] 填入 `.env` 的 `TIANYANCHA_TOKEN=`，并用 `TIANYANCHA_DAILY_LIMIT` 控制每日上限
- 现状：未配置时企业数据接口返回 503（带配置指引）

### 5. （可选）配置问财选股免费通道
- [ ] 浏览器登录同花顺问财，复制 Cookie 填入 `.env` 的 `PYWENCAI_COOKIE=`
- 说明：若已配置 iFinD token 则无需此项，问财会直接走官方通道

## 二、环境类任务

### 6. 启动 PostgreSQL（数据持久化）
- [ ] 方式一（推荐）：`docker-compose up -d` 一键起 PostgreSQL + Redis + MongoDB
- [ ] 方式二：本地安装 PostgreSQL，建库 `aistock`，确认 `.env` 的 `DATABASE_URL` 指向正确
- 现状：启动日志报 `PostgreSQL 初始化失败: WinError 1225`（连接被拒绝），系统降级运行，重启后数据不保留
- 验证：启动后端无该 WARNING

### 7. 初始化 git 仓库
- [ ] `git init && git add . && git commit -m "init"`
- 说明：项目目前完全没有版本控制，改坏无法回滚，建议最先做

## 三、代码修复类任务（可交给 AI 完成）

### 8. 修复 16 个 TypeScript 编译错误
- [ ] 运行 `cd frontend && npx tsc --noEmit` 复现
- 全部为 TS6133（未使用的导入/变量），分布在：
  - `src/pages/Backtest.tsx`（3 处）
  - `src/pages/Dashboard.tsx`（9 处）
  - `src/pages/News.tsx`（1 处）
  - `src/pages/Strategy.tsx`（3 处）
- 说明：`npm run build` 只跑 vite 不做类型检查所以构建能过，但严格 CI 会失败
- 提示词参考：「修复 frontend 下所有 tsc --noEmit 报出的 TS6133 错误，删除未使用的导入和变量」

### 9. 修复 Windows 控制台日志中文乱码
- [ ] 启动日志中文显示为乱码（GBK 编码问题）
- 方向：loguru sink 输出强制 UTF-8，或启动时设置 `PYTHONIOENCODING=utf-8`

## 四、功能完善类任务（工作量较大，建议单独立项）

### 10. 平安证券实盘对接
- [ ] 现状：`backend/brokers/` 只有空的 `__init__.py`，仅有内置模拟账户（10 万资金）
- 难点：国内券商无公开 API，常见方案是走通达信/同花顺下单程序（如 easytrader 库）或 QMT/PTrade 量化终端
- 建议：先用模拟盘把策略-信号-下单-风控全链路跑通，实盘最后再接

### 11. 补充自动化测试
- [ ] 项目目前零测试；建议先给 `market_data_service`（降级链路）和 `order_executor`（风控规则）补 pytest

### 12. 前端 bundle 优化（低优先级）
- [ ] 单 chunk 2.3MB（gzip 765KB），可按页面做动态 `import()` 代码分割

## 五、建议执行顺序

1. **先做 7（git init）** —— 后续所有改动都有保障
2. **再做 1（iFinD token）** —— 行情数据质量是系统的根基
3. **然后 2、3（LLM + 飞书）** —— 核心 AI 功能解锁
4. **6（PostgreSQL）** —— 需要长期跑数据时再做
5. **8、9（代码修复）** —— 随时可交给 AI 处理
6. **10、11、12** —— 功能迭代阶段再排期

## 附：快速启动命令

```bash
# 后端（使用内置 Python 环境）
cd backend && ../.tools/python-embed/python.exe -m uvicorn app.main:app --port 8000

# 前端（另开一个终端）
cd frontend && npm run dev

# 访问地址
# 前端页面: http://localhost:3000
# API 文档: http://localhost:8000/docs
```

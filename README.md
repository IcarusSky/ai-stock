# AI量化交易系统

基于AI的实时量化交易系统，支持多种策略、市场分析、回测和实盘对接。

## 功能特性

1. **实时行情面板** - 展示持仓、自选股、资金曲线
2. **多策略支持** - 趋势跟踪、均值回归、突破策略等
3. **每日策略选择** - 根据市场环境自动推荐策略
4. **回测分析** - 策略回测、指标分析、参数优化
5. **券商对接** - 平安证券对接（支持模拟/实盘）
6. **LLM策略生成** - 自然语言描述生成交易策略
7. **新闻分析** - 实时新闻、小作文分析、买点判断
8. **飞书推送** - 交易信号、风险预警、每日报告

## 技术栈

- **前端**: React + TypeScript + Ant Design + ECharts
- **后端**: Python FastAPI + SQLAlchemy
- **数据库**: PostgreSQL + Redis + MongoDB
- **实时通信**: WebSocket
- **LLM**: Claude API / OpenAI API

## 快速启动

### 1. 环境要求

- Docker & Docker Compose
- Node.js 18+ (前端开发)
- Python 3.11+ (后端开发)

### 2. Docker 部署

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 3. 本地开发

**后端：**
```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 复制环境配置
cp .env.example .env
# 编辑 .env 填入API密钥

# 启动服务
uvicorn app.main:app --reload --port 8000
```

**前端：**
```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 4. 访问地址

- 前端页面: http://localhost:3000
- API文档: http://localhost:8000/docs

## 配置说明

### 环境变量 (.env)

```env
# 数据库
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/aistock
REDIS_URL=redis://localhost:6379
MONGODB_URL=mongodb://localhost:27017/aistock

# LLM配置
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxx

# 飞书配置
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx

# 风控配置（10万资金）
MAX_POSITION_RATIO=0.2
MAX_TOTAL_POSITIONS=5
STOP_LOSS_RATIO=0.05
DAILY_LOSS_LIMIT=0.015
MIN_TRADE_AMOUNT=2000
```

### 数据源配置（同花顺 iFinD / 天眼查）

行情数据支持双通道自动降级，企业数据接入天眼查开放平台，均在 `backend/.env` 配置：

```env
# 同花顺 iFinD 官方 HTTP API（https://quantapi.51ifind.com 注册即有免费额度）
IFIND_REFRESH_TOKEN=
# auto=有 token 走 iFinD、否则走 akshare 免费通道；也可强制 ifind/free/mock
MARKET_DATA_PRIORITY=auto
# 天眼查开放平台（https://www.tianyancha.com/data 申请，按次计费）
TIANYANCHA_TOKEN=
TIANYANCHA_DAILY_LIMIT=100
```

- **同花顺 iFinD**：官方接口（含免费额度），refresh_token 从 iFinD SDK 包「超级命令 → 工具 → refresh_token 查询」获取；未配置时行情自动走 akshare 免费通道（网页抓取，无 SLA，仅限个人研究），再失败回退内置模拟数据，接口不会 500。
- **天眼查**：企业工商/股东/经营异常/行政处罚/诉讼/舆情接口，未配置 token 时企业数据接口返回 503 及配置指引；`TIANYANCHA_DAILY_LIMIT` 控制每日调用上限，防止超额计费。
- **问财选股**：`POST /api/datasource/wencai`，自然语言选股；有 iFinD token 走官方智能选股，或配置 `PYWENCAI_COOKIE` 走 pywencai 免费通道。
- **数据源状态**：`GET /api/datasource/status` 查看当前行情通道与各 token 配置状态，前端「设置」页也有展示。

> Kimi CLI 用户提示：同花顺另有官方 iFinD MCP Server（https://mcp.51ifind.com ，个人版 ¥40/月，注册有免费试用），可在 Kimi CLI 的 MCP 配置中加入（`{"mcpServers": {...,"url": "...", "headers": {"Authorization": "<密钥>"}}}`，官网可一键生成），让 AI 助手直接查行情选股；项目后端运行时使用上面的 HTTP API 接入，两者互不影响。

## 风险提示

⚠️ **重要声明**

1. 本系统仅供辅助参考，不构成投资建议
2. 炒股有风险，入市需谨慎
3. 实盘交易前请充分测试和评估风险
4. 初始资金建议从小资金开始，逐步增加

### 建议风控参数（10万资金）

| 参数 | 建议值 | 说明 |
|------|--------|------|
| 单只仓位上限 | 20% | 不超过2万元 |
| 最大持仓数 | 5只 | 分散风险 |
| 止损线 | 5% | 亏损达5%必须止损 |
| 日亏损上限 | 1.5% | 日亏1500元停止 |
| 单次最小交易 | 2000元 | 避免佣金占比过高 |

## 项目结构

```
ai-stock/
├── backend/
│   ├── app/
│   │   ├── api/          # API路由
│   │   ├── core/         # 核心模块
│   │   ├── services/     # 业务服务
│   │   ├── models/       # 数据模型
│   │   └── schemas/      # Pydantic模型
│   ├── brokers/          # 券商适配器
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/        # 页面组件
│   │   ├── services/     # API服务
│   │   └── App.tsx
│   └── package.json
├── data/                 # 数据存储
├── docker-compose.yml
└── README.md
```

## 核心API

### 行情服务
- `GET /api/market/quote/{code}` - 获取股票行情
- `GET /api/market/quotes` - 批量获取行情
- `GET /api/market/kline/{code}` - 获取K线数据
- `GET /api/market/sentiment` - 市场情绪

### 策略服务
- `GET /api/strategy/list` - 策略列表
- `POST /api/strategy/register` - 注册策略
- `POST /api/strategy/evaluate` - 评估市场环境
- `GET /api/strategy/daily/recommend` - 每日推荐

### 订单服务
- `POST /api/order/buy` - 买入下单
- `POST /api/order/sell` - 卖出下单
- `POST /api/order/cancel` - 撤单

### 回测服务
- `POST /api/backtest/run` - 发起回测
- `GET /api/backtest/{task_id}/result` - 获取结果
- `POST /api/backtest/optimize` - 参数优化

### 新闻服务
- `GET /api/news/realtime` - 实时新闻
- `GET /api/news/analyze/{id}` - 分析新闻
- `GET /api/news/market_sentiment` - 市场情绪报告

### LLM服务
- `POST /api/llm/strategy/generate` - 生成策略

## 许可证

MIT License

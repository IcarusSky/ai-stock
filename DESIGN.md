# AI 量化交易系统 全面升级设计方案

> 生成时间：2026-07-21
> 文档目的：基于 4 项侦察（鼓掌财经协议 / 竞品小宇量化 / 前端按钮-后端接口对账 / 股票池现状）产出可执行的升级方案，供用户拍板后分批落地。

---

## 〇、背景结论速览

| 侦察项 | 关键结论 |
|---|---|
| 鼓掌财经 | 协议已逆向：WebSocket `wss://swoole2.guzhang.com:443/?token=<JWT>`，token 写死在首页 HTML 的 `encryptedToken` 变量里，服务端 `ping`/客户端 `pong`，消息是 JSON。可以直接复刻 token 接入 |
| 竞品小宇量化 | 6 大主导航 + AI 助手 + 训练营，最强点是 K 线画线工具、策略市场、每日必看（区间突破 + 龙虎榜）、盘面监控 Webhook。我们当前完全没有这些 |
| 前端按钮对账 | **14 个按钮完全没接后端**（见 §三），其中回测页的"开始回测"按钮结果完全在前端伪造 |
| 股票池 | 当前根本没有"股票池"概念，只有自选股（watchlist），且自选股只支持增删，没有按板块/行业组织 |

---

## 一、鼓掌财经实时新闻接入方案

### 1.1 协议摘要（已验证）

```
WS URL: wss://swoole2.guzhang.com:443/?token={encryptedToken}
Token 获取: GET https://724.guzhang.com/app/ → 在 HTML 里搜 var encryptedToken = "..."
           （页面加载时写死，目前长期有效；失效后重新抓 HTML 提取即可）
心跳: 服务端发 "ping"（纯文本），客户端回 "pong"（纯文本）
消息格式: JSON，关键字段：
  aid        新闻 ID（用于去重）
  title      标题（"refresh"/"delete" 为控制消息）
  content    正文
  ptime      发布时间字符串 "2026-07-21 01:36:14"
  categoryId 频道分类（1=必看 7=电报 10=港台 15=A股 16=海外 …）
  comefrom   来源（选股宝/格隆汇/财联社/鼓掌网…）
控制消息:
  title=refresh, comefrom=鼓掌网 → 客户端收到后整体刷新
  title=delete,  comefrom=鼓掌网 → content 是要删的 aid
```

### 1.2 后端落地

新建 `backend/app/services/guzhang_client.py`：

```python
class GuzhangClient:
    """鼓掌财经实时快讯 WebSocket 客户端（单例）"""

    async def start(self):
        # 1) 抓 HTML 提取 token（带 1h 内存缓存 + 失败用旧 token）
        # 2) 建立 websockets.connect，?token=<jwt>
        # 3) 收 "ping" → 回 "pong"
        # 4) 收 JSON → 标准化成 NewsItem → 推给订阅者（asyncio.Queue）
        # 5) 断线指数退避重连（1s/2s/4s...max 60s），重连前刷新 token
```

接入点：
- `news_service.fetch_realtime_news()` 改为：先读 guzhang_client 的内存环形缓冲（最新 200 条），降级再走 mock
- `backend/app/main.py` lifespan 启动时 `asyncio.create_task(guzhang_client.start())`
- 新增 WebSocket 出口：`/ws/news` 把 guzhang 的实时流推给前端（前端 News 页建立 WS，免刷新看到新快讯）

### 1.3 风险

- token 是硬编码 JWT，长期有效（payload `exp: 1785173838` ≈ 2026-07-27）。到期后需要重新抓 HTML 提取。客户端要内置"token 失效自动重抓"逻辑
- 服务端按 IP 限流未知，建议单实例只维持 1 条连接，避免重复
- 不要在前端直接暴露 token；走我们后端 `/ws/news` 中转

---

## 二、竞品对标：小宇量化的能力地图

### 2.1 完整功能清单（截图证据在 `.scratch/competitor/`）

```
顶部导航
├── 回测（首页）
│   ├── 代码输入 + 市场(A股/美股/港股/台股/加密/A股期货) + 周期(1m~月K) + 日期范围
│   ├── K线图（核心）
│   │   ├── 画线工具：聚焦/趋势飘带/区间画线/斐波那契/筹码分布/尺子/手绘折线/涨跌幅测量/复盘笔记
│   │   ├── 阻力/支撑区间滑块
│   │   ├── 自动刷新（15s）
│   │   └── 加入自选股
│   ├── 策略编辑 / 策略回测（双 Tab）
│   ├── 策略市场 / 导入策略 / 回测记录
│   └── 查看 A 股列表
├── 雷达
│   ├── 3 大模式：🛰️ 验证策略 / 🧪 跑模拟盘 / 🎯 找买点
│   ├── 单策略 vs 分批建仓
│   ├── 多策略组合（可加多个）
│   ├── 全市场扫描：A股/美股/港股/台股/加密 × 日K/周K/月K
│   ├── 高级筛选：回测交易数 ≥ / 综合评分 ≥ / 股价 ≥ / 榜单大小
│   ├── 维度开关：含ST/含新股/含指数/含停牌
│   └── 板块筛选：沪主板/深主板/北交所/科创板/创业板
├── 监控
│   ├── 监控项 CRUD
│   ├── Webhook 通知（POST JSON 到指定 URL，含收件箱调试）
│   └── 微信推送（PushPlus token）
├── 自选
│   ├── 分组管理（新建分组）
│   ├── 按市场看列表（A股/美股/港股/台股/加密）
│   └── 从雷达结果 hover 加入自选
├── 策略
│   ├── 策略模版（量化社区/样板间）
│   ├── 每个策略带：收益率/胜率/夏普/最大回撤/交易次数/Alpha/回测区间/描述/一键导入
│   └── 例：MACD金叉/强势回踩/RSI超卖/黄金坑/急跌首阳/逆势抢反弹
└── ✨ 每日必看 ▾
    ├── 📐 区间突破选股（区间通道首次形成日期列表 + 旗形图解）
    └── 🐲 A 股龙虎榜

全局
├── AI 量化助手（右下角）
│   ├── 快捷指令 5 条（跑策略/回测/优化/想法验证/股票分析）
│   ├── 模型切换：ChatGPT(gpt-5.4) / Claude(opus-4.6) / DeepSeek
│   ├── 附加 K 线上下文
│   └── 多轮对话（新会话按钮）
├── 🎓 训练营（15 关闯关 + 语音 + 通关 200 积分）
├── 🛠️ 工作台（专业模式）
├── 订阅 PRO / 试用 3 天 / 200 积分
└── 许愿池 / Mac & Zip 客户端下载 / Bilibili 社群
```

### 2.2 我们目前缺什么（按优先级）

| 缺口 | 竞品水平 | 我们现状 | 优先级 |
|---|---|---|---|
| K 线图画线工具 | 9 种专业画线 + 复盘笔记 | 完全没有 | P0 |
| 策略市场 | 现成 20+ 策略一键导入 | 3 个写死的默认策略 | P0 |
| 雷达（全市场扫描）| 支持多市场多周期扫描 + 高级筛选 | 无 | P0 |
| 区间突破选股 | 每日自动生成区间通道首次形成列表 | 无 | P1 |
| 龙虎榜 | 完整 A 股龙虎榜 | 无 | P1 |
| 盘面监控 + Webhook | 监控项 CRUD + Webhook + PushPlus | 只有飞书 webhook | P1 |
| AI 助手 | 内嵌多模型多轮助手，可附加 K 线 | 只有 LLM 策略生成一个接口 | P1 |
| 自选股分组 | 多分组管理 | 单一列表 | P2 |
| 训练营 / 积分 / 订阅 | 完整体系 | 无 | P3（不做） |

### 2.3 超越点（我们能做而它没做的）

1. **实时快讯流**（鼓掌财经 WebSocket 接入）—— 它没有
2. **AI 新闻分析 + 买点判断**（已有 `/news/analyze` 接口基础）—— 它没有
3. **企业风险数据**（天眼查已接入）—— 它没有
4. **问财自然语言选股**（已接入）—— 它没有
5. **板块级股票池 + 板块轮动策略**（本次升级新增）—— 它只有自选股
6. **真实下单通道**（券商对接）—— 它只做回测和模拟盘，无下单

---

## 三、前端按钮-后端接口断点清单（必修）

### 3.1 完全断死（前端伪造数据/无后端）

| # | 位置 | 按钮/交互 | 现状 | 修复方案 |
|---|---|---|---|---|
| 1 | `Backtest.tsx:48-67` | "开始回测" | 调用真接口后**忽略结果**，前端用 `Math.random()` 伪造回测数据塞到 results 里 | 改：拿到 task_id 后轮询 `/backtest/{id}/status`，完成后取 `/backtest/{id}/result` 真实数据 |
| 2 | `Backtest.tsx:114-128` | "权益曲线"图 | 完全用 `Math.random()` 生成 30 天假数据 | 改：回测结果里返回 equity_curve 字段，前端用真实数据 |
| 3 | `Backtest.tsx:106-110` | "详情"按钮 | onClick 为空 | 改：弹窗展示回测完整数据（交易明细 + 每月收益 + 指标） |
| 4 | `Backtest.tsx:107` | "优化"按钮 | onClick 为空 | 改：调 `/backtest/optimize` |
| 5 | `Backtest.tsx:139-142` | 策略选择下拉 | 硬编码 3 个策略 | 改：从 `/strategy/list` 动态加载 |
| 6 | `Backtest.tsx:161-165` | "策略对比"按钮 | 只是打开 Modal，用当前 results（假数据）做对比 | 改：让用户勾选策略，调 `/backtest/compare` |
| 7 | `Strategy.tsx:114-117` | "查看/编辑/删除"按钮 | onClick 为空 | 改：查看=详情 Modal，编辑=表单调 PUT，删除=确认后调 DELETE |
| 8 | `Strategy.tsx:210` | "应用此策略"按钮 | onClick 为空 | 改：弹"选择股票池 + 启动监听"对话框 |
| 9 | `Strategy.tsx:52-76` | "AI生成策略" | 调的是 `strategyApi.register`（普通注册），**根本没调 LLM** | 改：调 `llmApi.generateStrategy(description)` |
| 10 | `Dashboard.tsx:300` | "添加自选"按钮 | onClick 为空 | 改：弹窗输入代码 → 调 `POST /market/watchlist` |
| 11 | `Settings.tsx:79-81` | "保存券商配置"按钮 | 只弹 message，不调接口 | 改：调 `POST /broker/config`（后端需新增）|
| 12 | `Settings.tsx:83-85` | "保存风控设置"按钮 | 只弹 message，不调接口 | 改：调 `POST /risk/config`（后端需新增）|
| 13 | `News.tsx:43-53` | "刷新"按钮 | 调的 `/news/realtime`，但后端是 mock 5 条假数据 | 改：后端对接鼓掌财经（见 §一）|
| 14 | `portfolio.py:24-33` | "现价"字段 | 后端写死 8 个股票的假价格 | 改：调 `market_data_service.get_quote(code)` |

### 3.2 后端假数据重灾区（表面通，实际废）

- `news_service.fetch_realtime_news` → 永远返回同 5 条 mock
- `news_service.get_market_sentiment_report` → hot_sectors/hot_stocks 写死
- `strategy_api.list_strategies` → 每次调用都重写 3 个默认策略进内存
- `strategy_api.get_daily_recommendation` → trading_plan 字段写死字符串
- `backtest_api.compare_strategies` → 返回固定假数据
- `backtest_api.optimize_parameters` → 返回固定假数据
- `portfolio_api.get_capital_curve` → `random.uniform` 生成资金曲线
- `portfolio_api.get_positions` → 8 只股票的"现价"硬编码

**这 8 处是本次升级必须拔掉的"假数据毒瘤"。**

---

## 四、全市场股票池方案

### 4.1 数据模型（新增 5 张表）

```sql
-- 股票基础信息（全市场 5000+ 只）
CREATE TABLE stock_basic (
  code        VARCHAR(10) PRIMARY KEY,        -- 600519 / 000001
  name        VARCHAR(32) NOT NULL,
  market      VARCHAR(8)  NOT NULL,           -- SH/SZ/BJ
  board       VARCHAR(16) NOT NULL,           -- 主板/创业板/科创板/北交所
  list_date   DATE,
  is_st       BOOLEAN DEFAULT FALSE,
  is_suspended BOOLEAN DEFAULT FALSE,
  total_share BIGINT,
  float_share BIGINT,
  updated_at  TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_stock_basic_market_board ON stock_basic(market, board);

-- 板块定义（行业 + 概念 + 地域）
CREATE TABLE sector (
  code        VARCHAR(20) PRIMARY KEY,        -- BK0428 (东财板块代码)
  name        VARCHAR(64) NOT NULL,
  type        VARCHAR(16) NOT NULL,           -- industry/concept/region
  source      VARCHAR(16) NOT NULL,           -- eastmoney/ths/ifind
  parent_code VARCHAR(20),
  updated_at  TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_sector_type ON sector(type);

-- 板块成分（多对多）
CREATE TABLE sector_member (
  sector_code VARCHAR(20) NOT NULL,
  stock_code  VARCHAR(10) NOT NULL,
  weight      NUMERIC(8,4),
  updated_at  TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY (sector_code, stock_code)
);
CREATE INDEX idx_sector_member_stock ON sector_member(stock_code);

-- 自定义股票池（用户可建多个）
CREATE TABLE stock_pool (
  id          SERIAL PRIMARY KEY,
  name        VARCHAR(64) NOT NULL,
  description TEXT,
  type        VARCHAR(16) NOT NULL,           -- custom/sector/dynamic
  filter_rule JSONB,                          -- type=dynamic 时的筛选规则
  created_at  TIMESTAMP DEFAULT NOW(),
  updated_at  TIMESTAMP DEFAULT NOW()
);

-- 池内标的
CREATE TABLE stock_pool_item (
  pool_id     INT NOT NULL REFERENCES stock_pool(id) ON DELETE CASCADE,
  stock_code  VARCHAR(10) NOT NULL,
  added_at    TIMESTAMP DEFAULT NOW(),
  note        TEXT,
  PRIMARY KEY (pool_id, stock_code)
);
```

### 4.2 数据同步

新建 `backend/app/services/stock_sync_service.py`：

```
sync_all_stocks()         全量初始化：ak.stock_zh_a_spot_em() → 5000+ 只
sync_sectors()            同步板块：ak.stock_board_industry_name_em() (~86 个行业)
                                + ak.stock_board_concept_name_em() (~400+ 概念)
sync_sector_members(code) 同步单个板块成分：ak.stock_board_industry_cons_em(symbol)
sync_daily()              每日 16:30 跑：基础信息增量 + ST/停牌状态刷新
sync_sector_weekly()      每周日跑：板块成分全量重刷（概念板块变动频繁）
```

并发与限速：
- 单板块成分接口串行抓，sleep 0.3s，全量约 500 板块 ≈ 3 分钟
- 失败重试 3 次，指数退避；连续 5 次失败熔断，记日志走人工
- 用 Redis 存 `sync_lock`，避免多实例并发抓

### 4.3 新增 API

```
# 股票池 CRUD
GET    /api/stock-pool/list                    # 我的所有池
POST   /api/stock-pool/create                  # 新建（custom 或 dynamic）
PUT    /api/stock-pool/{id}
DELETE /api/stock-pool/{id}
GET    /api/stock-pool/{id}/stocks             # 池内股票
POST   /api/stock-pool/{id}/add                # 批量加入
POST   /api/stock-pool/{id}/remove

# 板块浏览
GET    /api/sector/tree                        # 板块树（行业/概念/地域）
GET    /api/sector/{code}/stocks               # 板块成分股
GET    /api/sector/{code}/quote                # 板块行情（涨跌幅、成交额）
POST   /api/sector/{code}/create-pool          # 一键把板块转成我的池

# 全市场浏览
GET    /api/stock/list?market=&board=&keyword=&page=   # 5000+ 分页查询
GET    /api/stock/{code}/sectors               # 反查一只股票属于哪些板块

# 同步管理（管理员）
POST   /api/stock-pool/sync/trigger            # 手动触发同步
GET    /api/stock-pool/sync/status             # 同步状态/进度
```

### 4.4 前端新增"股票池"页

主导航插入一项"股票池"，页面布局：

```
┌─────────────────────────────────────────────────────────┐
│ 左侧树（300px）              │ 右侧内容                 │
├─────────────────────────────────────────────────────────┤
│ ▼ 我的股票池                │ ┌───────────────────────┐ │
│   • 默认池                  │ │ 池名/描述/股票数       │ │
│   • 新能源核心              │ │ [加入自选][跑回测]    │ │
│   • 高股息                  │ ├───────────────────────┤ │
│   + 新建股票池              │ │ 股票列表（表格）       │ │
│ ▼ 行业板块                  │ │ 代码/名称/最新价/涨跌 │ │
│   • 银行 (42)               │ │ /行业/概念/操作       │ │
│   • 半导体 (128)            │ │                       │ │
│   • 医药生物 (286)          │ │ 操作：移除/加自选/下单│ │
│ ▼ 概念板块                  │ └───────────────────────┘ │
│   • 人工智能 (312)          │                          │
│   • 新能源车 (256)          │                          │
│ ▼ 地域板块                  │                          │
└─────────────────────────────────────────────────────────┘
```

---

## 五、总体架构调整

```
┌──────────────────────────────────────────────────────────┐
│  前端 React (Ant Design + ECharts)                       │
│  ├─ Dashboard / Strategy / Backtest / News / Settings    │
│  ├─ 【新增】StockPool（股票池）                           │
│  ├─ 【新增】Radar（雷达-全市场扫描）                      │
│  ├─ 【新增】Kline Pro（专业K线+画线）                     │
│  └─ 【新增】Daily（每日必看：区间突破/龙虎榜）            │
└──────────────────────────────────────────────────────────┘
                          │ HTTP/WS
┌──────────────────────────────────────────────────────────┐
│  FastAPI 后端                                            │
│  ├─ REST API（现有 + 新增 stock-pool/sector/radar/kline）│
│  ├─ WebSocket /ws/news（实时快讯推送）                    │
│  └─ WebSocket /ws/quote（实时行情推送）                   │
│                                                          │
│  Services                                                │
│  ├─ 【新】guzhang_client.py  → 鼓掌财经 WS 客户端        │
│  ├─ 【新】stock_sync_service.py → 全市场股票池同步       │
│  ├─ 【新】radar_service.py   → 全市场扫描                │
│  ├─ 【新】kline_tool_service.py → 画线数据持久化         │
│  └─ 现有：market_data / news / strategy / backtest       │
│                                                          │
│  数据库                                                  │
│  ├─ PostgreSQL: 新增 5 张表（见 §4.1）                   │
│  └─ Redis: 快讯环形缓冲 + 行情快照 + 同步锁              │
└──────────────────────────────────────────────────────────┘
```

---

## 六、实施路线图（P0 → P3）

### P0（本轮必做，预计 2-3 天）
1. ✅ 鼓掌财经 WebSocket 接入（§一）→ 后端 + News 页实时流
2. ✅ 修复 §3.1 中的 14 个断点（重点是回测页造假、策略页空按钮、Dashboard 加自选）
3. ✅ 拔掉 §3.2 的 8 处后端假数据
4. ✅ 股票池：建 5 张表 + akshare 全量同步 + 基础 API（§4.3 前 7 个）
5. ✅ 股票池前端页（树 + 表格）

### P1（第二轮，预计 2 天）
6. 雷达页：单策略扫全市场 + 高级筛选
7. 区间突破选股（每日扫描区间通道首次形成）
8. 龙虎榜（akshare 有现成接口 `ak.stock_lhb_detail_em`）
9. 盘面监控（监控项 CRUD + Webhook 通知）
10. K 线 Pro 页：基础画线（线段/斐波那契/测量），数据落 PostgreSQL

### P2（第三轮，预计 1-2 天）
11. 自选股分组
12. AI 助手面板（右下角全局，对接现有 llmService）
13. 策略市场（本地模版库，不做社区）

### P3（可选）
14. 训练营 / 积分体系（工作量大，暂缓）

---

## 七、子 agent 协同分工建议

落地阶段建议并行开 4 个子 agent：

| Agent | 任务 | 依赖 |
|---|---|---|
| A | P0-1：鼓掌财经 WS 客户端 + 后端 /ws/news + News 页改造 | 无 |
| B | P0-2+P0-3：14 个前端断点 + 8 处后端假数据 | 无 |
| C | P0-4+P0-5：股票池 5 张表 + 同步服务 + API + 前端页 | 无 |
| D | P1 全部：雷达 / 区间突破 / 龙虎榜 / 监控 / K线Pro | 等 C 完成（要用股票池） |

---

## 八、需要您拍板的 3 件事

1. **股票池数据存储**：用 PostgreSQL 还是先用 SQLite 单文件跑通？（PostgreSQL 更规范但要启 docker，SQLite 零依赖即开即用，后续可迁移）
2. **鼓掌财经 token 使用**：是否接受"复用其官网 token"的方式？（技术可行，但是灰色地带；如果不行只能退而用财联社/东财的免费 RSS）
3. **P0 范围**：上面 P0 列了 5 项，是您确认全做，还是先挑 1-2 个最急的？

请回复后我立即开工。

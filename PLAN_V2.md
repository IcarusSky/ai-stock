# AI 量化交易系统完善方案 V2

> 生成时间：2026-07-21
> 前置文档：TODO.md（V1 待办清单）
> 状态：方案待确认，未实施

---

## 📋 现状盘点

| 模块 | 现状 | 缺口 |
|------|------|------|
| **新闻系统** | `guzhang_client.py` 已有 WebSocket 框架（连 `wss://swoole2.guzhang.com:443`），但 token 需每次抓取首页 HTML 获取，**未联调真实数据流入库** | ① token 自动刷新机制；② 落库与推送链路；③ 前端实时订阅 |
| **前端按钮** | 5 个页面（Dashboard/News/Strategy/Backtest/Settings）存在大量无后端承载的交互 | 需全面排查按钮→API 映射，补齐缺失接口 |
| **股票池** | 只有简单的 `stock.py` model，无板块/行业/概念维度 | 需对接全市场 5000+ 只票的分类体系，支持多维筛选 |
| **对标产品** | `http://localhost:18080/` 未启动（Docker 未运行） | 需先启动再 Playwright 探索功能清单 |

---

## 🏗️ 设计方案

### 一、新闻系统实时化（鼓掌财经对接）

**架构**：

```
鼓掌财经 WS (wss://swoole2.guzhang.com:443)
    ↓ (token 从 https://724.guzhang.com/app/ HTML 提取，~7 天过期)
backend/app/services/guzhang_client.py  (已存在，需增强)
    ↓ 标准化 NewsItem
┌─────────────────┬──────────────────┬─────────────────┐
↓                 ↓                  ↓                 ↓
NewsBuffer      PostgreSQL         WebSocket推送      LLM 打标
(内存500条)     (持久化)           (前端订阅)         (情绪/概念)
```

**关键改动**：

1. `guzhang_client.py` 增强：
   - `_fetch_token()` 已实现（抓首页正则提取），需加缓存 + 过期自动刷新
   - 断线指数退避重连（5s → 60s 上限）
   - 消息去重（按 `news_id`）
   - 消息分类：电报/公告/研报/小道消息
2. 新增 `news_ingest_service.py`：消费 client → 写 PG + 广播 WS
3. 前端 `News.tsx` 改 WebSocket 订阅模式，新增"实时滚动"开关
4. 新增 `POST /api/news/test-guzhang` 用于联调

**已抓到的关键信息**（来自 `guzhang_app.html` 源码）：
- WS 地址：`wss://swoole2.guzhang.com:443/?token={encryptedToken}`
- token 示例（2026-07-21 抓取）：`eyJyb2xlIjoic3Vic2NyaWJlciIsImlhdCI6MTc4NDU2NjMyNywiZXhwIjoxNzg1MTcxMTI3LCJub25jZSI6IjJhYjFmZmUzYTBkMDA2ZTkifQ.f061198f3777bf434591177e1e39fa1429c552c88edc28a3ed616031a6300d37`
- iat=1784566327, exp=1785171127（约 7 天有效期）
- 心跳：服务器发 `ping`，客户端回 `pong`
- 配置：`window.__NEWS_WS_CONFIG__ = {"host":"swoole2.guzhang.com","port":443,"scheme":"wss","path":"/"}`

---

### 二、前端按钮全量排查

**方法**：扫描所有 `onClick` / `onSubmit` / `<Button>` 事件，对照 `services/api.ts` 是否调用真实接口。

**预期产出**（子agent 扫描后输出表格）：

| 页面 | 按钮 | 当前调用 | 后端接口 | 状态 |
|------|------|---------|---------|------|
| Dashboard | 买入 | ❌ 无 | ❌ 无 | 需新增 |
| ... | ... | ... | ... | ... |

**修复策略**：
- 已有接口未接线 → 直接补 onClick 绑定
- 接口不存在 → 后端补 endpoint + 前端接线
- 纯 UI 装饰 → 删除或加 `disabled` + tooltip 说明

---

### 三、股票池重构（板块/行业/概念 5000+ 维护）

**数据源优先级**：

1. **iFinD**（已预留，需 token）→ 行业分类（申万一级/二级/三级）+ 概念板块
2. **akshare 兜底**（`stock_board_industry_name_em`、`stock_board_concept_name_em` 东财分类）

**推荐策略：双通道（akshare 兜底 + iFinD 增强）**

**数据模型**：

```python
Stock              # 基础表：code, name, exchange, list_date, ...
Industry           # 行业表（树形：一级→二级→三级）
Concept            # 概念表
StockIndustry      # 股票-行业关联（多对一）
StockConcept       # 股票-概念关联（多对多）
StockPool          # 用户自定义股票池
StockPoolItem      # 池内股票 + 加入原因 + 标签
SyncLog            # 同步日志（增量更新追踪）
```

**同步服务** `stock_pool_sync_service.py`：

- 全量同步：首次跑一遍 5000+ 票（约 5-10 分钟）
- 增量同步：每日 08:30 跑新股/退市/分类变更
- 数据源优先级：iFinD（有 token）→ akshare（兜底）

**API 设计**：

```
GET  /api/stock-pool/list              # 按行业/概念/自定义池筛选
POST /api/stock-pool/create            # 创建自定义池
POST /api/stock-pool/{id}/add          # 批量加入
DEL  /api/stock-pool/{id}/remove       # 批量移除
GET  /api/stock-pool/industries        # 行业树（申万一级/二级/三级）
GET  /api/stock-pool/concepts          # 概念列表
POST /api/stock-pool/sync              # 手动触发同步
GET  /api/stock-pool/sync/status       # 同步进度查询
```

**前端**：新增 `StockPool.tsx` 页面
- 左侧树（行业 / 概念 / 我的池）
- 右侧股票表格 + 行情快照 + 加入池按钮
- 顶部搜索 + 多条件筛选

---

### 四、对标 18080 功能清单（待启动后 Playwright 探索）

**前置**：用户需先启动 Docker 项目。

**探索路径**（子agent 执行）：

1. 首页 / Dashboard → 截图 + 功能点提取
2. 各菜单页逐个点击 → 记录路由、按钮、数据源
3. 控制台 → 看后端 API 路径与响应结构
4. 输出《对标产品功能矩阵.md》→ 与我方现有功能对比 → 列出 GAP

---

### 五、子 agent 分工方案

**阶段 A（侦察，可并行）**：

| Agent | 任务 | 输出 |
|-------|------|------|
| A1 | 鼓掌财经协议深度逆向（cookie/token/消息格式/重连策略） | 协议文档 + 客户端代码改进点 |
| A2 | 前端按钮全量扫描 + 后端接口对照表 | 按钮-接口映射表（Markdown） |
| A3 | akshare 板块/行业/概念接口能力评估 + 数据量级测试 | 数据模型建议 + 同步耗时估算 |
| A4 | 18080 项目 Playwright 探索（**需用户先启动 Docker**） | 对标产品功能矩阵.md |

**阶段 B（实施，依赖 A）**：

| Agent | 任务 | 依赖 |
|-------|------|------|
| B1 | 新闻实时链路（guzhang_client 增强 + ingest + WS 推送 + 前端订阅） | A1 |
| B2 | 前端按钮修复（按 A2 表格逐个处理） | A2 |
| B3 | 股票池后端（models + 同步服务 + API） | A3 |
| B4 | 股票池前端页面（StockPool.tsx） | B3 |
| B5 | 对标功能补齐 | A4 报告 + 用户确认优先级 |

**建议实施顺序**：B3（股票池后端） → B1（新闻） → B2（按钮） → B4（股票池前端） → B5（对标）

---

## ❓ 待用户确认的决策点

1. **18080 项目怎么启动？** Docker Desktop 当前没运行。是镜像名是什么？还是 `docker run` 命令？需要先跑起来才能 Playwright 探索。

2. **鼓掌财经 token 是 7 天过期吗？** 抓到的 token iat=1784566327, exp=1785171127，差约 7 天。是否可以**长期复用首页抓取**，还是已有稳定登录态？

3. **股票池数据源首选哪个？**
   - A. 等用户配 iFinD token（质量最高但要等）
   - B. 先用 akshare 东财分类（免费、立刻可用、5000+ 全量）
   - C. **双通道（akshare 兜底 + iFinD 增强）—— 推荐**

4. **阶段 B 的优先级排序**？倾向：B3 → B1 → B2 → B4 → B5，是否同意？

5. **是否允许并行启动阶段 A 的 4 个侦察 agent？** （A4 需要先把 18080 跑起来）

---

## 📝 已抓到的关键代码片段（避免重新逆向）

### 鼓掌财经 WebSocket 连接（来自 mainApp.js）

```javascript
function getWebSocketConfig() {
    const config = window.__NEWS_WS_CONFIG__ || {};
    const scheme = config.scheme && config.scheme !== 'auto'
        ? config.scheme
        : (window.location.protocol === 'https:' ? 'wss' : 'ws');
    return {
        scheme: scheme,
        host: config.host || window.location.hostname,
        port: Number(config.port) || 9508,
        path: config.path || '/'
    };
}

function buildWebSocketUrl() {
    const config = getWebSocketConfig();
    const separator = config.path.indexOf('?') === -1 ? '?' : '&';
    return `${config.scheme}://${config.host}:${config.port}${config.path}${separator}token=${encodeURIComponent(encryptedToken)}`;
}

// 心跳处理
socket.onmessage = function (event) {
    if (event.data === 'ping') {
        socket.send('pong');
        return;
    }
    // 处理新闻消息...
};
```

### 已有 guzhang_client.py 关键方法

```python
GUZHANG_APP_URL = "https://724.guzhang.com/app/"
GUZHANG_WS_URL_TEMPLATE = "wss://swoole2.guzhang.com:443/?token={token}"

class GuzhangClient:
    async def _fetch_token(self) -> str:
        # 抓首页 HTML 提取 encryptedToken
        ...
    async def _run_loop(self) -> None:
        # 主循环：连接 → 收消息 → 断线重连
        ...
    async def _receive_loop(self, ws) -> None:
        # 65s 超时，收到 ping 回 pong
        ...
    def _normalize(self, data: Dict) -> Optional[NewsItem]:
        # 标准化为 NewsItem
        ...
```

---

## 🔗 相关文档

- [TODO.md](./TODO.md) — V1 待办清单
- [README.md](./README.md) — 项目说明
- [SPEC.md](./SPEC.md) — 规格说明（待查）
- [DESIGN.md](./DESIGN.md) — 设计文档（待查）

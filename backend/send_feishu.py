import json
import urllib.request
import sys

WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6b9ad79-b308-4ecb-82f2-97643b82aaa9"

payload = {
    "msg_type": "text",
    "content": {
        "text": "AI Stock 一阶段工作已完成\n\n完成内容：\n1. 整合 README.md / TODO.md / SPEC.md / PLAN_V2.md / DESIGN.md 为单一 README.md\n2. 修复 Python 3.13 依赖兼容性（empyrical-reloaded 等）\n3. 实现 Settings 后端 API（券商/风控/飞书配置）\n4. 修复新闻系统：对接鼓掌财经 WebSocket，持久化到 PostgreSQL，广播到前端\n5. 新增市场监控前端页面（信号/资金流/龙虎榜/形态扫描）\n6. 新增股票池前端页面（板块/行业/概念分类、自定义池、批量加入）\n7. 前端 TypeScript 编译与生产构建通过\n8. 后端关键文件语法编译通过\n\n下一步：启动后端/前端服务进行联调验证。"
    }
}

req = urllib.request.Request(
    WEBHOOK,
    data=json.dumps(payload).encode('utf-8'),
    headers={"Content-Type": "application/json"},
    method="POST"
)
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode('utf-8')
        sys.stderr.write(f"STATUS {resp.status}\n")
        sys.stderr.write(f"BODY {body}\n")
except Exception as e:
    sys.stderr.write(f"ERROR {type(e).__name__}: {e}\n")
    raise

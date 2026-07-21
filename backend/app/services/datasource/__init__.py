"""
AI Stock - 数据源适配层

- ifind_client: 同花顺 iFinD 官方 HTTP API（付费，稳定）
- free_client: akshare/pywencai 免费通道（无 token 时兜底）
- tianyancha_client: 天眼查开放平台（企业工商/风险/舆情数据）
- router: 双通道自动选择与降级
"""

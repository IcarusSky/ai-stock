"""
AI Stock - 飞书推送服务
"""
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger

from app.core.config import settings


class FeishuService:
    """飞书推送服务"""

    def __init__(self):
        self.webhook_url = settings.FEISHU_WEBHOOK_URL
        self.app_id = settings.FEISHU_APP_ID
        self.app_secret = settings.FEISHU_APP_SECRET
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def send_message(self, content: str, msg_type: str = "text") -> bool:
        """发送消息"""
        if not self.webhook_url:
            logger.warning("飞书Webhook URL未配置")
            return False

        try:
            payload = {
                "msg_type": msg_type,
                "content": {
                    "text": content
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0
                )

            if response.status_code == 200:
                logger.info(f"飞书消息发送成功: {content[:50]}...")
                return True
            else:
                logger.error(f"飞书消息发送失败: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"飞书消息发送异常: {e}")
            return False

    async def send_card(self, card_content: Dict[str, Any]) -> bool:
        """发送卡片消息"""
        if not self.webhook_url:
            logger.warning("飞书Webhook URL未配置")
            return False

        try:
            payload = {
                "msg_type": "interactive",
                "card": card_content
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0
                )

            if response.status_code == 200:
                logger.info("飞书卡片消息发送成功")
                return True
            else:
                logger.error(f"飞书卡片消息发送失败: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"飞书卡片消息发送异常: {e}")
            return False

    async def send_trade_signal(
        self,
        stock_code: str,
        stock_name: str,
        signal: str,  # BUY, SELL
        price: float,
        reason: str,
        confidence: float
    ):
        """发送交易信号"""
        signal_text = "🟢 买入信号" if signal == "BUY" else "🔴 卖出信号"
        emoji = "🚀" if signal == "BUY" else "⚠️"

        content = f"""{emoji} {signal_text}

股票: {stock_name}({stock_code})
价格: {price:.2f}
置信度: {confidence:.0%}
原因: {reason}

时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

        await self.send_message(content)

    async def send_position_change(
        self,
        stock_code: str,
        stock_name: str,
        direction: str,
        quantity: int,
        price: float
    ):
        """发送持仓变动通知"""
        direction_text = "买入" if direction == "BUY" else "卖出"
        content = f"""📊 持仓变动

股票: {stock_name}({stock_code})
方向: {direction_text}
数量: {quantity}股
价格: {price:.2f}
金额: {quantity * price:.2f}

时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

        await self.send_message(content)

    async def send_risk_alert(self, alert_type: str, message: str):
        """发送风险预警"""
        content = f"""🚨 风险预警

类型: {alert_type}
详情: {message}

时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

        await self.send_message(content)

    async def send_daily_report(
        self,
        total_assets: float,
        today_profit: float,
        today_profit_rate: float,
        positions: List[Dict[str, Any]],
        pending_orders: int
    ):
        """发送每日报告"""
        profit_emoji = "🟢" if today_profit >= 0 else "🔴"
        profit_text = f"{profit_emoji} 今日盈亏: {today_profit:+.2f} ({today_profit_rate:+.2%})"

        positions_text = "\n".join([
            f"- {p['name']}({p['code']}): {p['quantity']}股, 盈亏{p['profit_rate']:+.2%}"
            for p in positions
        ]) if positions else "无持仓"

        content = f"""📈 AI操盘每日报告

💰 总资产: {total_assets:.2f}
{profit_text}

📋 持仓情况:
{positions_text}

⏳ 挂单数量: {pending_orders}

时间: {datetime.now().strftime('%Y-%m-%d')}"""

        await self.send_message(content)

    async def send_strategy_recommendation(
        self,
        market_env: str,
        recommended_strategies: List[str],
        risk_level: str
    ):
        """发送策略推荐"""
        strategies_text = "\n".join([f"- {s}" for s in recommended_strategies])

        content = f"""🎯 每日策略推荐

市场环境: {market_env}
风险等级: {risk_level}

推荐策略:
{strategies_text}

时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"""

        await self.send_message(content)

    def build_card_template(self, title: str, content: str, color: str = "blue") -> Dict[str, Any]:
        """构建卡片模板"""
        return {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title
                },
                "template": color
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": content
                    }
                }
            ]
        }


# 全局飞书服务实例
feishu_service = FeishuService()

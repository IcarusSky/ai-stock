"""
AI Stock - LLM策略生成服务
"""
import json
from typing import Optional, Dict, Any
from loguru import logger

from app.core.config import settings
from app.schemas.strategy import StrategyCreate, StrategyType, StrategyRule, RuleType, RuleCondition


class LLMService:
    """LLM服务（OpenAI 兼容协议，支持 kimi / deepseek / openai 等）"""

    def __init__(self):
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.timeout = settings.LLM_TIMEOUT

    async def generate_strategy(self, description: str) -> Optional[StrategyCreate]:
        """根据自然语言描述生成策略"""
        prompt = self._build_strategy_prompt(description)

        try:
            response = await self._call_llm(prompt)
            return self._parse_strategy_response(response)
        except Exception as e:
            logger.error(f"LLM策略生成失败: {e}")
            return None

    async def analyze_market_env(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析市场环境"""
        prompt = self._build_market_analysis_prompt(market_data)

        try:
            response = await self._call_llm(prompt)
            return self._parse_market_analysis(response)
        except Exception as e:
            logger.error(f"市场环境分析失败: {e}")
            return self._default_market_analysis()

    async def analyze_news(
        self,
        news_content: str,
        stock_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """分析新闻影响"""
        prompt = self._build_news_analysis_prompt(news_content, stock_code)

        try:
            response = await self._call_llm(prompt)
            return self._parse_news_analysis(response)
        except Exception as e:
            logger.error(f"新闻分析失败: {e}")
            return self._default_news_analysis()

    def _build_strategy_prompt(self, description: str) -> str:
        """构建策略生成Prompt"""
        return f"""
你是一个量化交易策略专家。用户描述了一个交易策略需求，请将其转化为可执行的策略配置。

用户需求：{description}

请生成符合以下JSON格式的策略配置：
{{
    "name": "策略名称",
    "type": "策略类型，选项：TREND_FOLLOWING, MEAN_REVERSION, BREAKTHROUGH, SECTOR_ROTATION, VALUE_INVESTMENT",
    "description": "策略描述",
    "params": {{
        "参数名": "参数值"
    }},
    "rules": [
        {{
            "type": "ENTRY或EXIT或FILTER",
            "conditions": [
                {{
                    "indicator": "指标名，如MA5, RSI, MACD, KDJ, BB_UPPER等",
                    "operator": "操作符，如>, <, crossover, crossunder",
                    "value": 比较值
                }}
            ],
            "logic": "AND或OR，多条件时的逻辑关系",
            "description": "规则描述"
        }}
    ]
}}

注意：
1. 只输出JSON，不要有其他文字
2. 指标名使用标准技术指标缩写
3. 参数值要合理，符合A股交易规则
"""

    def _build_market_analysis_prompt(self, market_data: Dict[str, Any]) -> str:
        """构建市场分析Prompt"""
        return f"""
分析当前市场环境，返回结构化的市场分析结果。

市场数据：
{json.dumps(market_data, ensure_ascii=False, indent=2)}

请返回以下JSON格式的分析结果：
{{
    "trend": "BULL(上涨)或BEAR(下跌)或NEUTRAL(震荡)",
    "volatility": "HIGH(高波动)或MEDIUM(中等)或LOW(低波动)",
    "volume": "HIGH(放量)或MEDIUM(平量)或LOW(缩量)",
    "sector_rotation": "FAST(快速轮动)或MEDIUM(中等)或SLOW(慢速轮动)",
    "overall": "OPTIMISTIC(乐观)或NEUTRAL(中性)或PESSIMISTIC(悲观)",
    "score": 0-100的评分,
    "description": "环境描述"
}}

只输出JSON。
"""

    def _build_news_analysis_prompt(self, news_content: str, stock_code: Optional[str]) -> str:
        """构建新闻分析Prompt"""
        target = f"股票{stock_code}" if stock_code else "大盘"
        return f"""
分析以下新闻对{target}的影响，判断是否构成买入或卖出信号。

新闻内容：
{news_content}

请返回以下JSON格式的分析结果：
{{
    "sentiment": "BULLISH(利好)或BEARISH(利空)或NEUTRAL(中性)",
    "sentiment_score": -1到1的情绪评分,
    "is_buy_signal": true或false,
    "buy_signal_reason": "构成买点的理由，如果不构成则为空",
    "is_sell_signal": true或false,
    "sell_signal_reason": "构成卖点的理由，如果不构成则为空",
    "confidence": 0到1的置信度,
    "impact_analysis": "影响分析",
    "related_stocks": ["可能相关的股票代码"],
    "recommendation": "BUY或HOLD或SELL或WATCH"
}}

只输出JSON。
"""

    async def _call_llm(self, prompt: str) -> str:
        """调用 OpenAI 兼容协议 LLM（kimi / deepseek / openai 通用）"""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens,
        }
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature

        response = await client.chat.completions.create(**kwargs)

        return response.choices[0].message.content or ""

    def _parse_strategy_response(self, response: str) -> Optional[StrategyCreate]:
        """解析策略响应"""
        try:
            # 提取JSON
            json_str = response.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            json_str = json_str.strip()

            data = json.loads(json_str)

            # 转换为策略创建请求
            strategy = StrategyCreate(
                name=data.get("name", "未命名策略"),
                type=StrategyType(data.get("type", "TREND_FOLLOWING")),
                description=data.get("description", ""),
                params=data.get("params", {}),
                rules=[]
            )

            # 解析规则
            for rule_data in data.get("rules", []):
                conditions = []
                for cond in rule_data.get("conditions", []):
                    conditions.append(RuleCondition(
                        type=RuleType(rule_data.get("type", "ENTRY")),
                        indicator=cond.get("indicator", ""),
                        operator=cond.get("operator", ">"),
                        value=cond.get("value", 0),
                        description=cond.get("description", "")
                    ))

                strategy.rules.append(StrategyRule(
                    type=RuleType(rule_data.get("type", "ENTRY")),
                    conditions=conditions,
                    logic=rule_data.get("logic", "AND"),
                    description=rule_data.get("description", "")
                ))

            return strategy

        except Exception as e:
            logger.error(f"解析策略响应失败: {e}")
            return None

    def _parse_market_analysis(self, response: str) -> Dict[str, Any]:
        """解析市场分析响应"""
        try:
            json_str = self._extract_json(response)
            return json.loads(json_str)
        except:
            return self._default_market_analysis()

    def _parse_news_analysis(self, response: str) -> Dict[str, Any]:
        """解析新闻分析响应"""
        try:
            json_str = self._extract_json(response)
            return json.loads(json_str)
        except:
            return self._default_news_analysis()

    def _extract_json(self, text: str) -> str:
        """提取JSON字符串"""
        text = text.strip()
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end]
        elif "```" in text:
            start = text.find("```") + 3
            end = text.rfind("```")
            text = text[start:end]
        return text.strip()

    def _default_market_analysis(self) -> Dict[str, Any]:
        """默认市场分析"""
        return {
            "trend": "NEUTRAL",
            "volatility": "MEDIUM",
            "volume": "MEDIUM",
            "sector_rotation": "MEDIUM",
            "overall": "NEUTRAL",
            "score": 50.0,
            "description": "市场环境分析中..."
        }

    def _default_news_analysis(self) -> Dict[str, Any]:
        """默认新闻分析"""
        return {
            "sentiment": "NEUTRAL",
            "sentiment_score": 0.0,
            "is_buy_signal": False,
            "buy_signal_reason": "",
            "is_sell_signal": False,
            "sell_signal_reason": "",
            "confidence": 0.0,
            "impact_analysis": "新闻分析中...",
            "related_stocks": [],
            "recommendation": "WATCH"
        }


# 全局LLM服务实例
llm_service = LLMService()

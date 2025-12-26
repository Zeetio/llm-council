"""LLM呼び出しログ管理

各LLM呼び出しのトークン使用量、コスト、レスポンス時間を記録
"""

import logging
from typing import Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class LLMCallLog:
    """単一のLLM呼び出しログ"""
    timestamp: str
    model: str
    stage: str  # stage1, stage2, stage3
    member_id: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    response_time_ms: int
    tool_used: bool
    tool_name: str = None
    estimated_cost_usd: float = 0.0


class LLMLogger:
    """セッション内のLLM呼び出しを記録"""

    # 価格表（$/1M tokens）- OpenRouter価格ベース
    # 定期的に更新が必要
    PRICING = {
        # OpenAI
        "openai/gpt-4o": {"input": 2.5, "output": 10.0},
        "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "openai/gpt-4.1": {"input": 2.0, "output": 8.0},
        "openai/gpt-4.1-mini": {"input": 0.4, "output": 1.6},
        "openai/gpt-5.1": {"input": 3.0, "output": 12.0},
        "openai/gpt-5-mini": {"input": 0.5, "output": 2.0},

        # Anthropic
        "anthropic/claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
        "anthropic/claude-3-5-haiku": {"input": 0.8, "output": 4.0},
        "anthropic/claude-sonnet-4": {"input": 3.0, "output": 15.0},
        "anthropic/claude-opus-4": {"input": 15.0, "output": 75.0},

        # Google
        "google/gemini-2.0-flash": {"input": 0.1, "output": 0.4},
        "google/gemini-2.5-flash": {"input": 0.15, "output": 0.60},
        "google/gemini-3-flash-preview": {"input": 0.1, "output": 0.4},

        # DeepSeek
        "deepseek/deepseek-chat": {"input": 0.14, "output": 0.28},
        "deepseek/deepseek-chat-v3": {"input": 0.14, "output": 0.28},
        "deepseek/deepseek-r1-distill-llama-8b": {"input": 0.03, "output": 0.06},

        # xAI
        "x-ai/grok-4.1-fast": {"input": 1.0, "output": 4.0},

        # デフォルト（不明なモデル用）
        "default": {"input": 1.0, "output": 3.0}
    }

    def __init__(self):
        self.logs: List[LLMCallLog] = []
        self.tool_logs: List[Dict[str, Any]] = []  # ツール実行ログ

    def log_call(
        self,
        model: str,
        stage: str,
        member_id: str,
        usage: Dict[str, int],
        response_time_ms: int,
        tool_used: bool = False,
        tool_name: str = None
    ) -> LLMCallLog:
        """
        LLM呼び出しを記録

        Args:
            model: モデルID
            stage: ステージ名 (stage1, stage2, stage3)
            member_id: メンバーID
            usage: トークン使用量 {prompt_tokens, completion_tokens, total_tokens}
            response_time_ms: レスポンス時間（ミリ秒）
            tool_used: ツール使用の有無
            tool_name: 使用したツール名

        Returns:
            記録されたログエントリ
        """
        cost = self._estimate_cost(model, usage)

        log = LLMCallLog(
            timestamp=datetime.utcnow().isoformat(),
            model=model,
            stage=stage,
            member_id=member_id,
            prompt_tokens=usage.get('prompt_tokens', 0),
            completion_tokens=usage.get('completion_tokens', 0),
            total_tokens=usage.get('total_tokens', 0),
            response_time_ms=response_time_ms,
            tool_used=tool_used,
            tool_name=tool_name,
            estimated_cost_usd=cost,
        )

        self.logs.append(log)
        logger.info(
            f"LLM Call: {model} | {usage.get('total_tokens', 0)} tokens | "
            f"{response_time_ms}ms | ${cost:.6f}"
        )

        return log

    def add_tool_logs(self, tool_logs: List[Dict[str, Any]]):
        """ツール実行ログを追加"""
        self.tool_logs.extend(tool_logs)

    def _estimate_cost(self, model: str, usage: Dict[str, int]) -> float:
        """
        モデルごとの推定コストを計算

        Args:
            model: モデルID
            usage: トークン使用量

        Returns:
            推定コスト（USD）
        """
        rates = self.PRICING.get(model, self.PRICING["default"])
        input_cost = (usage.get('prompt_tokens', 0) / 1_000_000) * rates["input"]
        output_cost = (usage.get('completion_tokens', 0) / 1_000_000) * rates["output"]

        return input_cost + output_cost

    def get_summary(self) -> Dict[str, Any]:
        """
        ログのサマリーを取得

        Returns:
            集計されたサマリー情報
        """
        if not self.logs:
            return {
                "total_calls": 0,
                "total_tokens": 0,
                "total_cost_usd": 0,
                "tool_calls": self.tool_logs
            }

        total_time = sum(log.response_time_ms for log in self.logs)

        return {
            "total_calls": len(self.logs),
            "total_tokens": sum(log.total_tokens for log in self.logs),
            "total_prompt_tokens": sum(log.prompt_tokens for log in self.logs),
            "total_completion_tokens": sum(log.completion_tokens for log in self.logs),
            "total_cost_usd": round(sum(log.estimated_cost_usd for log in self.logs), 6),
            "average_response_time_ms": round(total_time / len(self.logs)),
            "total_response_time_ms": total_time,
            "by_stage": self._group_by_stage(),
            "by_model": self._group_by_model(),
            "tool_calls": self.tool_logs,
        }

    def _group_by_stage(self) -> Dict[str, Any]:
        """ステージごとに集計"""
        stages = {}
        for log in self.logs:
            if log.stage not in stages:
                stages[log.stage] = {
                    "calls": 0,
                    "tokens": 0,
                    "cost_usd": 0,
                    "response_time_ms": 0,
                    "tool_used_count": 0
                }
            stages[log.stage]["calls"] += 1
            stages[log.stage]["tokens"] += log.total_tokens
            stages[log.stage]["cost_usd"] += log.estimated_cost_usd
            stages[log.stage]["response_time_ms"] += log.response_time_ms
            if log.tool_used:
                stages[log.stage]["tool_used_count"] += 1

        # コストを丸める
        for stage in stages.values():
            stage["cost_usd"] = round(stage["cost_usd"], 6)

        return stages

    def _group_by_model(self) -> Dict[str, Any]:
        """モデルごとに集計"""
        models = {}
        for log in self.logs:
            if log.model not in models:
                models[log.model] = {
                    "calls": 0,
                    "tokens": 0,
                    "cost_usd": 0,
                    "response_time_ms": 0
                }
            models[log.model]["calls"] += 1
            models[log.model]["tokens"] += log.total_tokens
            models[log.model]["cost_usd"] += log.estimated_cost_usd
            models[log.model]["response_time_ms"] += log.response_time_ms

        # コストを丸める
        for model in models.values():
            model["cost_usd"] = round(model["cost_usd"], 6)

        return models

    def to_json(self) -> List[Dict[str, Any]]:
        """全ログをJSONシリアライズ"""
        return [asdict(log) for log in self.logs]

"""Agent 执行策略。

把“系统允许 Agent 做到什么程度”集中放在一个地方。
这样 graph.py 不需要到处写魔法数字，也不需要知道 HTTP 配置。
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentExecutionPolicy:
    """一次 Agent 执行的安全边界。"""

    # 防止单次请求产生过多 LLM/Tool 循环。
    max_steps: int = 8

    # 防止用户提交过大的 prompt。
    max_input_chars: int = 4000

    # 只有明确列出的工具才允许自动重试。
    # 默认空集合：未知 Tool 宁可不重试，也不要把副作用执行两次。
    retryable_tools: frozenset[str] = field(default_factory=frozenset)

    def validate(self) -> None:
        """启动时检查配置，避免运行到一半才发现策略非法。"""
        if self.max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        if self.max_input_chars < 1:
            raise ValueError("max_input_chars must be >= 1")

"""Agent 执行限制。

限制不是为了让 Agent 变笨，而是为了防止异常情况下无限循环。
先把限制集中放在一个小文件里，避免散落在 graph/service/api 各处。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentLimits:
    """一次 Agent 请求允许消耗的资源上限。"""

    max_steps: int = 8
    max_tool_retries: int = 2

    def validate(self) -> None:
        """启动时尽早发现明显错误的配置。"""
        if self.max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        if self.max_tool_retries < 0:
            raise ValueError("max_tool_retries must be >= 0")

"""把一次 Agent 请求的运行信息集中在一个对象中。

Graph、API、日志都可以通过这个对象拿到同一个 run_id。
这样排查问题时，可以用 run_id 把一次请求的日志串起来。
"""

from dataclasses import dataclass

from .observability import AgentRun


@dataclass
class AgentRunContext:
    """一次 Agent 请求共享的上下文。"""

    run: AgentRun

    @property
    def run_id(self) -> str:
        """方便调用方读取本次请求的唯一 ID。"""
        return self.run.run_id

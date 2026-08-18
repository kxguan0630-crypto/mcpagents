"""Agent 流式事件。

不要直接把 LangGraph 的内部事件暴露给 HTTP 客户端。
这里定义一套我们自己的简单事件模型，API 层只认识这些事件。
"""

from dataclasses import dataclass
from typing import Literal


EventType = Literal["answer", "tool_start", "tool_end", "error", "done"]


@dataclass(frozen=True)
class AgentEvent:
    """一次 Agent 执行过程中可以被前端消费的事件。"""

    type: EventType
    content: str = ""
    tool_name: str | None = None

    def to_sse(self) -> str:
        """转换成最简单的 Server-Sent Events 文本。"""
        import json

        data = {
            "type": self.type,
            "content": self.content,
            "tool_name": self.tool_name,
        }
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

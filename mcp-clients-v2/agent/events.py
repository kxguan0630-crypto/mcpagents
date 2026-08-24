"""Agent 流式事件。

不要直接把 LangGraph 的内部事件暴露给 HTTP 客户端。
这里定义一套我们自己的简单事件模型，API 层只认识这些事件。
"""

from dataclasses import dataclass, field
from typing import Any, Literal


EventType = Literal[
    "answer",
    "tool_start",
    "tool_end",
    "approval_required",
    "error",
    "done",
]


@dataclass(frozen=True)
class AgentEvent:
    """一次 Agent 执行过程中可以被前端消费的事件。"""

    type: EventType
    content: str = ""
    tool_name: str | None = None
    approval_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    # 是否是 Agent 内部 Workflow 工具。
    # 这类工具用于记录 facts/decision，不访问业务系统，不应该展示给最终用户。
    internal: bool = False

    def to_sse(self) -> str:
        """转换成最简单的 Server-Sent Events 文本。"""
        import json

        data = {
            "type": self.type,
            "content": self.content,
            "tool_name": self.tool_name,
            "approval_id": self.approval_id,
            "data": self.data,
        }
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

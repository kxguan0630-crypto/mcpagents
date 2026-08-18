"""人工审批的数据模型。

这里先只解决一个问题：Agent 在执行有副作用的工具之前，可以暂停，
等待用户确认。

这个模块不负责 UI，也不负责 Redis。它只描述“审批请求是什么”。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ApprovalRequest:
    """等待用户确认的一次工具调用。"""

    approval_id: str
    session_id: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    message: str = "请确认是否继续执行此操作。"


@dataclass
class ApprovalDecision:
    """用户对审批请求作出的决定。"""

    approval_id: str
    approved: bool
    reason: str | None = None

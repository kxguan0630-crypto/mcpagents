"""Agent 执行过程中的人工审批运行时门。

这个模块只解决一个非常明确的问题：
当 Agent 准备执行一个被策略标记为“需要确认”的工具时，先暂停。

注意：它不负责 HTTP、SSE、Redis，也不负责决定哪些工具需要审批。
这些职责分别属于 api、approval_store 和 approval_policy。
"""

from dataclasses import dataclass
from typing import Any

from .approval import ApprovalRequest
from .approval_manager import ApprovalManager


@dataclass
class ApprovalRequired:
    """表示 Agent 当前不能继续，需要用户确认。"""

    request: ApprovalRequest


class ApprovalRuntime:
    """在工具执行前检查是否需要人工确认。"""

    def __init__(self, manager: ApprovalManager) -> None:
        self.manager = manager

    async def check(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ApprovalRequired | None:
        """如果工具需要审批，创建请求并返回；否则返回 None。"""
        if not self.manager.requires_approval(tool_name):
            return None

        request = await self.manager.create_request(
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
        )
        return ApprovalRequired(request=request)

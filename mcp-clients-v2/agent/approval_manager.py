"""人工审批流程的业务服务。

它负责创建、查询和消费审批请求。
Agent Graph 只需要依赖这个服务，不需要知道请求保存在哪里。
"""

from uuid import uuid4

from .approval import ApprovalDecision, ApprovalRequest
from .approval_policy import ApprovalPolicy
from .approval_store import ApprovalStore


class ApprovalManager:
    """审批流程的应用服务。"""

    def __init__(self, store: ApprovalStore, policy: ApprovalPolicy) -> None:
        self.store = store
        self.policy = policy

    def requires_approval(self, tool_name: str) -> bool:
        """判断指定工具是否需要用户确认。"""
        return self.policy.requires_approval(tool_name)

    async def create_request(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict,
    ) -> ApprovalRequest:
        """创建一个待用户确认的工具调用请求。"""
        request = ApprovalRequest(
            approval_id=uuid4().hex,
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            message=f"Agent 准备调用工具 {tool_name}，是否允许继续？",
        )
        await self.store.save(request)
        return request

    async def get_request(self, approval_id: str) -> ApprovalRequest | None:
        """读取审批请求，但不删除它。"""
        return await self.store.get(approval_id)

    async def delete_request(self, approval_id: str) -> None:
        """在 Agent 成功消费审批决定后删除请求。"""
        await self.store.delete(approval_id)

    async def decide(self, decision: ApprovalDecision) -> ApprovalRequest | None:
        """兼容简单场景：读取并立即消费审批请求。"""
        request = await self.get_request(decision.approval_id)
        if request is not None:
            await self.delete_request(decision.approval_id)
        return request

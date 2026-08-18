"""人工审批流程的业务服务。

它负责创建、查询和消费审批请求。
Agent Graph 只需要依赖这个服务，不需要知道请求保存在哪里。
"""

from hashlib import sha256

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

    @staticmethod
    def make_stable_approval_id(session_id: str, tool_call_id: str) -> str:
        """为一次 LangGraph tool call 生成稳定 ID。

        LangGraph 从 interrupt 恢复时，会重新执行 interrupt 所在节点之前的代码。
        如果这里每次都 uuid4()，恢复后会创建第二个审批请求并再次暂停。
        因此审批 ID 必须和原始 tool call 绑定，而不能每次重新随机生成。
        """
        raw = f"{session_id}:{tool_call_id}".encode("utf-8")
        return sha256(raw).hexdigest()[:32]

    async def create_request(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict,
        approval_id: str | None = None,
    ) -> ApprovalRequest:
        """创建待确认请求；如果同一调用已经存在，则复用原请求。"""
        if approval_id:
            existing = await self.store.get(approval_id)
            if existing is not None:
                return existing

        request = ApprovalRequest(
            approval_id=approval_id or self.make_stable_approval_id(session_id, tool_name),
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
        """读取审批请求，但把删除动作留给 resume 成功之后。

        这样用户点击确认后，即使 Agent resume 暂时失败，审批请求仍然存在，
        可以安全重试，而不会出现“已经批准但状态丢失”的问题。
        """
        return await self.get_request(decision.approval_id)

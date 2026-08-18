"""人工审批 HTTP 路由。

这一层只做协议转换和调用 AgentService。
审批规则仍然在 agent/ 中，LangGraph resume 也由 AgentService 负责。
"""

from fastapi import APIRouter, HTTPException

from agent.approval_manager import ApprovalManager
from agent.service import AgentService

from .approval_schemas import ApprovalDecisionRequest, ApprovalDecisionResponse


def create_approval_router(
    manager: ApprovalManager,
    agent_service: AgentService,
) -> APIRouter:
    """创建审批路由，并注入审批服务与 AgentService。"""
    router = APIRouter(prefix="/approvals", tags=["approvals"])

    @router.post("/decision", response_model=ApprovalDecisionResponse)
    async def decide(request: ApprovalDecisionRequest) -> ApprovalDecisionResponse:
        # 先读取但不删除审批请求，因为 resume 需要它对应的 session_id。
        approval_request = await manager.get_request(request.approval_id)
        if approval_request is None:
            raise HTTPException(status_code=404, detail="approval request not found")

        answer = await agent_service.resume(
            session_id=approval_request.session_id,
            approval_id=request.approval_id,
            approved=request.approved,
            reason=request.reason,
        )

        return ApprovalDecisionResponse(
            approval_id=request.approval_id,
            approved=request.approved,
            resumed=True,
            answer=answer,
        )

    return router

"""人工审批 HTTP 路由。

这一层只做协议转换：HTTP 请求 -> ApprovalDecision -> ApprovalManager。
真正的审批规则仍然在 agent/ 中。
"""

from fastapi import APIRouter, HTTPException

from agent.approval import ApprovalDecision
from agent.approval_manager import ApprovalManager

from .approval_schemas import ApprovalDecisionRequest, ApprovalDecisionResponse


def create_approval_router(manager: ApprovalManager) -> APIRouter:
    """创建审批路由，并注入审批服务。"""
    router = APIRouter(prefix="/approvals", tags=["approvals"])

    @router.post("/decision", response_model=ApprovalDecisionResponse)
    async def decide(request: ApprovalDecisionRequest) -> ApprovalDecisionResponse:
        decision = ApprovalDecision(
            approval_id=request.approval_id,
            approved=request.approved,
            reason=request.reason,
        )
        approval_request = await manager.decide(decision)

        if approval_request is None:
            raise HTTPException(status_code=404, detail="approval request not found")

        # 这一阶段先完成“审批请求生命周期”的闭环。
        # 真正的 Agent resume 会在下一阶段接入 checkpoint/thread。
        return ApprovalDecisionResponse(
            approval_id=request.approval_id,
            approved=request.approved,
            resumed=False,
        )

    return router

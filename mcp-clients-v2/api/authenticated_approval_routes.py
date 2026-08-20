"""带认证的人工审批路由。

审批恢复同样属于受保护操作，因此必须先通过 CSN 验证 Token，
再把 AuthContext 交给 AgentService.resume。
"""

from fastapi import APIRouter, Header, HTTPException

from agent.approval_manager import ApprovalManager
from agent.service import AgentService
from auth.context import AuthContext
from auth.verifier import AuthVerifier, AuthenticationError

from .approval_schemas import ApprovalDecisionRequest, ApprovalDecisionResponse


def create_authenticated_approval_router(
    manager: ApprovalManager,
    agent_service: AgentService,
    auth_verifier: AuthVerifier,
) -> APIRouter:
    """创建需要 Authorization Header 的审批路由。"""
    router = APIRouter(prefix="/approvals", tags=["approvals"])

    @router.post("/decision", response_model=ApprovalDecisionResponse)
    async def decide(
        request: ApprovalDecisionRequest,
        authorization: str | None = Header(default=None),
    ) -> ApprovalDecisionResponse:
        try:
            context: AuthContext = await auth_verifier.verify(authorization)
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        approval_request = await manager.get_request(request.approval_id)
        if approval_request is None:
            raise HTTPException(status_code=404, detail="approval request not found")

        answer = await agent_service.resume(
            session_id=approval_request.session_id,
            approval_id=request.approval_id,
            approved=request.approved,
            reason=request.reason,
            auth_context=context,
        )

        return ApprovalDecisionResponse(
            approval_id=request.approval_id,
            approved=request.approved,
            resumed=True,
            answer=answer,
        )

    return router

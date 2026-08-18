"""人工审批 HTTP 接口的数据结构。"""

from pydantic import BaseModel


class ApprovalDecisionRequest(BaseModel):
    """前端提交的审批决定。"""

    approval_id: str
    approved: bool
    reason: str | None = None


class ApprovalDecisionResponse(BaseModel):
    """审批接口返回结果。"""

    approval_id: str
    approved: bool
    resumed: bool

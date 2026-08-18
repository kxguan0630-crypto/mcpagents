"""审批恢复安全性的最小测试。

这里重点验证两个生产边界：
1. 同一个 tool call 必须得到同一个 approval_id。
2. 用户确认后，不能在 Agent resume 之前删除审批请求。
"""

import pytest

from agent.approval import ApprovalDecision
from agent.approval_manager import ApprovalManager
from agent.approval_policy import ApprovalPolicy
from agent.approval_store import InMemoryApprovalStore


@pytest.mark.asyncio
async def test_same_tool_call_reuses_approval_request() -> None:
    store = InMemoryApprovalStore()
    manager = ApprovalManager(store, ApprovalPolicy(frozenset({"create_case"})))

    approval_id = manager.make_stable_approval_id("session-1", "call-1")
    first = await manager.create_request(
        "session-1", "create_case", {"name": "demo"}, approval_id=approval_id
    )
    second = await manager.create_request(
        "session-1", "create_case", {"name": "demo"}, approval_id=approval_id
    )

    assert first.approval_id == second.approval_id
    assert first is second


@pytest.mark.asyncio
async def test_decide_does_not_delete_request_before_resume() -> None:
    store = InMemoryApprovalStore()
    manager = ApprovalManager(store, ApprovalPolicy(frozenset({"create_case"})))
    request = await manager.create_request(
        "session-1", "create_case", {}, approval_id="approval-1"
    )

    result = await manager.decide(
        ApprovalDecision(approval_id="approval-1", approved=True)
    )

    assert result == request
    assert await store.get("approval-1") == request

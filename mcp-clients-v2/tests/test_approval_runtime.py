"""人工审批运行时门的最小单元测试。"""

import pytest

from agent.approval_manager import ApprovalManager
from agent.approval_policy import ApprovalPolicy
from agent.approval_runtime import ApprovalRuntime
from agent.approval_store import InMemoryApprovalStore


@pytest.mark.asyncio
async def test_tool_without_approval_continues() -> None:
    manager = ApprovalManager(
        InMemoryApprovalStore(),
        ApprovalPolicy(frozenset()),
    )
    runtime = ApprovalRuntime(manager)

    result = await runtime.check("session-1", "query_patient", {})

    assert result is None


@pytest.mark.asyncio
async def test_tool_with_approval_creates_request() -> None:
    manager = ApprovalManager(
        InMemoryApprovalStore(),
        ApprovalPolicy(frozenset({"create_case"})),
    )
    runtime = ApprovalRuntime(manager)

    result = await runtime.check("session-1", "create_case", {"name": "demo"})

    assert result is not None
    assert result.request.tool_name == "create_case"
    assert result.request.session_id == "session-1"

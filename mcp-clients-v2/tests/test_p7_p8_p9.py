"""P7/P8/P9 的快速回归测试。

这些测试不依赖真实 LLM/MCP Server，专门验证 Runtime 的结构性契约。
"""

import asyncio

from agent.retry import retry_async
from agent.workflows.facts import build_workflow_fact_tools
from evals.cases import CASES
from evals.runner import evaluate


def test_internal_fact_tools_have_internal_metadata():
    tools = build_workflow_fact_tools()
    assert tools
    assert all(tool.metadata["visibility"] == "internal" for tool in tools)
    assert all(tool.metadata["category"] == "workflow_state" for tool in tools)


def test_eval_cases_cover_core_workflows():
    names = {case.name for case in CASES}
    assert "case_creation_must_check_patient_after_information" in names
    assert "order_with_design_skips_recipe_collection" in names
    assert "image_can_be_updated_after_order" in names


def test_eval_detects_missing_required_tool():
    case = CASES[0]
    result = evaluate(case, [])
    assert not result.passed
    assert "missing required tool: get_patients_by_name_and_phone" in result.failures


def test_eval_detects_forbidden_tool():
    case = CASES[1]
    result = evaluate(case, ["case_add"])
    assert not result.passed


def test_retry_async_recovers_from_transient_failure():
    calls = {"count": 0}

    async def operation():
        calls["count"] += 1
        if calls["count"] < 2:
            raise TimeoutError("temporary timeout")
        return "ok"

    async def run():
        return await retry_async(operation, attempts=2, base_delay=0)

    assert asyncio.run(run()) == "ok"
    assert calls["count"] == 2


def test_retry_async_does_not_retry_when_attempts_zero():
    calls = {"count": 0}

    async def operation():
        calls["count"] += 1
        raise RuntimeError("failure")

    async def run():
        try:
            await retry_async(operation, attempts=0, base_delay=0)
        except RuntimeError:
            return
        raise AssertionError("expected RuntimeError")

    asyncio.run(run())
    assert calls["count"] == 1

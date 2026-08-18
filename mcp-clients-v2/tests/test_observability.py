"""可观测性基础测试。

测试重点不是日志格式，而是 run 的生命周期：开始 -> 成功/失败 -> 耗时。
"""

from agent.observability import AgentRun


def test_run_finishes_with_duration():
    run = AgentRun(session_id="test-session")
    assert run.status == "running"
    assert run.duration_ms is None

    run.finish("success")

    assert run.status == "success"
    assert run.finished_at is not None
    assert run.duration_ms is not None


def test_run_records_error():
    run = AgentRun()
    run.finish("error", "tool failed")

    assert run.status == "error"
    assert run.error == "tool failed"

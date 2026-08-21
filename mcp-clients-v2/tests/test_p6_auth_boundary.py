"""P6 认证边界回归测试。

目标：保证 Token 是 Runtime 基础设施，而不是 AgentState、LangGraph config 或 LLM Tool 参数。
"""

from pathlib import Path


def test_graph_does_not_read_authorization_from_langgraph_config():
    graph_source = Path(__file__).parents[1].joinpath("agent", "graph.py").read_text(encoding="utf-8")

    assert 'configurable.get("authorization")' not in graph_source
    assert '"authorization" in getattr(tool, "args", {})' not in graph_source


def test_mcp_client_hides_and_overwrites_authorization():
    client_source = Path(__file__).parents[1].joinpath(
        "mcp_intergration", "client.py"
    ).read_text(encoding="utf-8")

    assert 'properties.pop("authorization", None)' in client_source
    assert 'runtime_arguments["authorization"] = auth_context.authorization' in client_source
    assert "get_auth_context()" in client_source


def test_agent_service_does_not_put_auth_in_graph_config():
    service_source = Path(__file__).parents[1].joinpath("agent", "service.py").read_text(encoding="utf-8")

    # Graph config 只应包含 checkpoint thread_id；认证上下文通过 ContextVar 传播。
    assert '"authorization":' not in service_source
    assert '"thread_id": session_id' in service_source

"""最小架构测试：确保 Agent 图可以构建。

这里不连接真实 MCP Server，也不调用真实模型。
"""

from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI

from agent.graph import build_agent_graph


def test_graph_builds():
    async def fake_tool(value: str) -> str:
        return value

    tool = StructuredTool.from_function(
        coroutine=fake_tool,
        name="fake_tool",
        description="A test tool",
    )
    llm = ChatOpenAI(api_key="test", base_url="http://localhost:1", model="test")
    graph = build_agent_graph(llm, [tool])

    assert graph is not None

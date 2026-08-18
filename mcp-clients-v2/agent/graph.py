"""Agent 图：LLM 决策 -> 工具执行 -> 回到 LLM。

这是整个项目最重要的文件。
注意：这里没有任何 `if tool_name == ...`。
模型决定是否调用工具以及调用哪个工具。
"""

from langchain_core.messages import SystemMessage
from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from .state import AgentState


SYSTEM_PROMPT = """你是企业业务助手。

你可以使用 MCP 提供的业务工具完成任务。
请遵循以下原则：
1. 先理解用户目标，再决定是否需要工具。
2. 工具返回结果后再继续推理，不要猜测业务数据。
3. 缺少关键参数时向用户询问，不要编造。
4. 完成任务后给用户清晰、简洁的结果。
"""


def build_agent_graph(llm: BaseChatModel, tools: list) -> StateGraph:
    """创建 Agent 图。

    图结构非常简单：

        START -> llm -> tools -> llm -> ... -> END

    这个结构就是主流 Agent 最核心的 ReAct 循环。
    """
    model = llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    async def call_model(state: AgentState):
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]

        response = await model.ainvoke(messages)
        return {"messages": [response], "step": state.get("step", 0) + 1}

    def should_use_tools(state: AgentState) -> str:
        last_message = state["messages"][-1]
        if getattr(last_message, "tool_calls", None):
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("llm", call_model)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "llm")
    graph.add_conditional_edges("llm", should_use_tools)
    graph.add_edge("tools", "llm")

    return graph.compile()

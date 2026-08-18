"""Agent 图：LLM 决策 -> 工具执行 -> 回到 LLM。

这是整个项目最重要的文件。
注意：这里没有任何 `if tool_name == ...`。
模型自己决定是否调用工具以及调用哪个工具。

本轮新增：
- 最大执行步数，防止异常情况下无限循环。
- ToolNode 统一承接工具错误，让错误回到 Agent，而不是直接炸掉整个进程。
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from .limits import AgentLimits
from .state import AgentState


SYSTEM_PROMPT = """你是企业业务助手。

你可以使用 MCP 提供的业务工具完成任务。
请遵循以下原则：
1. 先理解用户目标，再决定是否需要工具。
2. 工具返回结果后再继续推理，不要猜测业务数据。
3. 缺少关键参数时向用户询问，不要编造。
4. 如果工具返回错误，请根据错误重新判断；不要假装操作成功。
5. 完成任务后给用户清晰、简洁的结果。
"""


def build_agent_graph(
    llm: BaseChatModel,
    tools: list,
    limits: AgentLimits | None = None,
):
    """创建 Agent 图。

    图结构保持非常简单：

        START -> llm -> tools -> llm -> ... -> END

    这就是最核心的 ReAct 循环：模型决定，工具执行，结果再交给模型。
    """
    limits = limits or AgentLimits()
    limits.validate()

    # bind_tools 只告诉模型“有哪些能力”，并不决定具体调用哪一个工具。
    model = llm.bind_tools(tools)

    # ToolNode 根据模型产生的 tool_call 自动找到对应工具。
    # 这里仍然没有任何业务工具名称判断。
    tool_node = ToolNode(tools, handle_tool_errors=True)

    async def call_model(state: AgentState):
        """执行一次 LLM 推理。"""
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]

        response = await model.ainvoke(messages)
        return {"messages": [response], "step": state.get("step", 0) + 1}

    def should_continue(state: AgentState) -> str:
        """决定继续调用工具还是结束本轮 Agent。"""
        # step 是已经执行过的 LLM 次数。
        # 到达上限时强制结束，避免模型异常导致无限循环。
        if state.get("step", 0) >= limits.max_steps:
            return END

        last_message = state["messages"][-1]
        if getattr(last_message, "tool_calls", None):
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("llm", call_model)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "llm")
    graph.add_conditional_edges("llm", should_continue)
    graph.add_edge("tools", "llm")

    return graph.compile()

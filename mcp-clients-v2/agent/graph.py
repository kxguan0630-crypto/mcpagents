"""Agent 图：LLM 决策 -> 工具执行 -> 回到 LLM。

这是整个项目最重要的文件。

图结构仍然保持简单：

    START -> llm -> tools -> llm -> ... -> END

Human-in-the-loop：

    tools -> approval check -> interrupt -> resume -> tool

关键原则：
1. Agent 不硬编码具体业务工具名称。
2. 审批规则由 ApprovalPolicy 决定。
3. LangGraph 负责真正的暂停/恢复，不能自己用 while 循环模拟。
4. Checkpoint 由外部注入，Graph 不关心 Redis 或其他存储。
"""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .approval_runtime import ApprovalRuntime
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
    approval_runtime: ApprovalRuntime | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """创建 Agent 图。

    checkpointer 由应用启动层注入：
    - 本地开发可以传 MemorySaver。
    - 生产环境可以传 AsyncRedisSaver。

    Graph 本身不创建 Redis，也不管理连接生命周期。
    """
    limits = limits or AgentLimits()
    limits.validate()

    model = llm.bind_tools(tools)
    tool_map = {tool.name: tool for tool in tools}
    runtime = approval_runtime

    async def call_model(state: AgentState):
        """执行一次 LLM 推理。"""
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]

        response = await model.ainvoke(messages)
        return {"messages": [response], "step": state.get("step", 0) + 1}

    async def execute_tools(state: AgentState, config: dict[str, Any]):
        """执行 LLM 产生的工具调用。"""
        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", []) or []
        session_id = config["configurable"]["thread_id"]
        results = []

        for call in tool_calls:
            tool_name = call["name"]
            arguments = call.get("args", {})
            tool = tool_map.get(tool_name)
            if tool is None:
                results.append(
                    ToolMessage(
                        content=f"工具 {tool_name} 不存在。",
                        tool_call_id=call["id"],
                    )
                )
                continue

            if runtime is not None:
                approval = await runtime.check(
                    session_id=session_id,
                    tool_name=tool_name,
                    arguments=arguments,
                    tool_call_id=call["id"],
                )
                if approval is not None:
                    # interrupt 会把 Agent 状态交给 LangGraph Checkpoint。
                    # 注意：恢复时当前节点会重新执行，所以 ApprovalRuntime
                    # 必须复用同一个 tool_call_id 对应的审批请求。
                    decision = interrupt(
                        {
                            "type": "approval_required",
                            "approval_id": approval.request.approval_id,
                            "session_id": session_id,
                            "tool_name": tool_name,
                            "arguments": arguments,
                            "message": approval.request.message,
                        }
                    )
                    if not decision or not decision.get("approved", False):
                        results.append(
                            ToolMessage(
                                content="用户拒绝了这次工具调用。",
                                tool_call_id=call["id"],
                            )
                        )
                        continue

            try:
                result = await tool.ainvoke(arguments)
                results.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=call["id"],
                    )
                )
            except Exception as exc:
                results.append(
                    ToolMessage(
                        content=f"工具执行失败：{exc}",
                        tool_call_id=call["id"],
                    )
                )

        return {"messages": results}

    def should_continue(state: AgentState) -> str:
        """决定继续调用工具还是结束本轮 Agent。"""
        if state.get("step", 0) >= limits.max_steps:
            return END

        last_message = state["messages"][-1]
        if getattr(last_message, "tool_calls", None):
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("llm", call_model)
    graph.add_node("tools", execute_tools)
    graph.add_edge(START, "llm")
    graph.add_conditional_edges("llm", should_continue)
    graph.add_edge("tools", "llm")

    return graph.compile(checkpointer=checkpointer)

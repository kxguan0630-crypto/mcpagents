"""Agent 图：LLM 决策 -> 工具执行 -> 回到 LLM。

这是整个项目最重要的文件。

图结构仍然保持简单：

    START -> llm -> tools -> llm -> ... -> END

本轮增加 Human-in-the-loop：

    tools -> approval check -> interrupt -> resume -> tool

关键原则：
1. Agent 不硬编码具体业务工具名称。
2. 审批规则由 ApprovalPolicy 决定。
3. LangGraph 负责真正的暂停/恢复，不能自己用 while 循环模拟。
"""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
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
):
    """创建 Agent 图，并启用 LangGraph Checkpoint。

    MemorySaver 是本阶段专门用于演示 interrupt/resume 的最小实现。
    下一阶段如果要让暂停状态跨进程/多 worker 生存，应替换成持久化
    LangGraph checkpointer，而不是自己重新实现一套 resume 机制。
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
        """执行 LLM 产生的工具调用。

        Tool 名称只用于从 MCP 动态发现出来的 tool_map 中查找工具，
        这里没有任何业务判断，例如 create_case / create_order 等。
        """
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
                )
                if approval is not None:
                    # interrupt 会把 Agent 状态交给 LangGraph Checkpoint。
                    # 用户确认后，graph.ainvoke(Command(resume=...)) 会从这里继续。
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
                # 工具异常作为 ToolMessage 返回给 LLM，让 Agent 自己判断下一步。
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

    # interrupt/resume 必须依赖 LangGraph 的 checkpoint。
    return graph.compile(checkpointer=MemorySaver())

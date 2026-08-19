"""Agent 图：LLM + LangGraph + MCP Tools。

Graph 只负责通用 Agent Runtime：维护消息循环、调用模型、执行 Tool、处理审批和限制。
业务 Workflow 由 workflows/registry.py 提供；Graph 不通过具体业务 intent 做分支。

特别重要：Workflow 可以返回 RequiredAction。RequiredAction 是“必须执行的机器动作”，
不能依赖 LLM 自己决定是否调用。这样可以避免“模型说正在查询，但实际上没有调用接口”。
"""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.config import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .approval_runtime import ApprovalRuntime
from .limits import AgentLimits
from .state import AgentState
from .workflows.fact_handlers import apply_fact_tool
from .workflows.facts import build_workflow_fact_tools
from .workflows.implementations import build_default_workflow_registry
from .workflows.registry import WorkflowRegistry
from .workflows.tool_adapters import prepare_arguments

# 通用 Runtime 规则，不包含具体业务流程名称。
SYSTEM_PROMPT = """你是企业业务助手。

规则：
1. 理解用户的自然语言，不要猜测业务事实。
2. 用户明确表达业务意图后，使用内部 Workflow 意图工具记录意图。
3. 当前 Workflow 给出的阶段约束是确定性前置条件，必须遵守，不能跳过。
4. 用户明确提供的信息才能写入事实；MCP Tool 返回的数据才是外部业务事实。
5. Tool 执行失败时如实说明，不得把失败结果当成成功事实。
6. 需要用户决定时必须等待用户明确回答，不能替用户选择。
7. 不向用户暴露内部状态、checkpoint、Workflow 实现或运行时细节。
8. 如果当前 Workflow 有必须执行的机器动作，由 Runtime 自动执行；不要用自然语言假装已经执行。
"""


def _human_message(text: str, attachments: list[dict[str, Any]]) -> HumanMessage:
    """把 HTTP 输入转换成模型消息；图片只保存引用，不把二进制放入 AgentState。"""
    if not attachments:
        return HumanMessage(content=text)
    content: list[dict[str, Any]] = [{"type": "text", "text": text}]
    for item in attachments:
        url = item.get("url") or item.get("image_url")
        if url:
            content.append({"type": "image_url", "image_url": {"url": url}})
        else:
            ref = item.get("file_id") or item.get("fileId") or item.get("name") or "unknown"
            content.append({"type": "text", "text": f"[附件图片引用: {ref}]"})
    return HumanMessage(content=content)


def build_agent_graph(
    llm: BaseChatModel,
    tools: list,
    limits: AgentLimits | None = None,
    approval_runtime: ApprovalRuntime | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    workflow_registry: WorkflowRegistry | None = None,
):
    """创建可运行的 Agent Graph。

    ``workflow_registry`` 可由应用注入，默认使用产品内置 Workflow。
    Graph 本身不关心具体 Workflow 的数量和名称。
    """
    limits = limits or AgentLimits()
    limits.validate()
    workflow_registry = workflow_registry or build_default_workflow_registry()

    workflow_fact_tools = build_workflow_fact_tools()
    all_tools = [*tools, *workflow_fact_tools]
    model = llm.bind_tools(all_tools)
    tool_map = {tool.name: tool for tool in all_tools}

    async def call_model(state: AgentState):
        """执行一次 LLM 推理，并让当前 Workflow 提供最小确定性约束。"""
        messages = list(state.get("messages", []))
        facts = state.get("business_facts", {})
        intent = state.get("workflow_intent") or facts.get("workflow_intent")
        workflow = workflow_registry.resolve(intent)

        if not messages or not isinstance(messages[0], SystemMessage):
            messages.insert(0, SystemMessage(content=SYSTEM_PROMPT))

        hint = None
        if workflow is not None:
            messages.append(SystemMessage(content=workflow.instructions()))
            hint = workflow.next_step(facts)
            if hint:
                messages.append(SystemMessage(content=f"当前流程最小缺口：{hint}。只完成这个阶段，不要跳过前置条件。"))

        response = await model.ainvoke(messages)
        return {
            "messages": [response],
            "step": state.get("step", 0) + 1,
            "workflow_step": hint or "",
        }

    async def execute_tools(state: AgentState, config: RunnableConfig):
        """执行 LLM 产生的 Tool Call。

        这里处理模型主动调用的 Tool；Workflow 的 RequiredAction 不走 LLM Tool Call，
        而由 execute_required_action() 在下一节点确定性执行。
        """
        last_message = state["messages"][-1]
        facts = dict(state.get("business_facts", {}))
        attachments = state.get("attachments", [])
        results: list[ToolMessage] = []
        configurable = config.get("configurable", {})
        session_id = configurable.get("thread_id", "")
        authorization = configurable.get("authorization")
        intent = state.get("workflow_intent") or facts.get("workflow_intent")

        for call in getattr(last_message, "tool_calls", []) or []:
            tool_name = call["name"]
            arguments = prepare_arguments(tool_name, dict(call.get("args", {}) or {}), attachments)
            tool = tool_map.get(tool_name)
            if tool is None:
                results.append(ToolMessage(content=f"工具 {tool_name} 不存在。", tool_call_id=call["id"]))
                continue

            # 内部事实 Tool 不访问 MCP Server；具体字段处理集中在 fact_handlers.py。
            fact_message = apply_fact_tool(facts, tool_name, arguments)
            if fact_message is not None:
                results.append(ToolMessage(content=fact_message, tool_call_id=call["id"]))
                intent = facts.get("workflow_intent", intent)
                continue

            # authorization 是通用传输上下文，不属于任何业务 Workflow。
            if authorization and "authorization" in getattr(tool, "args", {}):
                arguments.setdefault("authorization", authorization)

            allowed, reason = workflow_registry.check_tool(intent, tool_name, facts, arguments)
            if not allowed:
                results.append(ToolMessage(content=f"流程门禁阻止本次工具调用：{reason}", tool_call_id=call["id"]))
                continue

            if approval_runtime is not None:
                approval = await approval_runtime.check(
                    session_id=session_id,
                    tool_name=tool_name,
                    arguments=arguments,
                    tool_call_id=call["id"],
                )
                if approval is not None:
                    decision = interrupt({
                        "type": "approval_required",
                        "approval_id": approval.request.approval_id,
                        "session_id": session_id,
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "message": approval.request.message,
                    })
                    if not decision or not decision.get("approved", False):
                        results.append(ToolMessage(content="用户拒绝了这次工具调用。", tool_call_id=call["id"]))
                        continue

            try:
                result = await tool.ainvoke(arguments)
                results.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
                # 只有真实 Tool 成功返回，才允许业务规则推进 business_facts。
                facts = workflow_registry.update_facts(facts, tool_name, result)
            except Exception as exc:
                results.append(ToolMessage(content=f"工具执行失败：{exc}", tool_call_id=call["id"]))

        return {
            "messages": results,
            "business_facts": facts,
            "workflow_intent": facts.get("workflow_intent", intent or ""),
        }

    async def execute_required_action(state: AgentState, config: RunnableConfig):
        """执行 Workflow 声明的 RequiredAction。

        这是本次修复的核心：如果业务流程要求“必须查询患者”，Runtime 会直接调用对应
        MCP Tool，而不是把“请查询患者”写进 Prompt 后期待 LLM 自己产生 Tool Call。
        """
        facts = dict(state.get("business_facts", {}))
        intent = state.get("workflow_intent") or facts.get("workflow_intent")
        action = workflow_registry.required_action(intent, facts)
        if action is None:
            return {"messages": [], "business_facts": facts}

        tool = tool_map.get(action.tool_name)
        if tool is None:
            message = ToolMessage(
                content=f"流程要求执行工具 {action.tool_name}，但当前 MCP Tool 集合中不存在该工具。",
                tool_call_id=f"required-{action.tool_name}",
            )
            return {"messages": [message], "business_facts": facts}

        configurable = config.get("configurable", {})
        authorization = configurable.get("authorization")
        arguments = prepare_arguments(action.tool_name, dict(action.arguments), state.get("attachments", []))
        if authorization and "authorization" in getattr(tool, "args", {}):
            arguments.setdefault("authorization", authorization)

        allowed, reason = workflow_registry.check_tool(intent, action.tool_name, facts, arguments)
        if not allowed:
            return {
                "messages": [ToolMessage(
                    content=f"流程门禁阻止自动动作：{reason}",
                    tool_call_id=f"required-{action.tool_name}",
                )],
                "business_facts": facts,
            }

        try:
            result = await tool.ainvoke(arguments)
            # 只有真实 MCP Tool 成功返回，Workflow 才能推进 patient_checked 等事实。
            facts = workflow_registry.update_facts(facts, action.tool_name, result)
            return {
                "messages": [ToolMessage(
                    content=str(result),
                    tool_call_id=f"required-{action.tool_name}",
                )],
                "business_facts": facts,
                "workflow_intent": facts.get("workflow_intent", intent or ""),
            }
        except Exception as exc:
            # 查询失败时绝不修改 patient_checked，下一轮仍会保留该必需动作。
            return {
                "messages": [ToolMessage(
                    content=f"自动业务动作执行失败：{exc}",
                    tool_call_id=f"required-{action.tool_name}",
                )],
                "business_facts": facts,
            }

    def should_continue(state: AgentState) -> str:
        """LLM 有 Tool Call 就进入 tools，否则结束当前轮。"""
        if state.get("step", 0) >= limits.max_steps:
            return END
        return "tools" if getattr(state["messages"][-1], "tool_calls", None) else END

    graph = StateGraph(AgentState)
    graph.add_node("llm", call_model)
    graph.add_node("tools", execute_tools)
    graph.add_node("required_action", execute_required_action)
    graph.add_edge(START, "llm")
    graph.add_conditional_edges("llm", should_continue)
    graph.add_edge("tools", "required_action")
    graph.add_edge("required_action", "llm")
    return graph.compile(checkpointer=checkpointer)

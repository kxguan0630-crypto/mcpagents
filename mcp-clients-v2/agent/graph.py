"""Agent 图：LLM + LangGraph + MCP Tools。

Graph 只负责 Agent Runtime：维护消息循环、调用模型、执行 Tool、处理审批和限制。
业务 Workflow 由 workflows/registry.py 提供；Graph 不再通过业务 intent 或 Tool 名称写 if/else。

一个重要原则：Workflow 声明的 RequiredAction 不经过 LLM 决策。
例如“患者信息和主诉齐全后必须查询患者”会由 Runtime 自动转成 Tool Call，
这样模型不能只说“系统正在查询”却不真正访问业务接口。

认证也是 Runtime 能力：Graph 不保存、不传递 authorization。
MCP Client 在真正执行 Tool 时从 AuthContext 自动注入已经验证过的 Token。
"""

from typing import Any
from uuid import uuid4

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
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

SYSTEM_PROMPT = """你是企业业务助手。

规则：
1. 理解用户的自然语言，不要猜测业务事实。
2. 用户明确表达业务意图后，使用内部 Workflow 意图工具记录意图。
3. 当前 Workflow 给出的阶段约束是确定性前置条件，必须遵守，不能跳过。
4. 用户明确提供的信息才能写入事实；MCP Tool 返回的数据才是外部业务事实。
5. Tool 执行失败时如实说明，不得把失败结果当成成功事实。
6. 需要用户决定时必须等待用户明确回答，不能替用户选择。
7. 不向用户暴露内部状态、checkpoint、Workflow 实现或运行时细节。
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
        """执行一次 LLM 推理，只负责理解用户和生成普通 Tool Call。"""
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

    def required_action_needed(state: AgentState) -> bool:
        """判断当前 Workflow 是否要求 Runtime 自动执行动作。"""
        facts = state.get("business_facts", {})
        intent = state.get("workflow_intent") or facts.get("workflow_intent")
        return workflow_registry.required_action(intent, facts) is not None

    async def create_required_tool_call(state: AgentState):
        """把 Workflow RequiredAction 转换成标准 AIMessage Tool Call。

        这里不调用 LLM。Tool 名称和参数来自 Workflow 的确定性规则，
        后续仍复用 execute_tools，因此审批、门禁、异常处理和事实更新保持一套实现。
        """
        facts = state.get("business_facts", {})
        intent = state.get("workflow_intent") or facts.get("workflow_intent")
        action = workflow_registry.required_action(intent, facts)
        if action is None:
            return {"messages": []}

        tool_call_id = f"workflow_{uuid4().hex}"
        message = AIMessage(
            content="",
            tool_calls=[{
                "name": action.tool_name,
                "args": action.arguments,
                "id": tool_call_id,
                "type": "tool_call",
            }],
        )
        return {"messages": [message]}

    async def execute_tools(state: AgentState, config: RunnableConfig):
        """执行 Tool，并把事实处理、Workflow 门禁与 MCP 调用分层。

        认证 Token 不从 LangGraph config 读取，也不写入 AgentState。
        MCP Client 会在真正调用 MCP Server 时从 AuthContext 自动注入 Token。
        """
        last_message = state["messages"][-1]
        facts = dict(state.get("business_facts", {}))
        attachments = state.get("attachments", [])
        results: list[ToolMessage] = []
        configurable = config.get("configurable", {})
        session_id = configurable.get("thread_id", "")
        intent = state.get("workflow_intent") or facts.get("workflow_intent")

        for call in getattr(last_message, "tool_calls", []) or []:
            tool_name = call["name"]
            arguments = prepare_arguments(tool_name, dict(call.get("args", {}) or {}), attachments)
            tool = tool_map.get(tool_name)
            if tool is None:
                results.append(ToolMessage(content=f"工具 {tool_name} 不存在。", tool_call_id=call["id"]))
                continue

            fact_message = apply_fact_tool(facts, tool_name, arguments)
            if fact_message is not None:
                results.append(ToolMessage(content=fact_message, tool_call_id=call["id"]))
                intent = facts.get("workflow_intent", intent)
                continue

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
                facts = workflow_registry.update_facts(facts, tool_name, result)
            except Exception as exc:
                results.append(ToolMessage(content=f"工具执行失败：{exc}", tool_call_id=call["id"]))

        return {
            "messages": results,
            "business_facts": facts,
            "workflow_intent": facts.get("workflow_intent", intent or ""),
        }

    def after_llm(state: AgentState) -> str:
        """LLM 后先检查 Workflow 必须动作，再处理模型自己的 Tool Call。"""
        if state.get("step", 0) >= limits.max_steps:
            return END
        if required_action_needed(state):
            return "required_action"
        return "tools" if getattr(state["messages"][-1], "tool_calls", None) else END

    graph = StateGraph(AgentState)
    graph.add_node("llm", call_model)
    graph.add_node("required_action", create_required_tool_call)
    graph.add_node("tools", execute_tools)
    graph.add_edge(START, "llm")
    graph.add_conditional_edges("llm", after_llm)
    graph.add_edge("required_action", "tools")
    graph.add_edge("tools", "llm")
    return graph.compile(checkpointer=checkpointer)

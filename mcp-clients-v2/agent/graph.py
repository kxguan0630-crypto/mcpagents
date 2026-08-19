"""Agent 图：LLM + LangGraph + 业务流程门禁 + MCP Tools。

核心职责分层：

    LLM
      ↓ 负责理解自然语言、收集信息、识别用户意图
    LangGraph
      ↓ 负责状态、节点、循环、checkpoint
    Workflow Rules
      ↓ 负责确定性的业务前置条件和当前业务阶段
    MCP Tools
      ↓ 负责真正执行后端业务

重要原则：business_facts 是唯一业务事实来源。
LLM 的判断不能直接修改业务事实；用户决定必须通过 record_* 工具记录，
MCP Tool 的事实必须通过 update_facts() 从真实工具结果产生。
"""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .approval_runtime import ApprovalRuntime
from .limits import AgentLimits
from .state import AgentState
from .workflows.case_creation import next_required_question as next_case_question
from .workflows.facts import build_workflow_fact_tools
from .workflows.order_creation import next_required_question as next_order_question
from .workflows.rules import (
    case_add_allowed,
    image_update_allowed,
    order_create_allowed,
    update_facts,
)


SYSTEM_PROMPT = """你是企业业务助手。

架构规则：
1. 你负责理解用户表达、收集缺失信息和识别用户意图。
2. LangGraph 和业务规则负责确定性的流程控制；不要通过猜测跳过前置条件。
3. MCP Tool 返回的数据才是业务事实，不要编造工具结果。
4. 病例创建：必须先收集患者基本信息和主诉，再调用 get_patients_by_name_and_phone；
   查询完成后根据真实查询结果处理患者选择。找到患者时必须让用户明确选择新建患者还是使用已有患者；
   没找到患者时可以进入新建患者路径，但仍然必须记录明确的患者决定。
5. 订单创建：诊断、影像、模型每次都必须询问用户是否提供；用户可以选择不提供。
   用户明确回答后，先使用 record_order_decisions 记录决定，再继续后续业务工具。
6. 影像可以在订单创建过程中提供，也可以在订单创建完成后独立补充/更新。
   用户上传图片后，应把图片交给 image_process 识别，而不是假装已经识别。
7. need_design=1 表示需要象贝设计：完全跳过处方信息收集。
   need_design=0 表示不需要象贝设计：必须询问用户是否提供处方，再根据决定继续。
8. 模型信息只能通过业务工具规定的口扫软件流程处理。
9. 缺少关键参数时向用户询问，不要编造。
10. 工具执行失败时如实说明，并根据错误重新判断。

对话要自然，不要向用户暴露内部状态名、checkpoint、Workflow Engine 等实现细节。
"""


def _human_message(text: str, attachments: list[dict[str, Any]]) -> HumanMessage:
    """把前端输入转换成 LangChain 消息。"""
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
):
    """创建 Agent 图。"""
    limits = limits or AgentLimits()
    limits.validate()

    # Agent 内部事实工具不访问业务 API，只把用户明确决定写入 business_facts。
    workflow_fact_tools = build_workflow_fact_tools()
    all_tools = [*tools, *workflow_fact_tools]
    model = llm.bind_tools(all_tools)
    tool_map = {tool.name: tool for tool in all_tools}
    runtime = approval_runtime

    async def call_model(state: AgentState):
        """执行一次 LLM 推理，并注入当前流程的最小缺口。"""
        messages = state["messages"]
        facts = state.get("business_facts", {})
        workflow_intent = state.get("workflow_intent")
        workflow_hint = None

        # Workflow 只提供“下一步缺口”，不负责生成面向用户的话术。
        if workflow_intent == "case_creation":
            workflow_hint = next_case_question(facts)
        elif workflow_intent == "order_creation":
            workflow_hint = next_order_question(facts, facts.get("need_design"))

        workflow_message = None
        if workflow_hint:
            workflow_message = SystemMessage(
                content=(
                    "当前业务流程的下一个必需阶段是："
                    f"{workflow_hint}。只围绕这个阶段完成当前用户交互；"
                    "不要跳到后面的提交步骤。自然语言由你生成。"
                )
            )

        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]
        if workflow_message:
            messages = [*messages, workflow_message]

        response = await model.ainvoke(messages)
        return {"messages": [response], "step": state.get("step", 0) + 1}

    async def execute_tools(state: AgentState, config: dict[str, Any]):
        """执行工具调用，并在执行前检查确定性的业务门禁。"""
        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", []) or []
        session_id = config["configurable"]["thread_id"]
        facts = dict(state.get("business_facts", {}))
        attachments = state.get("attachments", [])
        results = []

        for call in tool_calls:
            tool_name = call["name"]
            arguments = dict(call.get("args", {}) or {})
            tool = tool_map.get(tool_name)

            if tool is None:
                results.append(ToolMessage(content=f"工具 {tool_name} 不存在。", tool_call_id=call["id"]))
                continue

            # 用户决定只能通过内部 fact tool 写入，不能由 LLM 直接改 state。
            if tool_name == "record_order_decisions":
                for key in ("diagnosis_decision", "image_decision", "model_decision", "recipe_decision"):
                    if arguments.get(key) is not None:
                        facts[key] = arguments[key]
                results.append(ToolMessage(content="订单信息提供决定已记录。", tool_call_id=call["id"]))
                continue

            if tool_name == "record_patient_decision":
                facts["patient_decision"] = arguments["patient_decision"]
                results.append(ToolMessage(content="患者选择已记录。", tool_call_id=call["id"]))
                continue

            # 前端图片引用已经进入 AgentState；image_process 没有显式 image_list 时自动补上。
            if tool_name == "image_process" and not arguments.get("image_list") and attachments:
                arguments["image_list"] = attachments

            allowed = True
            reason = ""
            if tool_name == "case_add":
                allowed, reason = case_add_allowed(facts, arguments)
            elif tool_name == "case_order_add":
                allowed, reason = order_create_allowed(facts, arguments)
            elif tool_name == "save_case_face":
                allowed, reason = image_update_allowed(facts, arguments)

            if not allowed:
                results.append(ToolMessage(content=f"流程门禁阻止本次工具调用：{reason}", tool_call_id=call["id"]))
                continue

            if runtime is not None:
                approval = await runtime.check(
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
                # 只有工具真实成功返回，才允许改变业务事实。
                facts = update_facts(facts, tool_name, result)
            except Exception as exc:
                results.append(ToolMessage(content=f"工具执行失败：{exc}", tool_call_id=call["id"]))

        return {"messages": results, "business_facts": facts}

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

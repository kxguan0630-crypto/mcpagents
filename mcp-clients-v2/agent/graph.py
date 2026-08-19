"""Agent 图：LLM + LangGraph + 业务流程门禁 + MCP Tools。

核心职责分层：

    LLM
      ↓ 负责理解自然语言、提取信息、决定用户意图
    LangGraph
      ↓ 负责状态、节点、循环、checkpoint
    Workflow Rules
      ↓ 负责确定性的业务前置条件
    MCP Tools
      ↓ 负责真正执行后端业务

本文件不把完整业务流程硬编码成一条工具链。
但是，用户明确做出的“新建/已有患者”和“提供/不提供诊断、影像、模型、处方”
必须先被记录成结构化状态，否则后面的业务门禁不允许提交。
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
from .workflows.facts import build_workflow_fact_tools
from .workflows.rules import (
    case_add_allowed,
    image_update_allowed,
    order_create_allowed,
    update_facts,
)


SYSTEM_PROMPT = """你是企业业务助手。

架构规则：
1. 你负责理解用户表达、收集缺失信息和决定用户意图。
2. LangGraph 和业务规则负责确定性的流程控制；不要通过猜测跳过前置条件。
3. MCP Tool 返回的数据才是业务事实，不要编造工具结果。
4. 病例创建：必须先收集患者基本信息和主诉，再调用 get_patients_by_name_and_phone；
   查询完成后必须让用户明确选择新建患者还是使用已有患者，然后记录这个决定，之后才能 case_add。
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

    # MCP 工具之外，再给 LLM 两个非常小的“状态记录工具”。
    # 它们不访问 Server，只把用户已经明确表达的决定写入 business_facts。
    workflow_fact_tools = build_workflow_fact_tools()
    all_tools = [*tools, *workflow_fact_tools]
    model = llm.bind_tools(all_tools)
    tool_map = {tool.name: tool for tool in all_tools}
    runtime = approval_runtime

    async def call_model(state: AgentState):
        """执行一次 LLM 推理。"""
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]
        response = await model.ainvoke(messages)
        return {"messages": [response], "step": state.get("step", 0) + 1}

    async def execute_tools(state: AgentState, config: dict[str, Any]):
        """执行工具调用，并在执行前检查确定性的业务门禁。"""
        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", []) or []
        session_id = config["configurable"]["thread_id"]
        facts = state.get("business_facts", {})
        attachments = state.get("attachments", [])
        results = []

        for call in tool_calls:
            tool_name = call["name"]
            arguments = dict(call.get("args", {}) or {})
            tool = tool_map.get(tool_name)

            if tool is None:
                results.append(ToolMessage(content=f"工具 {tool_name} 不存在。", tool_call_id=call["id"]))
                continue

            # 内部状态工具只记录用户明确做出的决定，不走 MCP，也不需要审批。
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

            # 图片上传是 HTTP/Input 层能力；image_process 是识别工具。
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

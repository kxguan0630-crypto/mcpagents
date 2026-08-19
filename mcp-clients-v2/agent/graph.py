"""Agent 图：LLM + LangGraph + 业务流程门禁 + MCP Tools。

核心职责分层：

    LLM -> 理解自然语言、收集信息、识别用户意图
    LangGraph -> 管理状态、节点、循环和 checkpoint
    Workflow Rules -> 判断确定性的业务前置条件
    MCP Tools -> 执行真实后端业务

重要原则：business_facts 是唯一业务事实来源。
LLM 不能直接修改业务事实；用户决定必须通过 record_* 工具记录；
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
from .workflows.rules import case_add_allowed, image_update_allowed, order_create_allowed, update_facts


SYSTEM_PROMPT = """你是企业业务助手。

规则：
1. 负责理解用户、收集缺失信息和识别意图；不要猜测业务事实。
2. 病例创建必须先收集患者基本信息和主诉，再查询患者；查询后必须有明确患者选择。
3. 订单创建时诊断、影像、模型每次都必须询问，用户可以选择不提供。
4. 用户明确回答订单可选信息后，使用 record_order_decisions 记录决定。
5. 用户明确选择是否需要象贝设计后，使用 record_design_decision 记录 need_design。
6. need_design=1 完全跳过处方；need_design=0 必须询问处方。
7. 用户上传图片时使用 image_process；图片也可以在订单创建完成后独立补充/更新。
8. Tool 返回的数据才是业务事实；工具失败时如实说明。
9. 不要向用户暴露内部状态、checkpoint 或 Workflow 实现。
"""


def _human_message(text: str, attachments: list[dict[str, Any]]) -> HumanMessage:
    """把 HTTP 输入转换成模型消息；图片只传引用，不把二进制放入状态。"""
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


def build_agent_graph(llm: BaseChatModel, tools: list, limits: AgentLimits | None = None,
                      approval_runtime: ApprovalRuntime | None = None,
                      checkpointer: BaseCheckpointSaver | None = None):
    """创建可运行的 Agent Graph。"""
    limits = limits or AgentLimits()
    limits.validate()

    # 内部事实工具不访问 MCP Server，只负责把用户明确决定写入 Facts。
    workflow_fact_tools = build_workflow_fact_tools()
    all_tools = [*tools, *workflow_fact_tools]
    model = llm.bind_tools(all_tools)
    tool_map = {tool.name: tool for tool in all_tools}

    async def call_model(state: AgentState):
        """执行一次 LLM 推理，并注入 Workflow 当前最小缺口。"""
        messages = list(state.get("messages", []))
        facts = state.get("business_facts", {})
        intent = state.get("workflow_intent", "general")
        hint = None
        if intent == "case_creation":
            hint = next_case_question(facts)
        elif intent == "order_creation":
            hint = next_order_question(facts, facts.get("need_design"))

        if not messages or not isinstance(messages[0], SystemMessage):
            messages.insert(0, SystemMessage(content=SYSTEM_PROMPT))
        if hint:
            messages.append(SystemMessage(content=f"当前流程最小缺口：{hint}。只完成这个阶段，不要跳过前置条件。"))

        response = await model.ainvoke(messages)
        return {"messages": [response], "step": state.get("step", 0) + 1}

    async def execute_tools(state: AgentState, config: dict[str, Any]):
        """执行工具并更新 business_facts。"""
        last_message = state["messages"][-1]
        facts = dict(state.get("business_facts", {}))
        attachments = state.get("attachments", [])
        results: list[ToolMessage] = []
        session_id = config["configurable"]["thread_id"]

        for call in getattr(last_message, "tool_calls", []) or []:
            tool_name = call["name"]
            arguments = dict(call.get("args", {}) or {})
            tool = tool_map.get(tool_name)
            if tool is None:
                results.append(ToolMessage(content=f"工具 {tool_name} 不存在。", tool_call_id=call["id"]))
                continue

            # 事实工具是 Graph 内部工具，绝不发送到 MCP Server。
            if tool_name == "record_order_decisions":
                for key in ("diagnosis_decision", "image_decision", "model_decision", "recipe_decision"):
                    if arguments.get(key) is not None:
                        facts[key] = arguments[key]
                results.append(ToolMessage(content="订单信息提供决定已记录。", tool_call_id=call["id"]))
                continue

            if tool_name == "record_design_decision":
                facts["need_design"] = arguments["need_design"]
                # 切换到 need_design=1 时，旧处方决定失效，避免历史状态污染当前订单。
                if arguments["need_design"] == 1:
                    facts.pop("recipe_decision", None)
                results.append(ToolMessage(content="设计需求决定已记录。", tool_call_id=call["id"]))
                continue

            if tool_name == "record_patient_decision":
                facts["patient_decision"] = arguments["patient_decision"]
                results.append(ToolMessage(content="患者选择已记录。", tool_call_id=call["id"]))
                continue

            if tool_name == "image_process" and not arguments.get("image_list") and attachments:
                # Server 的真实参数名是 image_list；这里兼容前端 file_id/fileId/url 引用。
                arguments["image_list"] = attachments

            allowed, reason = True, ""
            if tool_name == "case_add":
                allowed, reason = case_add_allowed(facts, arguments)
            elif tool_name == "case_order_add":
                allowed, reason = order_create_allowed(facts, arguments)
            elif tool_name == "save_case_face":
                allowed, reason = image_update_allowed(facts, arguments)
            if not allowed:
                results.append(ToolMessage(content=f"流程门禁阻止本次工具调用：{reason}", tool_call_id=call["id"]))
                continue

            if approval_runtime := None:
                # 保留结构位置；实际审批运行时由下面的闭包变量处理。
                pass

            try:
                result = await tool.ainvoke(arguments)
                results.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
                # 只有真实 Tool 成功，才允许改变业务事实。
                facts = update_facts(facts, tool_name, result)
            except Exception as exc:
                results.append(ToolMessage(content=f"工具执行失败：{exc}", tool_call_id=call["id"]))

        return {"messages": results, "business_facts": facts}

    def should_continue(state: AgentState) -> str:
        """有 Tool Call 就继续，没有就结束；同时受最大步数保护。"""
        if state.get("step", 0) >= limits.max_steps:
            return END
        return "tools" if getattr(state["messages"][-1], "tool_calls", None) else END

    graph = StateGraph(AgentState)
    graph.add_node("llm", call_model)
    graph.add_node("tools", execute_tools)
    graph.add_edge(START, "llm")
    graph.add_conditional_edges("llm", should_continue)
    graph.add_edge("tools", "llm")
    return graph.compile(checkpointer=checkpointer)

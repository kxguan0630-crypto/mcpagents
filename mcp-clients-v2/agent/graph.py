"""Agent 图：LLM + LangGraph + 业务流程门禁 + MCP Tools。

核心职责分层：

    LLM
      ↓ 负责理解自然语言、提取信息、决定用户意图
    LangGraph
      ↓ 负责状态、节点、循环、interrupt/resume、checkpoint
    Workflow Rules
      ↓ 负责确定性的业务前置条件
    MCP Tools
      ↓ 负责真正执行后端业务

本文件不再根据具体业务工具名“硬编码一个完整流程”。
工具名只在安全门禁和事实记录处出现，因为这些是确定性的业务不变量。
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
from .workflows.rules import case_add_allowed, order_create_allowed, update_facts


SYSTEM_PROMPT = """你是企业业务助手。

架构规则：
1. 你负责理解用户表达、收集缺失信息和决定用户意图。
2. LangGraph 和业务规则负责确定性的流程控制；不要通过猜测跳过前置条件。
3. MCP Tool 返回的数据才是业务事实，不要编造工具结果。
4. 病例创建：必须先收集患者基本信息和主诉，再调用 get_patients_by_name_and_phone；
   查询完成后必须让用户决定新建患者还是使用已有患者，之后才能 case_add。
5. 订单创建：诊断信息、影像资料每次都必须询问用户是否提供；用户可以选择不提供。
6. 影像可以在订单创建过程中提供，也可以在订单创建完成后独立补充/更新。
   用户上传图片后，应把图片交给 image_process 识别，而不是假装已经识别。
7. need_design=1 表示需要象贝设计：跳过处方信息收集。
   need_design=0 表示不需要象贝设计：进入处方信息收集流程。
8. 模型信息只能通过业务工具规定的口扫软件流程处理。
9. 缺少关键参数时向用户询问，不要编造。
10. 工具执行失败时如实说明，并根据错误重新判断。

对话要自然，不要向用户暴露内部状态名、checkpoint、Workflow Engine 等实现细节。
"""


def _human_message(text: str, attachments: list[dict[str, Any]]) -> HumanMessage:
    """把前端输入转换成 LangChain 消息。

    URL 型图片可以直接作为多模态消息的一部分交给支持视觉的模型。
    file_id 等平台引用则同时保留在 AgentState.attachments，供 image_process 使用。
    """
    if not attachments:
        return HumanMessage(content=text)

    content: list[dict[str, Any]] = [{"type": "text", "text": text}]
    for item in attachments:
        url = item.get("url") or item.get("image_url")
        if url:
            content.append({"type": "image_url", "image_url": {"url": url}})
        else:
            # file_id 可能只对业务后端可见，所以不要伪造一个模型无法访问的 URL。
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
    """创建 Agent 图。

    Graph 本身不创建 Redis，也不管理连接生命周期；checkpoint 由应用启动层注入。
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
        """执行 LLM 产生的工具调用，并在执行前检查确定性的业务门禁。"""
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

            # 图片上传是 HTTP/Input 层能力；image_process 是识别工具。
            # 如果模型没有重复传 image_list，则由 Agent 自动把当前请求附件传给工具。
            if tool_name == "image_process" and not arguments.get("image_list") and attachments:
                arguments["image_list"] = attachments

            allowed = True
            reason = ""
            if tool_name == "case_add":
                allowed, reason = case_add_allowed(facts, arguments)
            elif tool_name == "case_order_add":
                allowed, reason = order_create_allowed(facts, arguments)

            if not allowed:
                results.append(
                    ToolMessage(
                        content=f"流程门禁阻止本次工具调用：{reason}",
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
                        results.append(ToolMessage(content="用户拒绝了这次工具调用。", tool_call_id=call["id"]))
                        continue

            try:
                result = await tool.ainvoke(arguments)
                results.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
                facts = update_facts(facts, tool_name)
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

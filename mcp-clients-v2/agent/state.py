"""Agent 共享状态。

状态只保存“事实”和“用户已经明确做出的决定”。
不要把整个业务流程藏在一个字符串里，也不要把图片二进制放进 checkpoint。
"""

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """一次 Agent 执行需要共享的数据。"""

    # LangGraph 的消息累加器：每轮用户输入和模型/工具消息都会追加。
    messages: Annotated[list, add_messages]

    # 防止异常情况下 LLM 无限循环调用工具。
    step: int

    # 已由成功 MCP Tool 证明的业务事实。
    business_facts: dict[str, Any]

    # 当前请求携带的文件/图片引用；只保存 file_id、url 等元数据。
    attachments: list[dict[str, Any]]

    # LLM 识别出的业务意图，例如 create_case、create_order、update_image。
    # 意图本身不是业务事实，不能替代 Workflow 门禁。
    workflow_intent: str

    # 病例流程中的用户决定。
    patient_decision: str

    # 订单流程中的用户决定。
    need_design: int
    diagnosis_decision: str
    image_decision: str
    model_decision: str
    recipe_decision: str

    # 当前订单阶段；仅用于可读性和调试，不作为第二套状态机。
    workflow_step: str

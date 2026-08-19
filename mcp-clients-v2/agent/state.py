"""Agent 共享状态。

设计原则：
1. AgentState 是运行容器，不保存第二套业务状态机。
2. business_facts 是病例/订单 Workflow 的唯一业务事实来源。
3. 用户决定和 MCP Tool 结果都必须最终落到 business_facts。
4. 图片二进制不进入 checkpoint，只保存前端提供的引用。
"""

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """一次 Agent 执行过程中需要共享的数据。"""

    # LangGraph 的消息累加器：保存用户、模型和工具消息，支持多轮工具调用。
    messages: Annotated[list, add_messages]

    # 防止异常情况下模型无限循环调用工具。
    step: int

    # 病例/订单的唯一业务事实来源。
    # 例如 patient_decision、need_design、diagnosis_decision 都只放这里。
    business_facts: dict[str, Any]

    # 当前请求携带的文件/图片引用；只保存 file_id、url 等元数据，避免 checkpoint 变大。
    attachments: list[dict[str, Any]]

    # LLM 识别出的业务意图，例如 create_case、create_order、update_image。
    # 意图只是路由提示，不是业务事实，也不能绕过 Workflow 门禁。
    workflow_intent: str

    # 当前阶段名称仅用于调试/观测；真正的流程判断由 workflows/*.py 完成。
    workflow_step: str

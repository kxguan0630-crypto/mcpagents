"""把用户已经明确做出的流程决定记录到 AgentState。

这些不是 MCP 业务工具，而是 Agent 内部的小工具。
它们不访问后端，只负责把“用户说了什么决定”变成结构化状态。

为什么需要它？

LLM 的自然语言消息不能直接作为可靠的业务状态。订单创建又要求每次明确询问
诊断、影像、模型，以及在 need_design=0 时询问处方，所以必须有一个清晰的地方
保存这些决定。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Decision = Literal["provide", "skip"]


class RecordOrderDecisionsInput(BaseModel):
    """记录用户对订单可选信息的明确决定。"""

    diagnosis_decision: Decision | None = Field(default=None, description="诊断：provide=提供，skip=不提供")
    image_decision: Decision | None = Field(default=None, description="影像：provide=提供，skip=不提供")
    model_decision: Decision | None = Field(default=None, description="模型：provide=提供，skip=不提供")
    recipe_decision: Decision | None = Field(default=None, description="处方：provide=提供，skip=不提供")


class RecordPatientDecisionInput(BaseModel):
    """记录用户对患者选择的决定。"""

    patient_decision: Literal["new", "existing"] = Field(
        description="new=新建患者，existing=使用已有患者"
    )


def build_workflow_fact_tools():
    """创建 Agent 内部工具。

    返回值使用普通函数，避免引入复杂的 Agent Framework 抽象。
    graph.py 会拦截这两个工具，不会把它们发送到 MCP Server。
    """
    from langchain_core.tools import StructuredTool

    return [
        StructuredTool.from_function(
            name="record_order_decisions",
            description=(
                "记录用户已经明确表达的订单信息提供决定。只有用户明确说提供或不提供时才能调用。"
            ),
            args_schema=RecordOrderDecisionsInput,
            func=lambda **kwargs: kwargs,
        ),
        StructuredTool.from_function(
            name="record_patient_decision",
            description="记录用户已经明确选择新建患者或使用已有患者。不能根据猜测调用。",
            args_schema=RecordPatientDecisionInput,
            func=lambda **kwargs: kwargs,
        ),
    ]

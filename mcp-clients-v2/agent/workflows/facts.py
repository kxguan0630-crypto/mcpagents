"""把用户已经明确做出的流程决定记录到 AgentState。

这些不是 MCP 业务工具，而是 Agent 内部的小工具。
它们不访问后端，只负责把“用户说了什么决定”变成结构化状态。

核心原则：LLM 只能提出结构化的“记录决定”调用，Graph 才负责把它写入
business_facts。这样业务状态不会因为普通文本推理而被隐式修改。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Decision = Literal["provide", "skip"]
DesignDecision = Literal[0, 1]


class RecordOrderDecisionsInput(BaseModel):
    """记录用户对订单可选信息的明确决定。"""

    diagnosis_decision: Decision | None = Field(default=None, description="诊断：provide=提供，skip=不提供")
    image_decision: Decision | None = Field(default=None, description="影像：provide=提供，skip=不提供")
    model_decision: Decision | None = Field(default=None, description="模型：provide=提供，skip=不提供")
    recipe_decision: Decision | None = Field(default=None, description="处方：provide=提供，skip=不提供")


class RecordDesignDecisionInput(BaseModel):
    """记录用户明确选择的设计需求。

    1 = 需要象贝设计，因此完全跳过处方；
    0 = 不需要象贝设计，因此必须进入处方询问。
    """

    need_design: DesignDecision = Field(
        description="1=需要象贝设计，完全跳过处方；0=不需要象贝设计，需要询问处方"
    )


class RecordPatientDecisionInput(BaseModel):
    """记录用户对患者选择的决定。"""

    patient_decision: Literal["new", "existing"] = Field(
        description="new=新建患者，existing=使用已有患者"
    )


def build_workflow_fact_tools():
    """创建 Agent 内部事实工具。

    返回值使用普通 StructuredTool，避免引入额外 Agent Framework 抽象。
    graph.py 会拦截这些工具，不会把它们发送到 MCP Server。
    """
    from langchain_core.tools import StructuredTool

    return [
        StructuredTool.from_function(
            name="record_order_decisions",
            description="记录用户已经明确表达的订单信息提供决定。只有用户明确说提供或不提供时才能调用。",
            args_schema=RecordOrderDecisionsInput,
            func=lambda **kwargs: kwargs,
        ),
        StructuredTool.from_function(
            name="record_design_decision",
            description="记录用户已经明确选择是否需要象贝设计。need_design=1 完全跳过处方；0 才进入处方询问。",
            args_schema=RecordDesignDecisionInput,
            func=lambda **kwargs: kwargs,
        ),
        StructuredTool.from_function(
            name="record_patient_decision",
            description="记录用户已经明确选择新建患者或使用已有患者。不能根据猜测调用。",
            args_schema=RecordPatientDecisionInput,
            func=lambda **kwargs: kwargs,
        ),
    ]

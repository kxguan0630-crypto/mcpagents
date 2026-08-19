"""Agent 内部事实工具。

这些工具不访问 MCP Server，只把用户已经明确表达的结构化决定/信息写入 AgentState。
LLM 负责理解语言；Graph 负责真正落状态，避免普通文本被误认为业务事实。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Decision = Literal["provide", "skip"]
WorkflowIntent = Literal["case_creation", "order_creation", "update_image"]


class RecordWorkflowIntentInput(BaseModel):
    """记录用户当前明确的业务意图。"""

    workflow_intent: WorkflowIntent = Field(description="case_creation=病例、order_creation=订单、update_image=影像更新")


class RecordCaseInformationInput(BaseModel):
    """记录用户已经明确提供的病例创建信息。"""

    patient_name: str | None = Field(default=None, description="患者姓名")
    gender: int | None = Field(default=None, description="患者性别业务值")
    patient_phone: str | None = Field(default=None, description="患者手机号")
    age: str | None = Field(default=None, description="患者年龄")
    complaint: str | None = Field(default=None, description="患者主诉")
    complaint_other: str | None = Field(default=None, description="其它主诉说明")


class RecordOrderDecisionsInput(BaseModel):
    """记录用户对订单可选信息的明确决定。"""

    diagnosis_decision: Decision | None = Field(default=None, description="诊断：provide=提供，skip=不提供")
    image_decision: Decision | None = Field(default=None, description="影像：provide=提供，skip=不提供")
    model_decision: Decision | None = Field(default=None, description="模型：provide=提供，skip=不提供")
    recipe_decision: Decision | None = Field(default=None, description="处方：provide=提供，skip=不提供")


class RecordDesignDecisionInput(BaseModel):
    """记录用户明确选择的设计需求。1=完全跳过处方，0=进入处方流程。"""

    need_design: Literal[0, 1] = Field(description="1=需要象贝设计，完全跳过处方；0=不需要象贝设计，需要询问处方")


class RecordPatientDecisionInput(BaseModel):
    """记录用户对患者选择的决定。"""

    patient_decision: Literal["new", "existing"] = Field(description="new=新建患者，existing=使用已有患者")


def build_workflow_fact_tools():
    """创建 Agent 内部工具；Graph 会拦截它们，不会发送到 MCP Server。"""
    from langchain_core.tools import StructuredTool

    return [
        StructuredTool.from_function(
            name="record_workflow_intent",
            description="记录用户已经明确表达的业务意图。不要根据猜测调用。",
            args_schema=RecordWorkflowIntentInput,
            func=lambda **kwargs: kwargs,
        ),
        StructuredTool.from_function(
            name="record_case_information",
            description="记录用户已经明确提供的患者和主诉信息。信息不完整时只记录已经明确提供的字段。",
            args_schema=RecordCaseInformationInput,
            func=lambda **kwargs: kwargs,
        ),
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

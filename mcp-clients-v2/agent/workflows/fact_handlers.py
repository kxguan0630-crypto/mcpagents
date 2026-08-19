"""Agent 内部事实工具的状态处理器。

Tool 名称和字段映射属于事实层，不应该散落在 Graph 的 if/elif 中。
Graph 只负责把 Tool Call 交给这里处理。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .case_creation import complaint_complete, patient_info_complete

FactHandler = Callable[[dict[str, Any], dict[str, Any]], str]


def _record_workflow_intent(facts: dict[str, Any], arguments: dict[str, Any]) -> str:
    facts["workflow_intent"] = arguments["workflow_intent"]
    return "业务流程意图已记录。"


def _record_case_information(facts: dict[str, Any], arguments: dict[str, Any]) -> str:
    for key in ("patient_name", "gender", "patient_phone", "age", "complaint", "complaint_other"):
        if arguments.get(key) not in (None, ""):
            facts[key] = arguments[key]
    facts["patient_info_collected"] = patient_info_complete(facts)
    facts["complaint_collected"] = complaint_complete(facts)
    return "病例信息已记录。"


def _record_order_decisions(facts: dict[str, Any], arguments: dict[str, Any]) -> str:
    for key in ("diagnosis_decision", "image_decision", "model_decision", "recipe_decision"):
        if arguments.get(key) is not None:
            facts[key] = arguments[key]
    return "订单信息提供决定已记录。"


def _record_design_decision(facts: dict[str, Any], arguments: dict[str, Any]) -> str:
    facts["need_design"] = arguments["need_design"]
    if arguments["need_design"] == 1:
        # need_design=1 完全跳过处方；旧处方决定不能污染当前流程。
        facts.pop("recipe_decision", None)
    return "设计需求决定已记录。"


def _record_patient_decision(facts: dict[str, Any], arguments: dict[str, Any]) -> str:
    facts["patient_decision"] = arguments["patient_decision"]
    return "患者选择已记录。"


FACT_HANDLERS: dict[str, FactHandler] = {
    "record_workflow_intent": _record_workflow_intent,
    "record_case_information": _record_case_information,
    "record_order_decisions": _record_order_decisions,
    "record_design_decision": _record_design_decision,
    "record_patient_decision": _record_patient_decision,
}


def apply_fact_tool(facts: dict[str, Any], tool_name: str, arguments: dict[str, Any]) -> str | None:
    """执行内部事实 Tool；未知 Tool 返回 None。"""
    handler = FACT_HANDLERS.get(tool_name)
    if handler is None:
        return None
    return handler(facts, arguments)

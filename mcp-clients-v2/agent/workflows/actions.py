"""Workflow 的确定性动作。

LLM 负责理解用户表达；Workflow 决定当前是否存在必须执行的机器动作。
这里把“必须执行什么 Tool”表达成结构化 Action，Graph Runtime 只负责执行，
从而避免出现“模型说正在查询，但实际上没有调用 Tool”的假执行。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RequiredAction:
    """Workflow 要求 Runtime 自动执行的一次 Tool 动作。"""

    tool_name: str
    arguments: dict[str, Any]
    reason: str


def next_required_action(facts: dict[str, Any]) -> RequiredAction | None:
    """返回病例流程当前唯一必须自动执行的动作。

    患者信息和主诉收集完成后，患者存在性检查是确定性业务动作，不能交给 LLM 自由决定。
    """
    if facts.get("patient_info_collected") and facts.get("complaint_collected") and not facts.get("patient_checked"):
        patient_name = facts.get("patient_name")
        patient_phone = facts.get("patient_phone")
        if patient_name and patient_phone:
            return RequiredAction(
                tool_name="get_patients_by_name_and_phone",
                arguments={
                    "patient_name": patient_name,
                    "patient_phone": patient_phone,
                },
                reason="患者信息和主诉已收集完成，必须先查询患者是否存在。",
            )
    return None

"""病例创建 Workflow 的可读定义。

这个文件只回答一个问题：病例创建当前还缺什么。

LLM 负责理解用户的自然语言；LangGraph 负责循环；本文件负责确定性顺序。
这样“先收集患者和主诉，再查患者，最后等待用户决定”不会依赖 Prompt 记忆。
"""

from __future__ import annotations

from typing import Any


CASE_CREATION_STEPS = (
    "collect_patient_info",
    "collect_complaint",
    "check_patient_exists",
    "wait_patient_decision",
    "create_case",
)


def next_required_question(facts: dict[str, Any]) -> str | None:
    """返回病例创建当前最小缺口。

    返回的是内部阶段名，不是给用户看的话术。
    """
    if not facts.get("patient_info_collected"):
        return "collect_patient_info"
    if not facts.get("complaint_collected"):
        return "collect_complaint"
    if not facts.get("patient_checked"):
        return "check_patient_exists"
    if facts.get("patient_decision") not in ("new", "existing"):
        return "wait_patient_decision"
    return None


def patient_info_complete(data: dict[str, Any]) -> bool:
    """判断创建病例所需的患者基本信息是否已经完整。"""
    required = ("patient_name", "gender", "patient_phone", "age")
    return all(data.get(key) not in (None, "") for key in required)


def complaint_complete(data: dict[str, Any]) -> bool:
    """判断主诉是否完整。

    complaint_other 只在主诉选择“其它”时要求；这里不猜测其它业务枚举。
    """
    complaint = data.get("complaint")
    if complaint in (None, ""):
        return False
    if str(complaint).strip() in {"其它", "其他", "other"}:
        return data.get("complaint_other") not in (None, "")
    return True


def patient_decision_valid(value: Any) -> bool:
    """只接受用户明确做出的两种患者选择。"""
    return value in ("new", "existing")

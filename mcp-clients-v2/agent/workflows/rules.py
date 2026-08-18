"""确定性的业务流程规则。

LangGraph 负责“怎么跑”，本文件负责“什么情况下允许继续”。

LLM 可以理解用户表达，但不能凭猜测制造业务事实；MCP Tool 成功返回才可以产生工具事实。
"""

from __future__ import annotations

import json
from typing import Any


def case_add_allowed(facts: dict[str, Any], arguments: dict[str, Any]) -> tuple[bool, str]:
    """病例创建硬门禁：患者检查和用户决策必须先完成。"""
    if not facts.get("patient_info_collected", False):
        return False, "创建病例前必须先收集完整患者信息。"
    if not facts.get("complaint_collected", False):
        return False, "创建病例前必须先收集患者主诉。"
    if not facts.get("patient_checked", False):
        return False, "创建病例前必须先完成患者存在性检查。"
    decision = facts.get("patient_decision")
    if decision not in ("new", "existing"):
        return False, "创建病例前必须明确用户选择：新建患者或使用已有患者。"

    new_a_patient = arguments.get("new_a_patient")
    patient_code = arguments.get("patient_code")
    if decision == "new" and new_a_patient != 1:
        return False, "用户已选择新建患者，case_add 必须使用 new_a_patient=1。"
    if decision == "existing":
        if new_a_patient != 2:
            return False, "用户已选择已有患者，case_add 必须使用 new_a_patient=2。"
        if not patient_code:
            return False, "使用已有患者创建病例时必须提供 patient_code。"
    return True, ""


def order_create_allowed(facts: dict[str, Any], arguments: dict[str, Any]) -> tuple[bool, str]:
    """订单提交硬门禁。

    诊断、影像、模型都是每次必须询问的交互项；用户可以选择不提供。
    need_design=1 完全跳过处方，need_design=0 才进入处方流程。
    """
    if not facts.get("order_checked", False):
        return False, "创建订单前必须先完成订单存在性检查。"
    if not facts.get("product_list_loaded", False):
        return False, "创建订单前必须先获取可选产品列表。"

    need_design = arguments.get("need_design")
    if need_design not in (0, 1):
        return False, "创建订单前必须明确 need_design：1=需要象贝设计，0=不需要。"

    for key, label in (("diagnosis_decision", "诊断"), ("image_decision", "影像"), ("model_decision", "模型")):
        if facts.get(key) not in ("provide", "skip"):
            return False, f"创建订单前必须完成{label}信息的询问并记录用户选择。"

    if need_design == 0 and facts.get("recipe_decision") not in ("provide", "skip"):
        return False, "need_design=0 时必须完成处方信息的询问并记录用户选择。"

    if need_design == 1 and arguments.get("recipe_info") is not None:
        return False, "need_design=1 时完全跳过处方信息收集，不应提交 recipe_info。"

    return True, ""


def tool_result_succeeded(result: Any) -> bool:
    """判断 MCP 返回值是否代表成功。"""
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            return True
    if isinstance(result, dict):
        return result.get("code") != 50000
    return True


def update_facts(facts: dict[str, Any], tool_name: str, result: Any) -> dict[str, Any]:
    """只根据成功的 MCP Tool 更新可验证业务事实。"""
    facts = dict(facts or {})
    if not tool_result_succeeded(result):
        return facts

    mapping = {
        "get_patients_by_name_and_phone": "patient_checked",
        "case_add": "case_created",
        "check_order_by_case_code": "order_checked",
        "get_product_list": "product_list_loaded",
        "image_process": "image_processed",
        "save_case_face": "image_updated",
        "case_order_add": "order_created",
    }
    fact = mapping.get(tool_name)
    if fact:
        facts[fact] = True
    return facts

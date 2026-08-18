"""业务流程规则。

这里不实现第二套 Workflow Engine。
LangGraph 负责节点、状态、暂停/恢复；本文件只保存容易读懂的业务规则，
避免把病例/订单规则继续塞进 MCP Tool 的超长 docstring 或 system prompt。
"""

from __future__ import annotations

from typing import Any


def case_add_allowed(facts: dict[str, bool], arguments: dict[str, Any]) -> tuple[bool, str]:
    """病例创建的硬门禁：必须先完成患者存在性检查。"""
    if not facts.get("patient_checked", False):
        return False, "创建病例前必须先完成患者存在性检查。"

    new_a_patient = arguments.get("new_a_patient")
    patient_code = arguments.get("patient_code")
    if new_a_patient == 2 and not patient_code:
        return False, "使用已有患者创建病例时必须提供 patient_code。"
    if new_a_patient not in (1, 2):
        return False, "创建病例前必须明确用户选择：新建患者(1)或使用已有患者(2)。"
    return True, ""


def order_create_allowed(facts: dict[str, bool], arguments: dict[str, Any]) -> tuple[bool, str]:
    """订单提交的第一层硬门禁。

    诊断、影像、模型、处方的“是否提供”属于用户交互状态，后续由 LangGraph
    Workflow 节点逐步记录；这里先确保不会绕过订单存在性检查和产品获取。
    """
    if not facts.get("order_checked", False):
        return False, "创建订单前必须先完成订单存在性检查。"
    if not facts.get("product_list_loaded", False):
        return False, "创建订单前必须先获取可选产品列表。"

    need_design = arguments.get("need_design")
    if need_design not in (0, 1):
        return False, "创建订单前必须明确 need_design：1=需要象贝设计，0=不需要。"

    # 业务规则：需要象贝设计时跳过处方；不需要象贝设计时才进入处方流程。
    if need_design == 1 and arguments.get("recipe_info") is not None:
        return False, "need_design=1 时应跳过处方信息收集。"

    return True, ""


def update_facts(facts: dict[str, bool], tool_name: str) -> dict[str, bool]:
    """根据已经成功执行的 MCP Tool 更新业务事实。

    这里只记录客观事实，不根据 LLM 的自然语言猜测状态。
    """
    facts = dict(facts or {})
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

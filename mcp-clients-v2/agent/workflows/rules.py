"""确定性的业务流程规则。

LangGraph 负责“怎么跑”，本文件负责“什么情况下允许继续”。

LLM 可以理解用户表达，但不能凭猜测制造业务事实；MCP Tool 成功返回才可以产生业务事实。
"""

from __future__ import annotations

import json
from typing import Any


def _as_dict(result: Any) -> dict[str, Any] | None:
    """把常见 MCP JSON 结果安全转换成字典。无法识别时返回 None。"""
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            value = json.loads(result)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None
    return None


def tool_result_succeeded(result: Any) -> bool:
    """判断 MCP 返回值是否代表业务成功。

    无法识别的纯文本按失败处理，避免错误字符串意外推进 Workflow。
    """
    payload = _as_dict(result)
    if payload is None:
        return False

    code = payload.get("code")
    if code is None:
        # 兼容没有 code 字段、但本身是结构化成功结果的旧业务接口。
        return True
    try:
        return int(code) == 0
    except (TypeError, ValueError):
        return False


def _payload_contains_data(result: Any, *keys: str) -> bool:
    """判断查询结果是否带有后续流程需要的数据。"""
    payload = _as_dict(result)
    if payload is None:
        return False
    return any(payload.get(key) not in (None, "", [], {}) for key in keys)


def update_facts(facts: dict[str, Any], tool_name: str, result: Any) -> dict[str, Any]:
    """只根据成功且可解释的 Tool 结果更新业务事实。"""
    facts = dict(facts or {})
    if not tool_result_succeeded(result):
        return facts

    if tool_name == "get_patients_by_name_and_phone":
        facts["patient_checked"] = True
        facts["patient_query_result"] = (
            "found" if _payload_contains_data(result, "data", "patients", "list") else "not_found"
        )
    elif tool_name == "case_add":
        facts["case_created"] = True
    elif tool_name == "check_order_by_case_code":
        facts["order_checked"] = True
    elif tool_name == "get_product_list":
        facts["product_list_loaded"] = True
    elif tool_name == "image_process":
        facts["image_processed"] = True
    elif tool_name == "save_case_face":
        facts["image_updated"] = True
    elif tool_name == "case_order_add":
        facts["order_created"] = True

    return facts


def case_add_allowed(facts: dict[str, Any], arguments: dict[str, Any]) -> tuple[bool, str]:
    """病例创建硬门禁：患者信息、主诉、查询和用户决定必须先完成。"""
    if not facts.get("patient_info_collected"):
        return False, "创建病例前必须先收集完整患者信息。"
    if not facts.get("complaint_collected"):
        return False, "创建病例前必须先收集患者主诉。"
    if not facts.get("patient_checked"):
        return False, "创建病例前必须完成患者存在性检查。"

    decision = facts.get("patient_decision")
    if decision not in ("new", "existing"):
        return False, "创建病例前必须明确选择新建患者或使用已有患者。"

    new_a_patient = arguments.get("new_a_patient")
    patient_code = arguments.get("patient_code")
    if decision == "new" and new_a_patient != 1:
        return False, "用户选择新建患者时，new_a_patient 必须为 1。"
    if decision == "existing" and (new_a_patient != 2 or not patient_code):
        return False, "使用已有患者时，new_a_patient 必须为 2 且必须提供 patient_code。"
    return True, ""


def order_create_allowed(facts: dict[str, Any], arguments: dict[str, Any]) -> tuple[bool, str]:
    """订单提交硬门禁。

    诊断、影像、模型必须询问；用户可以选择不提供。
    need_design=1 完全跳过处方，need_design=0 才进入处方询问。
    """
    if not facts.get("order_checked"):
        return False, "创建订单前必须先完成订单存在性检查。"
    if not facts.get("product_list_loaded"):
        return False, "创建订单前必须先获取产品列表。"

    need_design = arguments.get("need_design")
    if need_design not in (0, 1):
        return False, "need_design 必须为 0 或 1。"

    for key, label in (("diagnosis_decision", "诊断"), ("image_decision", "影像"), ("model_decision", "模型")):
        if facts.get(key) not in ("provide", "skip"):
            return False, f"创建订单前必须完成{label}信息的询问并记录用户选择。"

    if need_design == 0 and facts.get("recipe_decision") not in ("provide", "skip"):
        return False, "need_design=0 时必须完成处方信息询问并记录用户选择。"

    if need_design == 1 and arguments.get("recipe_info") is not None:
        return False, "need_design=1 时完全跳过处方，不应提交 recipe_info。"

    return True, ""


def image_update_allowed(facts: dict[str, Any], arguments: dict[str, Any]) -> tuple[bool, str]:
    """影像更新门禁：必须先完成图片识别，再保存/更新。"""
    if not arguments.get("case_code"):
        return False, "更新影像时必须提供 case_code。"
    if not facts.get("image_processed"):
        return False, "更新影像前必须先完成 image_process。"
    return True, ""

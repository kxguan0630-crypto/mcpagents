"""Workflow 关键业务不变量测试。

这些测试不连接真实 MCP Server，专门验证“流程门禁”不会因为 Prompt 或模型行为而失效。
"""

from agent.workflows.case_creation import next_required_question
from agent.workflows.order_creation import next_required_question as next_order_question
from agent.workflows.rules import case_add_allowed, image_update_allowed, order_create_allowed, update_facts


def test_case_must_check_patient_after_patient_and_complaint():
    facts = {"patient_info_collected": True, "complaint_collected": True}
    assert next_required_question(facts) == "check_patient_exists"


def test_case_must_wait_for_patient_decision_after_check():
    facts = {
        "patient_info_collected": True,
        "complaint_collected": True,
        "patient_checked": True,
    }
    assert next_required_question(facts) == "wait_patient_decision"


def test_case_add_existing_requires_patient_code():
    facts = {
        "patient_info_collected": True,
        "complaint_collected": True,
        "patient_checked": True,
        "patient_decision": "existing",
    }
    allowed, _ = case_add_allowed(facts, {"new_a_patient": 2})
    assert not allowed


def test_order_must_ask_three_optional_decisions():
    facts = {"order_checked": True, "product_list_loaded": True}
    assert next_order_question(facts, None) == "need_design"
    facts["need_design"] = 1
    assert next_order_question(facts, 1) == "diagnosis_decision"
    facts["diagnosis_decision"] = "skip"
    assert next_order_question(facts, 1) == "image_decision"


def test_need_design_one_skips_recipe():
    facts = {
        "order_checked": True,
        "product_list_loaded": True,
        "diagnosis_decision": "skip",
        "image_decision": "skip",
        "model_decision": "skip",
    }
    assert next_order_question(facts, 1) is None
    allowed, reason = order_create_allowed(facts, {"need_design": 1})
    assert allowed, reason


def test_need_design_zero_requires_recipe_decision():
    facts = {
        "order_checked": True,
        "product_list_loaded": True,
        "diagnosis_decision": "skip",
        "image_decision": "skip",
        "model_decision": "skip",
    }
    assert next_order_question(facts, 0) == "recipe_decision"
    allowed, _ = order_create_allowed(facts, {"need_design": 0})
    assert not allowed


def test_image_update_requires_image_processing():
    allowed, _ = image_update_allowed({}, {"case_code": "C001"})
    assert not allowed


def test_failed_tool_does_not_create_fact():
    facts = {}
    updated = update_facts(facts, "case_add", '{"code": 50000, "message": "failed"}')
    assert updated == {}

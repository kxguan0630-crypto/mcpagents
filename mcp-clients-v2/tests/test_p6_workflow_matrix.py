"""P6 核心业务 Workflow 验收矩阵。

这些测试不调用真实 LLM、Redis 或业务 HTTP API；它们锁定 Agent 最关键的确定性业务边界。
真实 MCP/业务接口联调仍需要在本地部署环境执行，详见 docs/p6-e2e-verification.md。
"""

from agent.workflows.case_creation import next_required_question, patient_decision_valid
from agent.workflows.order_creation import next_required_question as next_order_question
from agent.workflows.order_creation import should_collect_recipe


def test_case_must_collect_patient_and_complaint_before_patient_check():
    """患者查询不能早于患者信息和主诉收集完成。"""
    assert next_required_question({}) == "collect_patient_info"
    assert next_required_question({"patient_info_collected": True}) == "collect_complaint"
    assert next_required_question({
        "patient_info_collected": True,
        "complaint_collected": True,
    }) == "check_patient_exists"


def test_case_waits_for_explicit_patient_decision_after_check():
    """患者查询完成后必须等待用户明确选择新建或使用已有患者。"""
    checked = {
        "patient_info_collected": True,
        "complaint_collected": True,
        "patient_checked": True,
    }
    assert next_required_question(checked) == "wait_patient_decision"
    assert patient_decision_valid("new") is True
    assert patient_decision_valid("existing") is True
    assert patient_decision_valid("yes") is False


def test_order_always_asks_diagnosis_image_and_model():
    """诊断、影像、模型都必须询问，但用户可以选择 skip。"""
    facts = {"order_checked": True, "product_list_loaded": True, "diagnosis_decision": "skip"}
    assert next_order_question(facts, 1) == "image_decision"

    facts["image_decision"] = "skip"
    assert next_order_question(facts, 1) == "model_decision"

    facts["model_decision"] = "skip"
    assert next_order_question(facts, 1) is None


def test_need_design_one_skips_recipe_entirely():
    """need_design=1 时完全跳过处方流程。"""
    assert should_collect_recipe(1) is False
    facts = {
        "order_checked": True,
        "product_list_loaded": True,
        "diagnosis_decision": "skip",
        "image_decision": "skip",
        "model_decision": "skip",
    }
    assert next_order_question(facts, 1) is None


def test_need_design_zero_enters_recipe_flow():
    """只有 need_design=0 才进入处方询问。"""
    assert should_collect_recipe(0) is True
    facts = {
        "order_checked": True,
        "product_list_loaded": True,
        "diagnosis_decision": "skip",
        "image_decision": "skip",
        "model_decision": "skip",
    }
    assert next_order_question(facts, 0) == "recipe_decision"


def test_image_update_requires_image_processing_first():
    """订单/病例后的影像更新必须先完成 image_process。"""
    from agent.workflows.implementations import ImageUpdateWorkflow

    workflow = ImageUpdateWorkflow()
    assert workflow.next_step({}) == "image_process"
    assert workflow.next_step({"image_processed": True}) is None

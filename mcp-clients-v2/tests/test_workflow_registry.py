"""Workflow 解耦层的最小单元测试。"""

from agent.workflows.implementations import (
    CaseCreationWorkflow,
    ImageUpdateWorkflow,
    OrderCreationWorkflow,
    build_default_workflow_registry,
)


def test_default_registry_contains_business_workflows():
    registry = build_default_workflow_registry()

    assert isinstance(registry.resolve("case_creation"), CaseCreationWorkflow)
    assert isinstance(registry.resolve("order_creation"), OrderCreationWorkflow)
    assert isinstance(registry.resolve("update_image"), ImageUpdateWorkflow)
    assert registry.resolve("unknown") is None


def test_workflow_rules_are_not_selected_by_graph_branches():
    registry = build_default_workflow_registry()

    case = registry.resolve("case_creation")
    assert case.next_step({}) == "collect_patient_info"

    order = registry.resolve("order_creation")
    assert order.next_step({"order_checked": True, "product_list_loaded": True}) == "need_design"

    image = registry.resolve("update_image")
    assert image.next_step({}) == "image_process"

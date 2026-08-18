"""订单创建流程的可读定义。

“是否提供”是用户交互状态：用户可以选择不提供，但每次进入诊断和影像阶段都必须询问。
need_design 的业务语义在这里明确固定：

    need_design=1 -> 需要象贝设计 -> 跳过处方信息收集
    need_design=0 -> 不需要象贝设计 -> 进入处方信息收集
"""

ORDER_CREATION_STEPS = (
    "confirm_case",
    "check_existing_order",
    "select_product",
    "decide_design",
    "decide_diagnosis",
    "decide_image",
    "decide_model",
    "decide_recipe_if_needed",
    "create_order",
)

ORDER_RULES = {
    "check_existing_order": "除刚刚创建的新病例外，创建订单前必须检查病例是否已有订单。",
    "select_product": "必须先获取产品列表并由用户选择正式产品。",
    "decide_design": "必须明确 need_design。",
    "decide_diagnosis": "每次必须询问是否提供诊断信息；允许选择不提供。",
    "decide_image": "每次必须询问是否提供影像；允许选择不提供。用户主动上传图片时视为提供，并调用 image_process。",
    "decide_model": "必须询问是否提供模型；同意后按业务工具规定的口扫软件流程执行。",
    "decide_recipe_if_needed": "need_design=0 才进入处方信息收集；need_design=1 完全跳过。",
    "create_order": "只有上述必需交互完成后才允许 case_order_add。",
}

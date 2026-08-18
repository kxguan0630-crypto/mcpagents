"""面诊/影像独立业务能力。

影像不能只属于订单创建流程，因为订单创建完成后仍然可以补充或更新影像。
因此 Image/Face 能力作为独立 Workflow 被多个业务场景复用。
"""

FACE_WORKFLOW_STEPS = (
    "collect_face_info",
    "process_uploaded_images",
    "collect_model_if_needed",
    "save_or_update_face",
)

IMAGE_RULES = {
    "input": "图片由前端上传并以 file_id/url 等引用进入 Agent；不把二进制文件塞进 LangGraph checkpoint。",
    "recognition": "image_process 只负责识别/结构化图片，不等同于保存影像。",
    "update": "订单创建后仍可独立调用面诊/影像更新能力，不得强制重新走订单创建流程。",
    "batch": "image_process 对图片数量有单批限制时，由输入/工具适配层负责分批，不让 LLM 处理技术细节。",
}

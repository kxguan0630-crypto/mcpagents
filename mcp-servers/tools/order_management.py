# tools/order_management.py
import json
from mcp.server.fastmcp import FastMCP
from services.orthodontic_service import orthodontic_service
from models import RecipeInfoTemplate, CheckInfoTemplate, ModelInfoTemplate, PhotoInfoTemplate
from typing import Optional, Annotated
import logging
from models.validators import with_model_validation, set_current_language

logger = logging.getLogger("SERVER_LOGGER")
mcp = FastMCP("order_management")


@mcp.tool()
@with_model_validation(CheckInfoTemplate, 'check_info')
@with_model_validation(RecipeInfoTemplate, 'recipe_info')
async def case_order_add(
        service_type: str,
        product_ids: list,
        product_type: str,
        case_code: str,
        need_design: int,
        model_info: Optional[ModelInfoTemplate] = None,
        check_info: Annotated[dict, "临床诊断信息 / Clinical Diagnosis Information"] = None,
        photo_info: Optional[PhotoInfoTemplate] = None,
        recipe_info: Annotated[dict, "处方信息 / Prescription Information"] = None,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """创建正畸病例订单 / Create an orthodontic case order.

    本 MCP Tool 只负责一次明确的“提交订单”动作。

    多轮 Agent 流程由客户端 LangGraph Workflow 控制，不在这里实现：
    - 订单检查与产品选择；
    - need_design 决策；
    - 诊断、影像、模型的用户决定；
    - need_design=0 时的处方决定；
    - 创建订单前的用户确认。

    Tool 本身只关注参数和服务端校验：
    - need_design 必须是 0 或 1；
    - need_design=1 时不应提交 recipe_info；
    - check_info 和 recipe_info 会经过服务端模型校验；
    - model_info / photo_info 使用对应业务工具产生的结构化数据；
    - service_type、product_ids、product_type、case_code 是提交订单所需的基础参数。

    本工具不会自行调用其他 MCP Tool，也不会自行推进 Agent 流程。
    """
    try:
        set_current_language(we_lang)
        if need_design not in (0, 1):
            return json.dumps({"code": 40000, "message": "need_design must be 0 or 1"}, ensure_ascii=False)
        if need_design == 1 and recipe_info is not None:
            return json.dumps({"code": 40000, "message": "recipe_info must be omitted when need_design=1"}, ensure_ascii=False)

        result = await orthodontic_service.case_order_add(
            service_type=service_type,
            product_ids=product_ids,
            product_type=product_type,
            case_code=case_code,
            need_design=need_design,
            model_info=model_info,
            check_info=check_info,
            photo_info=photo_info,
            recipe_info=recipe_info,
            authorization=authorization,
        )
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        logger.exception("case_order_add failed")
        return json.dumps({"code": 50000, "message": str(exc)}, ensure_ascii=False)

# tools/product_and_equity_management.py
import json
from typing import Optional
from mcp.server.fastmcp import FastMCP
from services.orthodontic_service import orthodontic_service
import logging

logger = logging.getLogger("SERVER_LOGGER")
# Initialize FastMCP server
mcp = FastMCP("product_and_equity_management")


@mcp.tool()
async def get_product_list(
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """获取产品列表 / Get Product List

    使用场景 / Usage Scenarios:
    - 订单创建时选择产品 / Select products when creating order

    返回信息 / Returns:
    - 产品名称 / Product name
    - 价格 / Price
    - 权益 / Benefits
    - 产品类型 / Product type
    - 是否为体验装 / Is trial product

    Args:
        authorization: 可选的 Authorization Token / Optional Authorization token
        we_lang: 语言设置，默认为"zh-CN" / Language setting, default is "zh-CN"

    Returns:
        产品列表信息 / Product list information
    """
    msg = "获取产品列表" if we_lang == "zh-CN" else "Getting product list"
    logger.info(f"{msg}, lang={we_lang}")

    try:
        data = await orthodontic_service.get_product_list(
            authorization=authorization,
            we_lang=we_lang
        )
        return json.dumps(data)
    except Exception as e:
        error_msg = "获取产品列表时发生错误" if we_lang == "zh-CN" else "Error getting product list"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def get_equity_info(
        keyword: str,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """获取权益信息 / Get Equity Information

    通过患者姓名、或患者手机号、或患者编号、或病例编号查询权益信息
    Query equity information by patient name, phone number, code or case number

    以 markdown 格式展示 / Display in markdown format

    使用场景 / Usage Scenarios:
    - 查看患者享有的权益 / View patient's benefits
    - 确认订单包含的权益 / Confirm benefits included in order

    Args:
        keyword: 患者姓名、或患者手机号、或患者编号、或病例编号
                 Patient name, phone number, code or case number
        authorization: 可选的 Authorization Token / Optional Authorization token
        we_lang: 语言设置，默认为"zh-CN" / Language setting, default is "zh-CN"

    Returns:
        权益信息 / Equity information

    返回信息包括 / Details include:
    - 权益类型 / Equity type
    - 权益内容 / Equity content
    - 有效期 / Validity period
    - 使用状态 / Usage status
    """
    msg = "获取权益信息" if we_lang == "zh-CN" else "Getting equity information"
    logger.info(f"{msg}: keyword={keyword}, lang={we_lang}")

    try:
        data = await orthodontic_service.get_equity_info(
            keyword=keyword,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            error_msg = "未获取到权益信息" if we_lang == "zh-CN" else "Equity information not found"
            return json.dumps({"message": error_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "获取权益信息时发生错误" if we_lang == "zh-CN" else "Error getting equity information"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})
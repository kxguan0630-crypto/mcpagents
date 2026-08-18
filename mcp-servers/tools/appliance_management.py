# tools/appliance_management.py
import json
from mcp.server.fastmcp import FastMCP
from services.orthodontic_service import orthodontic_service
from models import OrderApplianceInfoTemplate
import logging

logger = logging.getLogger("SERVER_LOGGER")
# Initialize FastMCP server
mcp = FastMCP("appliance_management")


@mcp.tool()
async def save_appliance_info(
        basic_info: OrderApplianceInfoTemplate,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """申请补发矫治器 / Apply Appliance Reorder Information

    【核心功能】：专门用于处理矫治器的补发、重做、遗失补发等场景。
    【Core Function】: Specifically used for reissuing appliances, remakes, or lost replacements.

    使用场景 / Usage Scenarios:
    1.用户明确要求“补发”、“重做”或“再发一次”矫治器时 / When user explicitly asks to "reissue", "remake", or "send again".
    2.为患者创建新的补发订单 / Create a new reissue order for a patient.
    3.如果用户输入包含“补发”关键词，请优先使用此工具，不要使用“申请发货”工具 / If user input contains "reissue" or "补发", prioritize THIS tool. Do NOT use "Apply Delivery".

    如果缺少必要的参数，让用户提供
    If required parameters are missing, ask user to provide them

    Args:
        basic_info: 补发矫治器信息 (OrderApplianceInfoTemplate) / Appliance reissue information
        authorization: 可选的 Authorization Token / Optional Authorization token
        we_lang: 语言设置，默认为"zh-CN" / Language setting, default is "zh-CN"

    Returns:
        订单 ID / Order ID

    必填字段 / Required Fields:
    - case_code: 病例编号 / Case number
    - step: 步数(以 / 间隔，如23/24全口，25下颌) / Step (Separated by /, e.g., 23/24 full mouth, 25 mandibular.)
    - consignee: 收货人 / Consignee
    - consignee_mobile: 收货人手机 / Consignee mobile phone
    - consignee_address: 收货地址 / Consignee address
    选填字段 / Optional Field
    - remark: 备注 / Remark
    """
    lang_msg = "保存补发矫治器订单信息" if we_lang == "zh-CN" else "Saving appliance reorder information"
    logger.info(f"{lang_msg}, 语言/Lang: {we_lang}")

    try:
        # 验证必填字段 / Validate required fields
        basic_info.validate_optional_fields()

        # 转换模型数据 / Convert model data
        basic_info_dict = basic_info.model_dump(exclude_unset=True)

        data = await orthodontic_service.save_appliance(
            case_code=basic_info_dict.get('case_code'),
            step=basic_info_dict.get('step'),
            remark=basic_info_dict.get('remark'),
            consignee=basic_info_dict.get('consignee'),
            consignee_mobile=basic_info_dict.get('consignee_mobile'),
            consignee_address=basic_info_dict.get('consignee_address'),
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            error_msg = "保存补发矫治器订单信息失败" if we_lang == "zh-CN" else "Failed to save appliance reorder information"
            return json.dumps({"message": error_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "保存补发矫治器订单信息时发生错误" if we_lang == "zh-CN" else "Error saving appliance reorder information"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def get_appliance_list(
        case_code: str,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """获取补发矫治器列表 / Get Appliance Reorder List

    根据病例编号查询所有补发矫治器订单
    Query all appliance reorder orders by case number

    使用场景 / Usage Scenarios:
    - 查看患者的补发矫治器历史记录 / View patient's appliance reorder history
    - 用户明确要求查询“补发”矫治器列表 / The user explicitly requests to query the list of "replacement" aligners.

    Args:
        case_code: 病例编号 / Case number
        authorization: 可选的 Authorization Token / Optional Authorization token
        we_lang: 语言设置，默认为"zh-CN" / Language setting, default is "zh-CN"

    Returns:
        补发矫治器列表 / Appliance reorder list

    返回列表包含 / List includes:
    - order_number: 订单编号 / Order number
    - step: 步骤 / Step
    - status: 状态 / Status
    - create_time: 创建时间 / Creation time
    """
    msg = "获取补发矫治器列表" if we_lang == "zh-CN" else "Getting appliance reorder list"
    logger.info(f"{msg}: case_code={case_code}, lang={we_lang}")

    try:
        data = await orthodontic_service.get_appliance_list(
            case_code=case_code,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            error_msg = "未获取到补发矫治器列表" if we_lang == "zh-CN" else "Appliance reorder list not found"
            return json.dumps({"message": error_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "获取补发矫治器列表时发生错误" if we_lang == "zh-CN" else "Error getting appliance reorder list"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def get_appliance_info(
        order_number: str,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """获取补发矫治器订单信息 / Get Appliance Reorder Details

    使用场景 / Usage Scenarios:
        - **最高优先级触发：** 只要用户输入中包含 **“矫治器信息”**、或**“矫治器详情”**、 或 **“补发信息”**、 或 **“补发详情”** 任意一个关键词，**则调用本工具；**否则调用工具 `order_detail` 工具。/ Highest Priority Trigger: As long as the user input contains any of the keywords "Aligner Info", "Aligner Details", "Replacement Info", or "Replacement Details", then call this tool; otherwise, call the order_detail tool
        - **排他性规则：** 本工具是查询“矫治器订单”的**唯一**入口。/ Exclusivity Rule: This tool is the sole entry point for querying "Aligner Orders".
        - 例如输入：“xxx矫治器信息”，或 “xxx补发矫治器详情”，则调用 “get_appliance_info” 工具；否则调用 `order_detail` 工具。/ For instance, inputs like "xxx Aligner Info" or "xxx Replacement Aligner Details" should trigger the get_appliance_info tool; otherwise, call the order_detail tool.

    Args:
        order_number: 订单编号 / Order number
        authorization: 可选的 Authorization Token / Optional Authorization token
        we_lang: 语言设置，默认为"zh-CN" / Language setting, default is "zh-CN"

    Returns:
        补发矫治器订单信息 / Appliance reorder order details

    返回信息包括 / Details include:
    - case_code: 病例编号 / Case number
    - step: 步骤 / Step
    - remark: 备注 / Remark
    - consignee: 收货人 / Consignee
    - consignee_mobile: 收货人手机 / Consignee mobile
    - consignee_address: 收货地址 / Consignee address
    - status: 订单状态 / Order status
    """
    msg = "获取补发矫治器订单信息" if we_lang == "zh-CN" else "Getting appliance reorder details"
    logger.info(f"{msg}: order_number={order_number}, lang={we_lang}")

    try:
        data = await orthodontic_service.get_appliance_info(
            order_number=order_number,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            error_msg = "未获取到补发矫治器订单信息" if we_lang == "zh-CN" else "Appliance reorder details not found"
            return json.dumps({"message": error_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "获取补发矫治器订单信息时发生错误" if we_lang == "zh-CN" else "Error getting appliance reorder details"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})

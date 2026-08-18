# tools/retainner_management.py
import json
from mcp.server.fastmcp import FastMCP
from services.orthodontic_service import orthodontic_service
from models import OrderRetainerInfoTemplate
import logging

logger = logging.getLogger("SERVER_LOGGER")
# Initialize FastMCP server
mcp = FastMCP("retainner_management")


@mcp.tool()
async def save_retainer_info(
        case_code: str,
        basic_info: OrderRetainerInfoTemplate,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """创建保持器订单 / Create Retainer Order

    使用场景 / Usage Scenarios:
    1：用户明确要求查询“定制”、或“保持器”订单信息 / The user explicitly requests to query information for 'customized' or 'retainer' orders
    2：为患者创建新的保持器订单 / Create a new retainer order for a patient.

    根据流程指导顺序校验执行
    Execute validation according to the process guide

    流程指导 / Process Guide:
    1. 根据用户输入的信息，调用主订单信息的工具 [get_main_order_info]，提示用户：上颌矫治步数最大可输入步数 `upper_periods`；下颌矫治步数最大可输入步数 `lower_periods`；保持器的价格 `sale_price`。
       Based on user input, call tool [get_main_order_info] ,Notify User: max upper periods `upper_periods`, max lower periods `lower_periods`, and retainer price `sale_price`.

    2. 根据用户输入的信息校验，如果用户输入的上颌矫治步数大于主订单信息中的上颌矫治步数最大可输入步数 `upper_periods`，则提示用户：上颌矫治步数最大可输入步数为`upper_periods`值
       Validate user input: if upper_step > `upper_periods`, inform user that max upper steps is `upper_periods` value.

    3. 根据用户输入的信息校验，如果用户输入的下颌矫治步数大于主订单信息中的下颌矫治步数最大可输入步数 `lower_periods`，则提示用户：下颌矫治步数最大可输入步数为`lower_periods`值
       Validate user input: if lower_step > `lower_periods`, inform user that max lower steps is `lower_periods` value.

    4. 根据用户输入的信息，计算订单金额：订单金额 = 需要定制保持器的数量 [pair_count] * 保持器的价格 [`sale_price`] * 2，询问用户：「询问是否接受并继续提交保持器订单信息？(y/n)」。
       Calculate order amount: Amount = pair_count * sale_price * 2. Ask user: "Do you accept and continue to submit retainer order? (y/n)"

    5. 正式发起创建保持器订单前,需要询问用户  收件人姓名，收货地址，联系电话 是否全部正确，是否需要修改？
      Before formally initiating the creation of a retainer order, please confirm with the user whether the recipient's name, shipping address, and contact phone number are all correct. Do any modifications need to be made?

    6. 若用户选择继续保存保持器订单信息 [y]，则基于收集到的所有必要信息构建请求体，并发送至服务器完成订单创建;若用户没有选择继续保存保持器订单信息 [n]，则提问：「是否还有其他帮助？」。
       If user chooses to continue [y], build request body with all collected information and send to server to complete order creation; if user chooses not to continue [n], ask: "Is there anything else I can help you with?"

    Args:
        case_code: 病例编号 / Case number
        basic_info: 保持器订单信息 (OrderRetainerInfoTemplate) / Retainer order information
        authorization: 可选的 Authorization Token / Optional Authorization token
        we_lang: 语言设置，默认为"zh-CN" / Language setting, default is "zh-CN"

    Returns:
        订单 ID / Order ID

    必填字段 / Required Fields:
    - case_code: 病例编号 / Case number
    - pair_count: 需要定制保持器的数量 / Number of retainers to customize
    - upper_step: 上颌矫治步数 / Upper step count
    - lower_step: 下颌矫治步数 / Lower step count
    - consignee: 收货人 / Consignee
    - consignee_mobile: 收货人手机 / Consignee mobile phone
    - consignee_address: 收货地址 / Consignee address
    选填字段 / Optional Field
    - remark: 备注 / Remark
    - ks_model: 模型文件 / Model file

    """
    msg = "创建保持器订单" if we_lang == "zh-CN" else "Creating retainer order"
    logger.info(f"{msg}: case_code={case_code}, lang={we_lang}")

    try:
        # 验证必填字段 / Validate required fields
        basic_info.validate_optional_fields()

        # 转换模型数据 / Convert model data
        basic_info_dict = basic_info.model_dump(exclude_unset=True)
        basic_info_dict['case_code'] = case_code

        data = await orthodontic_service.save_retainer(
            case_code=basic_info_dict.get('case_code'),
            pair_count=basic_info_dict.get('pair_count'),
            upper_step=basic_info_dict.get('upper_step'),
            lower_step=basic_info_dict.get('lower_step'),
            ks_model=basic_info_dict.get('ks_model'),
            remark=basic_info_dict.get('remark'),
            consignee=basic_info_dict.get('consignee'),
            consignee_mobile=basic_info_dict.get('consignee_mobile'),
            consignee_address=basic_info_dict.get('consignee_address'),
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            error_msg = "创建保持器订单失败" if we_lang == "zh-CN" else "Failed to create retainer order"
            return json.dumps({"message": error_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "创建保持器订单时发生错误" if we_lang == "zh-CN" else "Error creating retainer order"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def get_retainer_list(
        case_code: str,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """保持器订单列表 / Get Retainer Order List

    通过病例编号 (C 开头) 查询保持器订单列表
    Query retainer order list by case number (starts with C)

    数据整理后以 markdown 格式输出
    Output data in markdown format after organizing

    Args:
        case_code: 病例编号 / Case number
        authorization: 可选的 Authorization Token / Optional Authorization token
        we_lang: 语言设置，默认为"zh-CN" / Language setting, default is "zh-CN"

    Returns:
        保持器订单列表 / Retainer order list

    返回列表包含 / List includes:
    - order_number: 订单编号 / Order number
    - pair_count: 保持器数量 / Pair count
    - upper_step: 上颌步数 / Upper step
    - lower_step: 下颌步数 / Lower step
    - status: 订单状态 / Order status
    - create_time: 创建时间 / Creation time
    """
    msg = "获取保持器订单列表" if we_lang == "zh-CN" else "Getting retainer order list"
    logger.info(f"{msg}: case_code={case_code}, lang={we_lang}")

    try:
        data = await orthodontic_service.get_retainer_list(
            case_code=case_code,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            error_msg = "未获取到保持器订单列表" if we_lang == "zh-CN" else "Retainer order list not found"
            return json.dumps({"message": error_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "获取保持器订单列表时发生错误" if we_lang == "zh-CN" else "Error getting retainer order list"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})


@mcp.tool()
async def get_retainer_info(
        order_number: str,
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> str:
    """保持器订单详情信息 / Get Retainer Order Details

    使用场景 / Usage Scenarios:
        - **最高优先级触发：** 只要用户输入中包含 **“保持器信息”**、或**“保持器详情”**、 或 **“定制信息”**、 或 **“定制详情”** 任意一个关键词，**则调用本工具；**否则调用工具 `order_detail` 工具。/ Highest Priority Trigger: As long as the user input contains any of the keywords "Retainer Info", "Retainer Details", "Custom Info", or "Custom Details", then call this tool; otherwise, call the order_detail tool
        - **排他性规则：** 本工具是查询“保持器订单”的**唯一**入口 / Exclusivity Rule: This tool is the sole entry point for querying "Retainer Orders".
        - 例如输入：“xxx保持器信息”，或 “xxx定制保持器详情”，则调用 “get_retainer_info” 工具；否则调用 `order_detail` 工具。/ For example, for inputs like "xxx Retainer Info" or "xxx Custom Retainer Details", call the get_retainer_info tool; otherwise, call the order_detail tool.



    Args:
        order_number: 订单编号 / Order number
        authorization: 可选的 Authorization Token / Optional Authorization token
        we_lang: 语言设置，默认为"zh-CN" / Language setting, default is "zh-CN"

    Returns:
        保持器订单详情信息 / Retainer order details

    返回信息包括 / Details include:
    - case_code: 病例编号 / Case number
    - pair_count: 保持器数量 / Pair count
    - upper_step: 上颌步数 / Upper step
    - lower_step: 下颌步数 / Lower step
    - ks_model: 口扫模型 / Intraoral scan model
    - remark: 备注 / Remark
    - consignee: 收货人 / Consignee
    - consignee_mobile: 收货人手机 / Consignee mobile
    - consignee_address: 收货地址 / Consignee address
    - status: 订单状态 / Order status
    """
    msg = "获取保持器订单详情" if we_lang == "zh-CN" else "Getting retainer order details"
    logger.info(f"{msg}: order_number={order_number}, lang={we_lang}")

    try:
        data = await orthodontic_service.get_retainer_info(
            order_number=order_number,
            authorization=authorization,
            we_lang=we_lang
        )

        if not data:
            error_msg = "未获取到保持器订单详情" if we_lang == "zh-CN" else "Retainer order details not found"
            return json.dumps({"message": error_msg, "code": 30000})

        return json.dumps(data)

    except Exception as e:
        error_msg = "获取保持器订单详情时发生错误" if we_lang == "zh-CN" else "Error getting retainer order details"
        logger.error(f"{error_msg}: {e}")
        return json.dumps({"message": f"{error_msg}: {str(e)}", "code": 50000})
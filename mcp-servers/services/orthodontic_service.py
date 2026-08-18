# services/orthodontic_service.py
from typing import Dict, Any, Optional, List
from services.http_client import http_client
from config.settings import settings
from utils.exceptions import ExternalAPIError
# from utils.logger import logger
import logging
logger = logging.getLogger("SERVER_LOGGER")

class OrthodonticService:
    """正畸服务封装类"""

    def __init__(self):
        self.base_url = settings.API_BASE_URL
        self.image_process_url = settings.IMAGE_PROCESS_URL

    async def make_request(
            self,
            endpoint: str,
            data: Dict[str, Any],
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """
        发送API请求

        Args:
            endpoint: API端点
            data: 请求数据
            authorization: 授权令牌

        Returns:
            响应数据或None
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {"Accept": "application/json"}

        if authorization:
            headers["Authorization"] = authorization

        if we_lang:
            headers["We-Lang"] = we_lang

        response =  await http_client.post(url, data, headers)

        #统一处理响应
        return self._process_response(response, endpoint)

    def _process_response(self, response: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
        """
        统一处理API响应

        Args:
            response: API响应
            endpoint: 请求的端点

        Returns:
            处理后的业务数据

        Raises:
            ExternalAPIError: 当响应格式不正确或业务失败时抛出
        """
        if response.get("code") == 10000:
            return response.get('resultObject', response)
        else:
            raise ExternalAPIError(
                f"API调用失败：{response.get('msg', '未知错误')}"
            )

    async def case_add(
            self,
            patient_name: str,
            gender: int,
            patient_phone: str,
            age: str,
            new_a_patient: int,
            complaint: str,
            complaint_other: Optional[str] = None,
            patient_code: Optional[str] = None,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """创建病例"""
        data = {
            "patient_name": patient_name,
            "gender": gender,
            "patient_phone": patient_phone,
            "age": age,
            "new_a_patient": new_a_patient,
            "complaint": complaint,
            "complaint_other": complaint_other,
            "patient_code": patient_code
        }

        return await self.make_request("/ai/orth-case/add", data, authorization, we_lang)

    async def get_patients_by_name_and_phone(
            self,
            patient_name: Optional[str] = None,
            patient_phone: Optional[str] = None,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """根据姓名和手机号查询患者"""
        data = {
            "patient_name": patient_name,
            "patient_phone": patient_phone
        }
        logger.info(f"查询患者信息：{data}")

        return await self.make_request(
            "/ai/orth-case/get-patients-by-name-and-phone",
            data,
            authorization,
            we_lang
        )

    async def get_product_list(
            self,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """获取产品列表"""
        return await self.make_request("/v3/product/list", {}, authorization, we_lang)

    async def create_case_order(
            self,
            service_type: str,
            product_ids: List[str],
            product_type: str,
            case_code: str,
            need_design: int,
            model_info: Optional[Dict] = None,
            check_info: Optional[Dict] = None,
            photo_info: Optional[Dict] = None,
            recipe_info: Optional[Dict] = None,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """创建病例订单"""
        data = {
            "service_type": service_type,
            "product_ids": product_ids if isinstance(product_ids, list) else [product_ids],
            "product_type": product_type,
            "case_code": case_code,
            "need_design": need_design,
            "model_info": model_info,
            "check_info": check_info,
            "photo_info": photo_info,
            "recipe_info": recipe_info
        }

        # 移除None值
        data = {k: v for k, v in data.items() if v is not None}

        return await self.make_request("/ai/orth-case-order/add", data, authorization, we_lang)

    async def process_images(
            self,
            image_list: List[Dict],
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """处理影像图片"""
        # 转换file_id字段名
        processed_images = []
        for image in image_list:
            processed_image = image.copy()
            if 'file_id' in processed_image:
                processed_image['fileId'] = processed_image.pop('file_id')
            processed_images.append(processed_image)

        data = {"imageList": processed_images}
        headers = {"Accept": "application/json", "Accept-Language": we_lang}

        if authorization:
            headers["Authorization"] = authorization

        return await http_client.post(self.image_process_url, data, headers)

    # 在 OrthodonticService 类中添加以下方法

    async def get_patient_case_info(
            self,
            keyword: str,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """获取患者病例信息"""
        data = {"keyword": keyword}
        return await self.make_request("/ai/orth-case/patient-info", data, authorization, we_lang)

    async def get_case_face_list(
            self,
            keyword: str,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """获取面诊列表"""
        data = {"keyword": keyword}
        return await self.make_request("/ai/orth-case/case-face-list", data, authorization, we_lang)

    async def get_case_face_detail(
            self,
            keyword: str,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """获取面诊详情"""
        data = {"keyword": keyword}
        return await self.make_request("/ai/orth-case/face-detail", data, authorization, we_lang)

    async def save_case_face(
            self,
            case_code: Optional[str] = None,
            face_code: Optional[str] = None,
            basic_info: Optional[Dict] = None,
            photo_info: Optional[Dict] = None,
            model_info: Optional[Dict] = None,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """保存面诊信息"""
        data = {
            "case_code": case_code,
            "face_code": face_code,
            "basic_info": basic_info,
            "photo_info": photo_info,
            "model_info": model_info
        }
        # 移除None值
        data = {k: v for k, v in data.items() if v is not None}
        return await self.make_request("/ai/orth-case/face-save", data, authorization, we_lang)

    async def get_order_list(
            self,
            keyword: str,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """获取订单列表"""
        data = {"keyword": keyword}
        return await self.make_request("/ai/orth-case/order-list", data, authorization, we_lang)

    # async def save_model_info(
    #         self,
    #         keyword: str,
    #         model_info: Optional[Dict] = None,
    #         authorization: Optional[str] = None,
    #         we_lang: str = "zh-CN"
    # ) -> Optional[Dict[str, Any]]:
    #     """保存模型信息"""
    #     data = {
    #         "keyword": keyword,
    #         "model_info": model_info
    #     }
    #     return await self.make_request("/ai/orth-case-order/save-model-info", data, authorization, we_lang)

    async def save_check_info(
            self,
            keyword: str,
            check_info: Optional[Dict] = None,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """保存临床诊断信息"""
        data = {
            "keyword": keyword,
            "check_info": check_info
        }
        return await self.make_request("/ai/orth-case-order/save-check-info", data, authorization, we_lang)

    async def save_photo_info(
            self,
            keyword: str,
            photo_info: Dict = None,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """保存影像资料信息"""
        data = {
            "keyword": keyword,
            "photo_info": photo_info
        }
        logger.info(f"保存影像资料信息：{data}")
        return await self.make_request("/ai/orth-case-order/save-photo-info", data, authorization, we_lang)

    async def save_recipe_info(
            self,
            keyword: str,
            recipe_info: Optional[Dict] = None,
            recipe_code: Optional[str] = None,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """保存处方信息"""
        data = {
            "keyword": keyword,
            "recipe_info": recipe_info,
            "recipe_code": recipe_code
        }
        data = {k: v for k, v in data.items() if v is not None}
        return await self.make_request("/ai/orth-case-order/save-recipe-info", data, authorization, we_lang)

    async def get_recipe_list(
            self,
            keyword: str,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """获取处方列表"""
        data = {"keyword": keyword}
        return await self.make_request("/ai/orth-case/recipe-list", data, authorization, we_lang)

    async def get_batch_product_list(
            self,
            keyword: str,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """获取发货批次和产品清单"""
        data = {"keyword": keyword}
        return await self.make_request("/ai/orth-case/batch-product-list", data, authorization, we_lang)

    async def get_stage_num(
            self,
            case_code: str,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """获取阶段调整次数信息"""
        data = {"case_code": case_code}
        return await self.make_request("/ai/orth-case-order/stage-num", data, authorization, we_lang)

    async def submit_stage_adjustment(
            self,
            case_code: str,
            order_number: Optional[str] = None,
            sub_stage_info: Optional[Dict] = None,
            model_info: Optional[Dict] = None,
            check_info: Optional[Dict] = None,
            photo_info: Optional[Dict] = None,
            recipe_info: Optional[Dict] = None,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """提交阶段调整申请"""
        data = {
            "case_code": case_code,
            "order_number": order_number,
            "sub_stage_info": sub_stage_info,
            "model_info": model_info,
            "check_info": check_info,
            "photo_info": photo_info,
            "recipe_info": recipe_info
        }
        data = {k: v for k, v in data.items() if v is not None}
        return await self.make_request("/ai/orth-case-order/sub-stage", data, authorization, we_lang)

    async def get_appliance_list(
            self,
            case_code: str,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """获取补发矫治器列表"""
        data = {"case_code": case_code}
        return await self.make_request("/ai/orth-case/appliance-list", data, authorization, we_lang)

    async def get_appliance_info(
            self,
            order_number: str,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """获取补发矫治器订单信息"""
        data = {"order_number": order_number}
        return await self.make_request("/ai/orth-case/appliance-info", data, authorization, we_lang)

    async def save_appliance(
            self,
            case_code: str,
            step: Optional[str] = None,
            remark: Optional[str] = None,
            consignee: Optional[str] = None,
            consignee_mobile: Optional[str] = None,
            consignee_address: Optional[str] = None,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """保存补发矫治器订单"""
        data = {
            "case_code": case_code,
            "step": step,
            "remark": remark,
            "consignee": consignee,
            "consignee_mobile": consignee_mobile,
            "consignee_address": consignee_address
        }
        data = {k: v for k, v in data.items() if v is not None}
        return await self.make_request("/ai/orth-case/sub-appliance", data, authorization, we_lang)

    async def save_retainer(
            self,
            case_code: str,
            pair_count: Optional[str] = None,
            upper_step: Optional[str] = None,
            lower_step: Optional[str] = None,
            ks_model: Optional[str] = None,
            remark: Optional[str] = None,
            consignee: Optional[str] = None,
            consignee_mobile: Optional[str] = None,
            consignee_address: Optional[str] = None,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """保存保持器订单"""
        data = {
            "case_code": case_code,
            "pair_count": pair_count,
            "upper_step": upper_step,
            "lower_step": lower_step,
            "ks_model": ks_model,
            "remark": remark,
            "consignee": consignee,
            "consignee_mobile": consignee_mobile,
            "consignee_address": consignee_address
        }
        data = {k: v for k, v in data.items() if v is not None}
        return await self.make_request("/ai/orth-case/sub-retainer", data, authorization, we_lang)

    async def check_order_by_case_code(
            self,
            case_code: str,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """获取主订单信息"""
        data = {"case_code": case_code}
        return await self.make_request("/ai/orth-case-order/check-order-by-case-code", data, authorization, we_lang)

    async def submit_order(
            self,
            keyword: str,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """提交订单"""
        data = {"keyword": keyword}
        return await self.make_request("/ai/orth-case-order/submit-order", data, authorization, we_lang)

    async def get_pay_list(
            self,
            keyword: str,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """获取支付记录列表"""
        data = {"keyword": keyword}
        return await self.make_request("/ai/orth-case/pay-list", data, authorization, we_lang)

    async def apply_delivery(
            self,
            order_number: str,
            pair_count: int,
            consignee: str,
            consignee_address: str,
            consignee_mobile: str,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """申请发货"""
        data = {
            "order_number": order_number,
            "pair_count": pair_count,
            "consignee": consignee,
            "consignee_address": consignee_address,
            "consignee_mobile": consignee_mobile
        }
        return await self.make_request("/ai/orth-case/apply-delivery", data, authorization, we_lang)

    async def get_order_remain_periods(
            self,
            order_number: str,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """查询订单的剩余副数(剩余期数)信息"""
        data = {"order_number": order_number}
        return await self.make_request("/ai/orth-case/order-batch-apply", data, authorization, we_lang)

    async def get_retainer_list(
            self,
            case_code: str,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """保持器订单列表，通过病例编号(C开头)查询"""
        data = {"case_code": case_code}
        return await self.make_request("/ai/orth-case/retainer-list", data, authorization, we_lang)



    async def get_retainer_info(
            self,
            order_number: str,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """保持器订单详情信息，通过订单编号(XB开头)查询"""
        data = {"order_number": order_number}
        return await self.make_request("/ai/orth-case/retainer-info", data, authorization, we_lang)

    async def get_order_detail(
            self,
            order_number: str,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """查询订单详情"""
        data = {"order_number": order_number}
        return await self.make_request("/ai/orth-case/order-detail", data, authorization, we_lang)

    # 在 OrthodonticService 类中添加以下方法
    async def execute_command_open_ksapp(
            self,we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """执行打开口扫软件命令"""
        # 根据语言参数返回不同语言的按钮
        if we_lang == "zh-CN":
            button_text = "开启扫描软件"
        else:
            button_text = "Start Scanning Software"
        # 直接返回固定的按钮HTML，与user_case.py中的实现一致
        return {
            "button": f"<button class='ai-custom-button' data-auto-action='executeOpenKsapp'>{button_text}</button>"
        }

    async def get_equity_info(
            self,
            keyword:str = None,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """获取权益信息,通过患者姓名、或患者手机号、或患者编号、或病例编号"""
        data = {"keyword": keyword}
        return await self.make_request("/ai/orth-case/equity-info", data, authorization, we_lang)

    async def get_main_order_info(
            self,
            case_code:str = None,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Optional[Dict[str, Any]]:
        """查询主订单信息"""
        data = {"case_code": case_code}
        return await self.make_request("/ai/orth-case/main-order-info", data, authorization, we_lang)

    async def check_order_editable(
            self,
            keyword: str,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Dict[str, Any]:
        """
        检查订单诊断或者影像资料是否可编辑,返回是否可编辑
        """
        data = {"keyword": keyword}
        return await self.make_request("/ai/orth-case-order/check-order-editable", data, authorization, we_lang)

    async def check_recipe_editable(
            self,
            keyword: str,
            recipe_code: str = None,
            authorization: Optional[str] = None,
            we_lang: str = "zh-CN"
    ) -> Dict[str, Any]:
        """
        检查订单处方是否可编辑,返回是否可编辑
        """
        data = {"keyword": keyword, "recipe_code": recipe_code}
        return await self.make_request("/ai/orth-case-order/check-recipe-editable", data, authorization, we_lang)

# 全局服务实例
orthodontic_service = OrthodonticService()

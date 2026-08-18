from pydantic import BaseModel, Field, model_validator, ValidationError
from typing import Optional,Union
from .validators import _


class OrderApplianceInfoTemplate(BaseModel):
    """ 补发矫治器订单信息（大模型请严格按此结构字段生成数据）:/ Replacement Aligner Order Information (Large models must strictly generate data according to this structure/fields) :
        case_code:病例编号 / Case number
        step:需要补发的矫治器步数 / step
        remark:备注 / remark
        consignee:收货人名称 / Consignee
        consignee_mobile:收货人联系电话 / Consignee mobile phone
        consignee_address:收货人详细地址 / Consignee address
    """
    # 非必填字段
    case_code: Optional[str] = Field(..., description=_("病例编号","Case number"))
    step: Optional[Union[str, int]] = Field(..., description=_("需要补发的矫治器步数","step"))
    remark: Optional[str] = Field(None, description=_("其他事项(备注内容)","remark"))
    consignee: Optional[str] = Field(..., description=_("收货人名称","Consignee"))
    consignee_mobile: Optional[str] = Field(..., description=_("收货人联系电话","Consignee mobile phone"))
    consignee_address: Optional[str] = Field(..., description=_("收货人详细地址","Consignee address"))

    # @model_validator(mode='after')
    def validate_optional_fields(self):
        """
        自定义验证器：对非必填字段进行值校验 / Custom Validator: Validate values for non-required fields
        """
        errors = []

        if self.step is not None:
            if isinstance(self.step,int):
                self.step = str(self.step)

        if self.step is None:
            errors.append(_(f"保存补发矫治器订单信息,请提供‘需要补发的矫治器步数’",
                            f"Save Replacement Aligner Order Information. Please provide the 'Number of Aligner Stages for Replacement'"))

        if self.consignee is None:
            errors.append(_(f"收货人名称不能为空",
                            f"Consignee name cannot be empty"
                            ))

        if self.consignee_mobile is None:
            errors.append(_(f"收货人联系电话不能为空",
                            f"Consignee phone number cannot be empty"))

        if self.consignee_address is None:
            errors.append(_(f"收货人详细地址不能为空",
                            f"Consignee address cannot be empty"))

        # 如果有错误，抛出异常
        if errors:
            raise ValueError("; ".join(errors))

        return  self

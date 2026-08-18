from pydantic import BaseModel, Field, model_validator, ValidationError
from typing import Optional,Union,Annotated


class OrderRetainerInfoTemplate(BaseModel):
    """ 保持器订单信息（大模型请严格按下面定义字段生成数据）:
        # case_code:病例编号
        pair_count:需要定制保持器的数量
        upper_step:上颌矫治步数
        lower_step:下颌矫治步数
        ks_model:模型文件
        remark:备注
        consignee:收货人名称
        consignee_mobile:收货人联系电话
        consignee_address:收货人详细地址
    """
    # case_code: Optional[str] = Field(..., description="病例编号")
    pair_count: Optional[Union[str, int]] = Field(..., description="需要定制保持器的数量")
    upper_step: Optional[Union[str,int]] = Field(None, description="上颌矫治步数")
    lower_step: Optional[Union[str,int]] = Field(None, description="下颌矫治步数")
    ks_model: Optional[Union[str,dict]] = Field(None, description="模型文件")
    remark: Optional[str] = Field(None, description="其他事项(备注内容)")
    consignee: Optional[str] = Field(..., description="收货人名称")
    consignee_mobile: Optional[str] = Field(..., description="收货人联系电话")
    consignee_address: Optional[str] = Field(..., description="收货人详细地址")

    # @model_validator(mode='after')
    def validate_optional_fields(self):
        """
        自定义验证器：对非必填字段进行值校验
        """
        errors = []

        if self.pair_count is not None:
            if isinstance(self.pair_count,str):
                self.pair_count = int(self.pair_count)
        else:
            errors.append(f"需要定制保持器的数量不能为空")

        if self.upper_step is not None:
            if isinstance(self.upper_step,str):
                self.upper_step = int(self.upper_step)

        if self.lower_step is not None:
            if isinstance(self.lower_step,str):
                self.lower_step = int(self.lower_step)

        if self.ks_model is not None:
            if isinstance(self.ks_model,dict):
                file_id = self.ks_model.get('file_id', None)
                if file_id is not None:
                    self.ks_model = file_id
                else:
                    errors.append(f"模型文件数据 {self.ks_model} 异常,请尝试重新提交文件～～")

        if self.consignee is None:
            errors.append(f"收货人名称不能为空")

        if self.consignee_mobile is None:
            errors.append(f"收货人联系电话不能为空")

        if self.consignee_address is None:
            errors.append(f"收货人详细地址不能为空")

        # 如果有错误，抛出异常
        if errors:
            raise ValueError("; ".join(errors))

        return  self

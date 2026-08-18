from pydantic import BaseModel, Field, model_validator, ValidationError
from typing import Optional,List,Union,Any
import re
from models.validators import _


class FaceBasicInfoTemplate(BaseModel):
    """ 基础信息（大模型请严格按此结构生成数据）:
        appendix_exam：附件检查 / Attachment Check|1:脱落 (Detached) 2:完好 (Intact)
        current_wearing_period：当前佩戴期数 / Current wearing period
        op_type：临床操作 / Clinical Procedure|1:片切 (Interproximal Reduction) 2:拔牙 (Extraction) 3:粘贴附件 (Attachment Bonding)
        orth_app_fitting：矫治器贴合 / Aligner Fit|1:磨损 (Worn) 2:无磨损 (No wear) 3:未知 (Unknown)
        other_remark：备注内容 / Remarks
        patient_adherence：患者依从性 / Patient Adherence|1:优 (Excellent) 2:良 (Good) 3:差 (Poor)
        tooth_mob：牙齿松动度(单选) / Tooth Mobility (Single Choice)|1:无松动 (No mobility) 2:松动I度 (Mobility I) 3:松动II度 (Mobility II) 4:松动III度 (Mobility III)
    """
    # 非必填字段
    appendix_exam: Optional[Union[str, int]] = Field(None, description="附件检查 / Attachment Check|1:脱落 (Detached) 2:完好 (Intact)")# 单选,将枚举值转为整数值
    current_wearing_period: Optional[Union[str, int]] = Field(None, description="当前佩戴期数 / Current wearing period") # 将枚举值转为字符串值
    op_type: Optional[Union[List[Any],str,int]] = Field(None, description="临床操作 / Clinical Procedure|1:片切 (Interproximal Reduction) 2:拔牙 (Extraction) 3:粘贴附件 (Attachment Bonding)")# 多选，列表格式
    orth_app_fitting: Optional[Union[str, int]] = Field(None, description="矫治器贴合 / Aligner Fit|1:磨损 (Worn) 2:无磨损 (No wear) 3:未知 (Unknown)")# 单选，将枚举值转为整数值
    other_remark: Optional[str] = Field(None, description="备注内容 / Remarks")# 将值转为字符串值
    patient_adherence: Optional[Union[str, int]] = Field(None, description="患者依从性 / Patient Adherence|1:优 (Excellent) 2:良 (Good) 3:差 (Poor)")# 单选，将枚举值转为整数值
    tooth_mob: Optional[Union[str, int]] = Field(None, description="牙齿松动度(单选) / Tooth Mobility (Single Choice)|1:无松动 (No mobility) 2:松动I度 (Mobility I) 3:松动II度 (Mobility II) 4:松动III度 (Mobility III)")# 单选，将枚举值转为整数值


    @model_validator(mode='after')
    def validate_optional_fields(self):
        """
        自定义验证器：对非必填字段进行值校验
        """
        errors = []

        if self.appendix_exam is not None:
            if isinstance(self.appendix_exam,str):
                self.appendix_exam = int(self.appendix_exam)
            if self.appendix_exam not in [1, 2]:
                # errors.append(f"附件检查 的值 {self.appendix_exam} 不在允许范围内,请具体描述‘附件检查的选项内容为：脱落|完好’")
                errors.append(_(f"附件检查 的值 {self.appendix_exam} 不在允许范围内,请具体描述‘附件检查的选项内容为：脱落|完好’",
                                f"The value {self.appendix_exam} for Attachment Examination is out of the allowed range. Please describe specifically. The options for Attachment Examination are: Detached | Intact"
                            ))


        if self.current_wearing_period is not None:
            if isinstance(self.current_wearing_period,int):
                self.current_wearing_period = str(self.current_wearing_period)

        # # 校验 op_type 是否为 "片切"、"拔牙"、"粘贴附件"
        if self.op_type is not None:
            # 校验类型是否为字符串
            if isinstance(self.op_type, str):
                data = self.op_type.strip()
                self.op_type = [int(x) for x in re.split(r'[;,，、]', data) if x]
            # 校验类型是否为整数
            if isinstance(self.op_type, int):
                self.op_type = [self.op_type]
            # 校验类型是否为列表
            if not isinstance(self.op_type, list):
                # errors.append(f"临床操作 的值 {self.op_type} 不在允许范围内,请具体描述‘临床操作的选项内容：片切|拔牙|粘贴附件’")
                errors.append(_(f"临床操作 的值 {self.op_type} 不在允许范围内,请具体描述‘临床操作的选项内容：片切|拔牙|粘贴附件’",
                                f"The value {self.op_type} for Clinical Procedure is out of the allowed range. Please describe specifically. The options for Clinical Procedure are: Interproximal Reduction (IPR) | Extraction | Attachment Bonding"
                            ))
            for i, val in enumerate(self.op_type):
                # 校验每个元素是否为整数
                num = int(val)
                if not isinstance(num, int):
                    # errors.append(f"临床操作的元素值错误-1，请具体描述‘临床操作的选项内容：片切|拔牙|粘贴附件’")
                    errors.append(_(f"临床操作的元素值错误-1，请具体描述‘临床操作的选项内容：片切|拔牙|粘贴附件’",
                                    f"The value -1 for Clinical Procedure is invalid. Please describe specifically. The options for Clinical Procedure are: Interproximal Reduction (IPR) | Extraction | Attachment Bonding"
                                    ))
                # 校验每个元素是否在允许范围内
                if num not in [1, 2, 3]:
                    # errors.append(f"临床操作的元素值错误-2，请具体描述‘临床操作的选项内容：片切|拔牙|粘贴附件’")
                    errors.append(_(f"临床操作的元素值错误-2，请具体描述‘临床操作的选项内容：片切|拔牙|粘贴附件’",
                                    f"The element value -2 for Clinical Procedure is invalid. Please describe specifically. The options for Clinical Procedure are: Interproximal Reduction (IPR) | Extraction | Attachment Bonding"
                                    ))
                    # raise ValueError(f"临床操作的元素值错误，请具体描述‘临床操作的选项内容：片切|拔牙|粘贴附件’")

        # 校验 orth_app_fitting 是否为 1、2、3
        if self.orth_app_fitting is not None:
            if isinstance(self.orth_app_fitting,str):
                self.orth_app_fitting = int(self.orth_app_fitting)
            if self.orth_app_fitting not in [1, 2, 3]:
                # errors.append(f"矫治器贴合 的值 {self.orth_app_fitting} 不在允许范围内,请具体描述‘矫治器贴合的选项内容：磨损|无磨损|未知’")
                errors.append(_(f"矫治器贴合 的值 {self.orth_app_fitting} 不在允许范围内,请具体描述‘矫治器贴合的选项内容：磨损|无磨损|未知’",
                                f"The value {self.orth_app_fitting} for Aligner Fit is out of the allowed range. Please describe specifically. The options for Aligner Fit are: Worn | No Wear | Unknown"
                                ))
        # 校验 patient_adherence 是否为 1、2、3
        if self.patient_adherence is not None:
            if isinstance(self.patient_adherence,str):
                self.patient_adherence = int(self.patient_adherence)
            if self.patient_adherence not in [1, 2, 3]:
                # errors.append(f"患者依从性 的值 {self.patient_adherence} 不在允许范围内,请具体描述‘患者依从性的选项内容：优|良|差’")
                errors.append(_(f"患者依从性 的值 {self.patient_adherence} 不在允许范围内,请具体描述‘患者依从性的选项内容：优|良|差’",
                                f"The value {self.patient_adherence} for Patient Adherence is out of the allowed range. Please describe specifically. The options for Patient Adherence are: Excellent | Good | Poor"
                                ))

        # 校验 tooth_mob 是否为 1、2、3、4
        if self.tooth_mob is not None:
            if isinstance(self.tooth_mob,str):
                self.tooth_mob = int(self.tooth_mob)
            if self.tooth_mob not in [1, 2, 3, 4]:
                # errors.append(f"牙齿松动度 的值 {self.tooth_mob} 不在允许范围内,请具体描述‘牙齿松动度的选项内容：无松动|松动I度|松动II度|松动III度’")
                errors.append(_(f"牙齿松动度 的值 {self.tooth_mob} 不在允许范围内,请具体描述‘牙齿松动度的选项内容：无松动|松动I度|松动II度|松动III度’",
                                f"The value {self.tooth_mob} for Tooth Mobility is out of the allowed range. Please describe specifically. The options for Tooth Mobility are: No Mobility | Mobility Grade I | Mobility Grade II | Mobility Grade III"
                                ))

        # 如果有错误，抛出异常
        if errors:
            raise ValueError("; ".join(errors))

        return  self



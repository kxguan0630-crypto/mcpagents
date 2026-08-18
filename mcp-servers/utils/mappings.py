# imageType 映射关系
import json
from typing import Dict, Any

IMAGE_TYPE_MAPPING = {
    "FrontalClosedPhoto": "face_close",
    "FrontalOcclusion": "mouth_front",
    "FrontalSmilePhoto": "face_open",
    "FullJawTomography": "xray_front",
    "LateralPhoto": "face_side",
    "MandibularDentition": "mouth_lower",
    "MaxillaryDentition": "mouth_upper",
    "OcclusalLeft": "mouth_left",
    "OcclusalRight": "mouth_right",
    "OverbiteAndOverjet": "mouth_cover",
    "SlopingPhoto": "face_smile",
    "XRayLateral": "xray_side",
    "Unintended": "other_file",
    "Signature": ["sign_one","sign_two"]
}

# orientation 映射关系
ORIENTATION_MAPPING = {
    "Up": 0,
    "Left": 1,
    "Right": -1,
    "Down": 2
}

def transform_image_data(image_process_result)-> Dict[str, Any]:
    """
    将 image_process 工具返回的结果转换为符合 PhotoInfoTemplate 格式的字典
     所有字段值都会转换为字符串，嵌套的 JSON 也会转义为字符串格式

    Args:
        image_process_result (dict): image_process 工具返回的结果

    Returns:
        dict: 转换后的数据字典，所有字段值都是字符串
    """
    transformed_data = {}
    signature_count = 0  # 用于记录 Signature 类型图片的数量

    if not image_process_result.get("isSucceed", False):
        raise ValueError("图片处理失败，请检查image_process工具的返回值")

    result_list = image_process_result.get("data", {}).get("result", [])
    if not result_list:
        raise ValueError("图片处理结果为空，请检查image_process工具的返回值")

    for item in result_list:
        image_type = item.get("imageType")
        file_id = item.get("fileId")
        orientation = item.get("orientation")

        target_field = IMAGE_TYPE_MAPPING.get(image_type)
        if not target_field:
            continue

        deg = ORIENTATION_MAPPING.get(orientation, 0)
        image_data = {
            "file_id": str(file_id) if file_id else "",
            "score": item.get("score", 0.0),
            "imageType": str(item.get("imageType", "")),
            "deg": deg,
            "h": 1,
            "v": 1
        }

        if image_type == "Signature":
            if signature_count < len(IMAGE_TYPE_MAPPING["Signature"]):
                target_key = IMAGE_TYPE_MAPPING["Signature"][signature_count]
                transformed_data[target_key] = image_data
                signature_count += 1
        else:
            if isinstance(target_field, list):
                for field in target_field:
                    transformed_data[field] = image_data
            else:
                transformed_data[target_field] = image_data


    return transformed_data
# tools/image_process.py
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from services.orthodontic_service import orthodontic_service
from utils.mappings import transform_image_data
import logging

logger = logging.getLogger("SERVER_LOGGER")
# Initialize FastMCP server
mcp = FastMCP("image_processing")


@mcp.tool()
async def image_process(
        image_list: List[Dict[str, Any]],
        authorization: str = None,
        we_lang: str = "zh-CN"
) -> Dict[str, Any]:
    """
    影像图片处理工具 / Image Processing Tool

    重要规则:
    如果用户上传的图片数量超过4张,则分批去调用此工具去处理.每次最多处理4张,当处理完所有图片后,才把所有图片的结果返回给用户.
    If the user uploads more than 4 images, call this tool in batches to process them. Process a maximum of 4 images at a time. Only return all image results to the user after all images have been processed.

    处理用户上传的口腔医学影像图片，返回处理后的图像数据
    Process uploaded dental medical images and return processed image data

    功能 / Functions:
    - 自动识别图片类型 (口内照、口外照、X 光片等) / Automatically identify image type (intraoral, extraoral, X-ray, etc.)
    - 评估图片质量并打分 / Evaluate image quality and score
    - 转换图片方向信息 / Convert image orientation information
    - 生成符合 PhotoInfoTemplate 格式的数据 / Generate data in PhotoInfoTemplate format

    Args:
        image_list: 用户上传的图片列表，从用户的上传文件信息中获取 file_id,url 的值，按照 fileId,url 字段组合成字典，然后放到列表中
                    List of images uploaded by user, get file_id and url values from user's upload file information,
                    combine into dictionary according to fileId and url fields, then put into list
        authorization: 可选的 Authorization Token，默认为 None / Optional Authorization token, default is None
        we_lang: 语言设置，默认为"zh-CN" / Language setting, default is "zh-CN"

    Returns:
        处理后的图像数据，包含以下字段:
        Processed image data with the following fields:
        - face_close: 正面闭合照片 / Frontal closed photo
        - face_open: 正面开口微笑照片 / Frontal open smile photo
        - face_side: 侧立照片 / Lateral photo
        - face_smile: 侧 45 度微笑照片 / 45-degree smile photo
        - mouth_upper: 上颌照片 / Maxillary dentition
        - mouth_lower: 下颌照片 / Mandibular dentition
        - mouth_front: 正面咬合照片 / Frontal occlusion
        - mouth_left: 咬合左侧位照片 / Left occlusal
        - mouth_right: 咬合右侧位照片 / Right occlusal
        - mouth_cover: 覆合覆盖照片 / Overbite and overjet
        - xray_front: 全颌曲面断层照片 / Full jaw tomography
        - xray_side: 头颅侧位定位片 / X-ray lateral
        - sign_one: 签名第一张照片 / First signature photo
        - sign_two: 签名第二张照片 / Second signature photo

        每张照片包含 / Each photo includes:
        - file_id: 文件 ID / File ID
        - score: 质量评分 / Quality score
        - imageType: 图片类型 / Image type
        - deg: 旋转角度 / Rotation angle
        - h: 水平方向 / Horizontal direction
        - v: 垂直方向 / Vertical direction
    """
    lang_msg = "开始处理影像图片" if we_lang == "zh-CN" else "Start processing images"
    logger.info(f'{lang_msg}, 语言/Lang: {we_lang}')

    try:
        # 处理图像列表，将 file_id 转换为 fileId
        # Process image list, convert file_id to fileId
        processed_images = []
        for image in image_list:
            processed_image = image.copy()
            # 如果存在 file_id，则转换为 fileId
            # If file_id exists, convert to fileId
            if 'file_id' in processed_image:
                processed_image['fileId'] = processed_image.pop('file_id')
            processed_images.append(processed_image)

        logger.info(f'处理图像列表/Processing image list: {processed_images}')

        data = await orthodontic_service.process_images(
            image_list=processed_images,
            authorization=authorization,
            we_lang=we_lang
        )

        success_msg = "图片处理成功" if we_lang == "zh-CN" else "Image processing successful"
        logger.info(f'{success_msg}/Result: {data}')

        if not data:
            error_msg = "图像处理失败" if we_lang == "zh-CN" else "Image processing failed"
            return {"message": error_msg, "code": 30000}

        return transform_image_data(data)

    except Exception as e:
        error_msg = "图像处理时发生错误" if we_lang == "zh-CN" else "Error during image processing"
        logger.error(f"{error_msg}: {e}")
        return {"message": f"{error_msg}: {str(e)}", "code": 50000}

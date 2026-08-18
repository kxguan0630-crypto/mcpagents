"""影像处理相关的确定性规则。

这里不负责理解用户说了什么，也不负责保存面诊资料。
它只处理一个很明确的技术规则：image_process 单次最多处理 4 张图片。

这样“超过 4 张图片需要分批”不再依赖 LLM 是否记住 Tool Description。
"""

from __future__ import annotations

from typing import Any

IMAGE_BATCH_SIZE = 4


def split_image_batches(images: list[dict[str, Any]], batch_size: int = IMAGE_BATCH_SIZE) -> list[list[dict[str, Any]]]:
    """按照 image_process 的单次上限切分图片。

    例如 10 张图片会得到 4 + 4 + 2 三批。
    空列表返回空列表，避免产生无意义的工具调用。
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")
    return [images[i:i + batch_size] for i in range(0, len(images), batch_size)]


def merge_image_results(results: list[Any]) -> Any:
    """合并多批 image_process 的结果。

    image_process 当前返回结构由服务端决定，因此这里尽量保持原始结构：
    - 如果结果都是 dict，则按字段合并；同名列表会追加。
    - 如果无法安全合并，则返回原始结果列表，不猜测业务字段。
    """
    if len(results) == 1:
        return results[0]
    if not results:
        return {}

    if not all(isinstance(item, dict) for item in results):
        return results

    merged: dict[str, Any] = {}
    for result in results:
        for key, value in result.items():
            if key not in merged:
                merged[key] = value
            elif isinstance(merged[key], list) and isinstance(value, list):
                merged[key].extend(value)
            elif merged[key] in (None, ""):
                merged[key] = value
            elif value in (None, ""):
                continue
            else:
                # 同一字段出现不同标量结果时，不覆盖已有结果，避免静默丢数据。
                merged[key] = [merged[key], value]
    return merged

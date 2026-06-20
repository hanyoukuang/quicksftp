# utils/file_utils.py
import os
from typing import Tuple

import mimetypes

def is_binary(filename: str) -> bool:
    """
    使用 Python 内置的 mimetypes 库进行准确的二进制文件判断。
    相比硬编码扩展名列表，mimetypes 支持更广泛的标准 MIME 类型，
    并能够自动适配操作系统的 MIME 数据库。

    :param filename: 文件名或包含文件名的路径
    :return: 如果判断为二进制文件返回 True，否则返回 False
    """
    if not mimetypes.inited:
        mimetypes.init()
        
    mime_type, _ = mimetypes.guess_type(filename)
    
    if mime_type is None:
        # 如果 mimetypes 无法识别（例如无后缀的文件），使用黑名单过滤绝对的二进制类型
        _, ext = os.path.splitext(filename.lower())
        fallback_binaries = {
            ".bin", ".dat", ".pyc", ".pyo", ".class", ".exe", ".dll", 
            ".so", ".o", ".a", ".lib", ".db", ".sqlite", ".iso", ".img", 
            ".dmg", ".apk", ".ipa", ".elf", ".rom"
        }
        return ext in fallback_binaries

    # 明确是 text/* 类型的肯定是文本
    if mime_type.startswith("text/"):
        return False
        
    # 一些 application/* 类型其实是纯文本格式
    text_application_types = {
        "application/json",
        "application/xml",
        "application/javascript",
        "application/x-javascript",
        "application/x-sh",
        "application/x-python-code",
        "application/sql",
        "application/yaml",
        "application/x-yaml",
        "application/toml",
    }
    if mime_type in text_application_types:
        return False
        
    # 其余 (image/*, video/*, audio/*, 大部分 application/*) 都认为是二进制
    return True


def path_stand(src: str, loc: str) -> Tuple[str, str]:
    """
    统一路径格式，并拼接目标路径。
    将 Windows 风格的反斜杠转换为斜杠，并去除末尾的斜杠，
    最后根据源文件/目录名生成在目标位置的完整路径。

    :param src: 源文件/目录路径
    :param loc: 目标存放位置的父目录路径
    :return: 格式化后的 (源路径, 拼接后的目标完整路径)
    """
    # 统一转换路径分隔符并去掉末尾的斜杠
    src_standard = src.replace("\\", "/").rstrip("/")
    loc_standard = loc.replace("\\", "/").rstrip("/")

    # 获取源路径的最后一部分（文件名或最底层目录名）
    target_name = src_standard.split("/")[-1]

    # 拼接出完整的目标路径
    loc_full = "/".join((loc_standard, target_name))

    return src_standard, loc_full

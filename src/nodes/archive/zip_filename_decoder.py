"""
ZIP文件名解码模块

提供可靠的ZIP文件名解码方案，支持：
- 检测ZIP规范中的UTF-8标志位
- 自动处理中文环境常见编码问题
- 兼容日文、韩文等多语言环境

典型用法：
>>> from nodes.archive.zip_filename_decoder import decode_zip_filename
>>> raw_name = b'\\x82\\xa0\\x82\\xa2'  # Shift-JIS编码的示例
>>> decoded = decode_zip_filename(raw_name, 0)
"""

import logging
from typing import Tuple, List

# 配置模块级日志
logger = logging.getLogger(__name__)

# 预定义编码检测顺序（基于中文环境优化）
ENCODING_PAIRS: List[Tuple[str, str]] = [
    ('cp437', 'gbk'),      # Windows简体中文默认
    ('cp437', 'gb18030'),  # 国家标准扩展
    ('cp437', 'big5'),     # 繁体中文
    ('cp932', 'shift-jis'),# 日文
    ('cp949', 'euc-kr'),   # 韩文
    ('utf-8', 'utf-8')     # 直接UTF-8回退
]

def decode_zip_filename(raw_bytes: bytes, flag_bits: int) -> str:
    """
    增强版ZIP文件名解码器
    
    参数：
    - raw_bytes: 从ZIP文件头获取的原始字节
    - flag_bits: ZIP文件头的flag_bits（用于检测UTF-8标志）
    
    返回：
    - 解码后的文件名字符串
    
    异常：
    - 不会抛出异常，无法解码时返回替换字符
    """
    try:
        # 检测ZIP UTF-8标志位（0x0800）
        if flag_bits & 0x800:
            logger.debug("检测到ZIP UTF-8标志，尝试UTF-8解码")
            try:
                return raw_bytes.decode('utf-8')
            except UnicodeDecodeError as e:
                logger.warning(f"UTF-8标志位解码失败: {e}")

        # 多重编码尝试
        for src_enc, dst_enc in ENCODING_PAIRS:
            try:
                # 直接解码尝试
                decoded = raw_bytes.decode(dst_enc)
                logger.debug(f"直接解码成功: {dst_enc}")
                return decoded
            except UnicodeDecodeError:
                try:
                    # 二次编码转换尝试
                    decoded = raw_bytes.decode(src_enc).encode(src_enc).decode(dst_enc)
                    logger.debug(f"二次解码成功: {src_enc}->{dst_enc}")
                    return decoded
                except (UnicodeDecodeError, UnicodeEncodeError) as e:
                    logger.debug(f"编码尝试失败 {src_enc}->{dst_enc}: {e}")
                    continue

        # 最终回退方案
        logger.warning("所有编码尝试失败，使用UTF-8替换模式")
        return raw_bytes.decode('utf-8', errors='replace')

    except Exception as e:
        logger.error(f"解码过程中发生意外错误: {e}")
        return raw_bytes.decode('utf-8', errors='replace')

def test_decode_zip_filename():
    """模块自带的测试用例"""
    test_cases = [
        (b'\xcf\x84\xe2\x94\x82\xe2\x95\x94\xc2\xbd', 0x800, "UTF-8带BOM测试"),
        (b'\x82\xa0\x82\xa2', 0, "Shift-JIS测试"),         # 示例：あい
        (b'\xc4\xe3\xba\xc3', 0, "GBK测试"),               # 示例：你好 
        (b'\xa7\x41\xa6\x6e', 0, "Big5测试"),              # 示例：測試
        (b'\xbe\xc8\xb3\xe6', 0, "EUC-KR测试"),            # 示例：안녕
        (b'\x1b$B$3$s$K$A$O', 0, "ISO-2022-JP测试")       # 示例：こんにちは
    ]
    
    for data, flags, desc in test_cases:
        result = decode_zip_filename(data, flags)
        print(f"测试用例 [{desc}]:")
        print(f"原始字节: {data}")
        print(f"解码结果: {result}\n")

if __name__ == "__main__":
    # 直接运行该文件可以执行测试用例
    logging.basicConfig(level=logging.DEBUG)
    test_decode_zip_filename() 
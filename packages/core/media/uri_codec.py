from urllib.parse import quote, unquote
from pathlib import Path

def encode_uri(file_path: str) -> str:
    """编码为存储用URI（仅处理必要字符）"""
    return quote(
        Path(file_path).as_posix(),
        safe='/!*()@:&=+$,;',  # 保留常见路径符号
        encoding='utf-8'
    )

def decode_uri(uri: str) -> str:
    """解码为显示用路径"""
    return unquote(uri)
# 存储时（数据交换）
file_path = "E:/テスト目录/日本語 file 测试.avif"
storage_uri = encode_uri(file_path)
# → E:/%E3%83%86%E3%82%B9%E3%83%88%E7%9B%AE%E5%BD%95/%E6%97%A5%E6%9C%AC%E8%AA%9E%20file%20%E6%B5%8B%E8%AF%95.avif

# 显示时（日志/界面）
display_path = decode_uri(storage_uri)
print(display_path)
# → E:/テスト目录/日本語 file 测试.avif
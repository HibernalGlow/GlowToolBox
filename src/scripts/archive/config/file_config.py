import os
from pathlib import Path
# 必须包含这些大写变量名
VIPSHOME = r'D:\1VSCODE\1ehv\other\vips\bin'
CJXL_PATH = Path(r'D:\1VSCODE\1ehv\other\cjxl\cjxl.exe')
# ...其他变量定义...
# 全局常量
INCLUDED_KEYWORDS = ['汉化', '官方', '中文', '漢化', '掃', '修正', '制', '譯', '个人', '翻', '製', '嵌', '訳', '淫书馆']
PERFORMANCE_CONFIG_PATH = r"D:\1VSCODE\1ehv\archive\config\performance_config.py"
ENCRYPTION_KEY = 'HibernalGlow'
FILENAME_MAPPING_FILE = 'filename_mapping.json'

# 图片转换配置
IMAGE_CONVERSION_CONFIG = {
    'source_formats': {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.avif', '.jxl'},
    'target_format': '.avif',
    'webp_config': {
        'quality': 90,
        'method': 4,
        'lossless': False,
        'strip': True
    },
    'avif_config': {
        'quality': 90,
        'speed': 7,
        'chroma_quality': 100,
        'lossless': False,
        'strip': True
    },
    'jxl_config': {
        'quality': 90,
        'effort': 7,
        'lossless': False,
        'modular': False,
        'jpeg_recompression': False,
        'jpeg_lossless': False,
        'strip': True
    },
    'jpeg_config': {
        'quality': 90,
        'optimize': True,
        'strip': True
    },
    'png_config': {
        'optimize': True,
        'compress_level': 6,
        'strip': True
    }
}

# 文件格式配置
SUPPORTED_ARCHIVE_FORMATS = {'.zip', '.cbz'}
VIDEO_FORMATS = {'.mp4', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.mov', '.m4v', '.mpg', '.mpeg', '.3gp', '.rmvb'}
AUDIO_FORMATS = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac', '.wma', '.opus', '.ape', '.alac'}
EXCLUDED_IMAGE_FORMATS = {'.jxl', '.avif', '.webp', '.gif', '.psd', '.ai', '.cdr', '.eps', '.svg', '.raw', '.cr2', '.nef', '.arw', '.dng', '.tif', '.tiff'}

# 效率检查配置
EFFICIENCY_CHECK_CONFIG = {
    'min_files_to_check': 3,
    'min_efficiency_threshold': 10,
    'max_inefficient_files': 3
}

# 添加cjxl路径到全局配置
CJXL_PATH = Path(r'D:\1VSCODE\1ehv\other\cjxl\cjxl.exe')
DJXL_PATH = Path(r'D:\1VSCODE\1ehv\other\cjxl\djxl.exe')

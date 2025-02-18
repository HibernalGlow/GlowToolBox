import os
import json
from pathlib import Path



import os

class Settings:
    """全局配置类"""
    # 日志相关
    verbose_logging = True
    
    # 路径处理相关
    use_direct_path_mode = True
    
    # 图片处理相关
    filter_height_enabled = True
    remove_grayscale = True
    min_size = 631
    
    # 日志记录相关
    add_processed_log_enabled = True
    ignore_processed_log = True
    
    # 性能相关
    max_workers = min(4, os.cpu_count() or 4)
    
    # 功能开关
    backup_removed_files_enabled = True
    use_clipboard = False
    
    # UI相关
    has_tui = True
    use_debugger = False
    
    # 哈希文件相关
    hash_collection_file = os.path.expanduser(r"E:\1EHV\image_hashes_collection.json")
    hash_files_list = os.path.expanduser(r"E:\1EHV\hash_files_list.txt")
    
    # 哈希计算参数
    hash_params = {
        'hash_size': 10,
        'hash_version': 1
    } 

    # 全局配置
    GLOBAL_HASH_CACHE = os.path.expanduser(r"E:\1EHV\image_hashes_global.json")
    HASH_COLLECTION_FILE = os.path.expanduser(r"E:\1EHV\image_hashes_collection.json")  # 修改为collection
    HASH_FILES_LIST = os.path.expanduser(r"E:\1EHV\hash_files_list.txt")

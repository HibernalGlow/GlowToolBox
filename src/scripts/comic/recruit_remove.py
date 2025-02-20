import os
import sys
import json
import hashlib
import argparse
import subprocess
from pathlib import Path
from typing import Optional, List
import logging
from datetime import datetime
# 添加TextualLogger导入

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nodes.tui.textual_logger import TextualLoggerManager
from nodes.pics.hash_process_config import get_latest_hash_file_path, process_artist_folder, process_duplicates
from nodes.record.logger_config import setup_logger

# 在全局配置部分添加以下内容
# ================= 日志配置 =================
config = {
    'script_name': 'recruit_remove',
}
logger, config_info = setup_logger(config)

# 参数配置
DEFAULT_PARAMS = {
    'ref_hamming_distance': 16,  # 与外部参考文件比较的汉明距离阈值
    'hamming_distance': 0,  # 内部去重的汉明距离阈值
    'self_redup': False,  # 是否启用自身去重复
    'remove_duplicates': True,  # 是否启用重复图片过滤
    'hash_size': 10,  # 哈希值大小
    'filter_white_enabled': False,  # 是否启用白图过滤
    'recruit_folder': r'E:\1EHV\[01杂]\zzz去图',  # 画师文件夹
}

# TextualLogger布局配置
TEXTUAL_LAYOUT = {
    "current_stats": {
        "ratio": 2,
        "title": "📊 总体进度",
        "style": "lightyellow"
    },
    "current_progress": {
        "ratio": 2,
        "title": "🔄 当前进度",
        "style": "lightcyan"
    },
    "process_log": {
        "ratio": 3,
        "title": "📝 处理日志",
        "style": "lightpink"
    },
    "update_log": {
        "ratio": 3,
        "title": "ℹ️ 更新日志",
        "style": "lightblue"
    },
}

# 常量设置
WORKER_COUNT = 2  # 线程数
FORCE_UPDATE = False  # 是否强制更新哈希值

def init_TextualLogger():
    TextualLoggerManager.set_layout(TEXTUAL_LAYOUT, config_info['log_file'])

def process_single_path(path: Path, workers: int = 4, force_update: bool = False, params: dict = None) -> bool:
    """处理单个路径
    
    Args:
        path: 输入路径
        workers: 线程数
        force_update: 是否强制更新
        params: 参数字典，包含处理参数
        
    Returns:
        bool: 是否处理成功
    """
    try:
        logging.info(f"[#process_log]\n🔄 处理路径: {path}")
        
        recruit_folder=Path(params['recruit_folder']).resolve()
        # 处理画师文件夹，生成哈希文件
        hash_file = process_artist_folder(recruit_folder, workers, force_update)
        if not hash_file:
            return False
            
        logging.info(f"[#update_log]✅ 生成哈希文件: {hash_file}")
        
        # 处理重复文件
        logging.info(f"[#process_log]\n🔄 处理重复文件 {path}")
        process_duplicates(hash_file, [str(path)], params, workers)
        
        logging.info(f"[#update_log]✅ 处理完成: {path}")
        return True
        
    except Exception as e:
        logging.info(f"[#process_log]❌ 处理路径时出错: {path}: {e}")
        return False

def main():
    """主函数"""
    # 获取路径列表
    print("请输入要处理的路径（每行一个，输入空行结束）:")
    paths = []
    while True:
        path = input().strip().replace('"', '')
        if not path:
            break
        paths.append(Path(path))
    if not paths:
        print("[#process_log]❌ 未输入任何路径")
        return
        
    print("[#process_log]\n🚀 开始处理...")
    
    # 准备参数
    params = DEFAULT_PARAMS.copy()
    recruit_folder = Path(params['recruit_folder']).resolve()
    
    # 处理画师文件夹，生成哈希文件
    hash_file = process_artist_folder(recruit_folder, WORKER_COUNT, FORCE_UPDATE)
    if not hash_file:
        logging.info("[#process_log]❌ 无法生成哈希文件")
        return
    
    success_count = 0
    total_count = len(paths)
    
    for i, path in enumerate(paths, 1):
        logging.info(f"[#process_log]\n=== 处理第 {i}/{total_count} 个路径 ===")
        logging.info(f"[#process_log]路径: {path}")
        
        # 更新进度
        progress = int((i - 1) / total_count * 100)
        logging.debug(f"[#current_progress]当前进度: [{('=' * int(progress/5))}] {progress}%")
        logging.info(f"[#current_stats]总路径数: {total_count} 已处理: {i-1} 成功: {success_count} 总进度: [{('=' * int(progress/5))}] {progress}%")
        
        # 处理重复文件
        try:
            process_duplicates(hash_file, [str(path)], params, WORKER_COUNT)
            success_count += 1
        except Exception as e:
            logging.info(f"[#process_log]❌ 处理失败: {path}: {e}")
        
        # 更新最终进度
        progress = int(i / total_count * 100)
        logging.debug(f"[#current_progress]当前进度: [{('=' * int(progress/5))}] {progress}%")
        logging.info(f"[#current_stats]总路径数: {total_count}\n已处理: {i}\n成功: {success_count}\n总进度: [{('=' * int(progress/5))}] {progress}%")
            
    logging.info(f"[#update_log]\n✅ 所有处理完成: 成功 {success_count}/{total_count}")

if __name__ == "__main__":
    main() 
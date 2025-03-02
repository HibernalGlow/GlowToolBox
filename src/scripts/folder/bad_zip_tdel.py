import os
import subprocess
import json  # 将yaml改为json
from datetime import datetime
import concurrent.futures
from functools import partial
import shutil
import argparse
import pyperclip
from pathlib import Path
import sys
import logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nodes.tui.textual_logger import TextualLoggerManager
from nodes.record.logger_config import setup_logger

# 获取脚本所在目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 将历史文件从yaml改为json
HISTORY_FILE = os.path.join(SCRIPT_DIR, 'archive_check_history.json')

# 配置日志面板布局
TEXTUAL_LAYOUT = {
    "status": {
        "ratio": 2,
        "title": "📊 状态信息",
        "style": "lightblue"
    },
    "progress": {
        "ratio": 2,
        "title": "🔄 处理进度",
        "style": "lightcyan"
    },
    "success": {
        "ratio": 3,
        "title": "✅ 成功信息",
        "style": "lightgreen"
    },
    "warning": {
        "ratio": 2,
        "title": "⚠️ 警告信息",
        "style": "lightyellow"
    },
    "error": {
        "ratio": 2,
        "title": "❌ 错误信息",
        "style": "lightred"
    }
}

# 初始化日志
config = {
    'script_name': 'bad_zip_tdel',
    'console_enabled': False
}
logger, config_info = setup_logger(config)

def load_check_history():
    """加载检测历史记录（从JSON文件）"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f) or {}
        except json.JSONDecodeError:
            logger.error(f"[#error] 历史记录文件格式错误，将创建新的历史记录")
            return {}
    return {}

def save_check_history(history):
    """保存检测历史记录（到JSON文件）"""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def check_archive(file_path):
    """检测压缩包是否损坏"""
    try:
        result = subprocess.run(['7z', 't', file_path], 
                              capture_output=True, 
                              text=True)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"[#error] ❌ 检测文件 {file_path} 时发生错误: {str(e)}")
        return False

def get_archive_files(directory, archive_extensions):
    """快速收集需要处理的文件"""
    for root, _, files in os.walk(directory):
        for filename in files:
            if any(filename.lower().endswith(ext) for ext in archive_extensions):
                yield os.path.join(root, filename)

def get_paths_from_clipboard():
    """从剪贴板读取多行路径"""
    try:
        clipboard_content = pyperclip.paste()
        if not clipboard_content:
            return []
            
        paths = [
            Path(path.strip().strip('"').strip("'"))
            for path in clipboard_content.splitlines() 
            if path.strip()
        ]
        
        valid_paths = [
            path for path in paths 
            if path.exists()
        ]
        
        if valid_paths:
            logger.info(f"[#status] 📋 从剪贴板读取到 {len(valid_paths)} 个有效路径")
        else:
            logger.warning("[#warning] ⚠️ 剪贴板中没有有效路径")
            
        return valid_paths
        
    except Exception as e:
        logger.error(f"[#error] ❌ 读取剪贴板时出错: {e}")
        return []

def process_directory(directory, skip_checked=False, max_workers=4):
    """处理目录下的所有压缩包文件"""
    archive_extensions = ('.zip', '.rar', '.7z', '.cbz')
    check_history = load_check_history()
    
    # 删除temp_开头的文件夹
    for root, dirs, _ in os.walk(directory, topdown=True):
        for dir_name in dirs[:]:  # 使用切片创建副本以避免在迭代时修改列表
            if dir_name.startswith('temp_'):
                try:
                    dir_path = os.path.join(root, dir_name)
                    logger.info(f"[#status] 🗑️ 正在删除临时文件夹: {dir_path}")
                    shutil.rmtree(dir_path)
                except Exception as e:
                    logger.error(f"[#error] 删除文件夹 {dir_path} 时发生错误: {str(e)}")

    # 收集需要处理的文件
    files_to_process = []
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.lower().endswith(archive_extensions):
                file_path = os.path.join(root, filename)
                if file_path.endswith('.tdel'):
                    continue
                if skip_checked and file_path in check_history and check_history[file_path]['valid']:
                    logger.info(f"[#status] ⏭️ 跳过已检查且完好的文件: {file_path}")
                    continue
                files_to_process.append(file_path)

    if not files_to_process:
        logger.info("[#status] ✨ 没有需要处理的文件")
        return

    # 更新进度信息
    total_files = len(files_to_process)
    logger.info(f"[@progress] 检测压缩包完整性 (0/{total_files}) 0%")

    # 定义单个文件处理函数
    def process_single_file(file_path, file_index):
        logger.info(f"[#status] 🔍 正在检测: {file_path}")
        is_valid = check_archive(file_path)
        result = {
            'path': file_path,
            'valid': is_valid,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        # 更新进度
        progress_percentage = int((file_index + 1) / total_files * 100)
        logger.info(f"[@progress] 检测压缩包完整性 ({file_index + 1}/{total_files}) {progress_percentage}%")
        return result

    # 使用线程池处理文件
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 使用enumerate获取索引，方便更新进度
        futures = [executor.submit(process_single_file, file_path, i) for i, file_path in enumerate(files_to_process)]
        
        # 处理结果
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            file_path = result['path']
            is_valid = result['valid']
            
            check_history[file_path] = {
                'time': result['time'],
                'valid': is_valid
            }
            
            if not is_valid:
                new_path = file_path + '.tdel'
                # 如果.tdel文件已存在，先删除它
                if os.path.exists(new_path):
                    try:
                        os.remove(new_path)
                        logger.info(f"[#status] 🗑️ 删除已存在的文件: {new_path}")
                    except Exception as e:
                        logger.error(f"[#error] 删除文件 {new_path} 时发生错误: {str(e)}")
                        continue
                
                try:
                    os.rename(file_path, new_path)
                    logger.warning(f"[#warning] ⚠️ 文件损坏,已重命名为: {new_path}")
                except Exception as e:
                    logger.error(f"[#error] 重命名文件时发生错误: {str(e)}")
            else:
                logger.info(f"[#success] ✅ 文件完好: {file_path}")
            
            # 定期保存检查历史
            save_check_history(check_history)

    # 处理结果的循环结束后，添加删除空文件夹的功能
    removed_count = 0
    logger.info(f"[@progress] 清理空文件夹 (0/100) 0%")
    
    # 获取目录总数以计算进度
    dir_count = sum(len(dirs) for _, dirs, _ in os.walk(directory))
    processed_dirs = 0
    
    for root, dirs, _ in os.walk(directory, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                if not os.listdir(dir_path):  # 检查文件夹是否为空
                    os.rmdir(dir_path)
                    removed_count += 1
                    logger.info(f"[#status] 🗑️ 已删除空文件夹: {dir_path}")
            except Exception as e:
                logger.error(f"[#error] 删除空文件夹失败 {dir_path}: {str(e)}")
            
            # 更新进度
            processed_dirs += 1
            progress = int(processed_dirs / dir_count * 100) if dir_count > 0 else 100
            logger.info(f"[@progress] 清理空文件夹 ({processed_dirs}/{dir_count}) {progress}%")
    
    logger.info(f"[@progress] 清理空文件夹 ({dir_count}/{dir_count}) 100%")
    if removed_count > 0:
        logger.info(f"[#success] ✨ 共删除了 {removed_count} 个空文件夹")

def main():
    parser = argparse.ArgumentParser(description='压缩包完整性检查工具')
    parser.add_argument('paths', nargs='*', help='要处理的路径列表')
    parser.add_argument('-c', '--clipboard', action='store_true', help='从剪贴板读取路径')
    args = parser.parse_args()

    # 初始化TextualLogger
    TextualLoggerManager.set_layout(TEXTUAL_LAYOUT, config_info['log_file'])
    
    # 获取要处理的路径
    directories = []
    
    if args.clipboard:
        directories.extend(get_paths_from_clipboard())
    elif args.paths:
        for path_str in args.paths:
            path = Path(path_str.strip('"').strip("'"))
            if path.exists():
                directories.append(path)
            else:
                logger.warning(f"[#warning] ⚠️ 警告：路径不存在 - {path_str}")
    else:
        default_path = Path(r"D:\3EHV")
        if default_path.exists():
            directories.append(default_path)
            logger.info(f"[#status] 📂 使用默认路径: {default_path}")
        else:
            logger.error("[#error] ❌ 默认路径不存在")
            return

    if not directories:
        logger.error("[#error] ❌ 未提供任何有效的路径")
        return

    skip_checked = True
    # 可以根据CPU核心数调整线程数
    max_workers = os.cpu_count() or 4
    
    # 处理每个目录
    total_dirs = len(directories)
    for idx, directory in enumerate(directories):
        dir_progress = int((idx / total_dirs) * 100) if total_dirs > 0 else 100
        logger.info(f"[@progress] 处理目录 ({idx+1}/{total_dirs}) {dir_progress}%")
        logger.info(f"[#status] 📂 开始处理目录: {directory}")
        process_directory(directory, skip_checked, max_workers=max_workers)
        logger.info(f"[#success] ✅ 目录处理完成: {directory}")
    
    # 最终完成
    logger.info(f"[@progress] 处理目录 ({total_dirs}/{total_dirs}) 100%")
    
if __name__ == "__main__":
    main()
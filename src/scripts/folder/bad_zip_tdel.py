import os
import subprocess
import yaml
from datetime import datetime
import concurrent.futures
from functools import partial
import shutil
import argparse
import pyperclip
from pathlib import Path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nodes.tui.rich_logger import RichProgressHandler

# 获取脚本所在目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(SCRIPT_DIR, 'archive_check_history.yaml')

def load_check_history():
    """加载检测历史记录"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    return {}

def save_check_history(history):
    """保存检测历史记录"""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(history, f, allow_unicode=True, sort_keys=False)

def check_archive(file_path):
    """检测压缩包是否损坏"""
    try:
        result = subprocess.run(['7z', 't', file_path], 
                              capture_output=True, 
                              text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 检测文件 {file_path} 时发生错误: {str(e)}")
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
            print(f"📋 从剪贴板读取到 {len(valid_paths)} 个有效路径")
        else:
            print("⚠️ 剪贴板中没有有效路径")
            
        return valid_paths
        
    except Exception as e:
        print(f"❌ 读取剪贴板时出错: {e}")
        return []

def process_directory(directory, handler, skip_checked=False, max_workers=4):
    """处理目录下的所有压缩包文件"""
    archive_extensions = ('.zip', '.rar', '.7z', '.cbz')
    check_history = load_check_history()
    
    # 删除temp_开头的文件夹
    for root, dirs, _ in os.walk(directory, topdown=True):
        for dir_name in dirs[:]:  # 使用切片创建副本以避免在迭代时修改列表
            if dir_name.startswith('temp_'):
                try:
                    dir_path = os.path.join(root, dir_name)
                    handler.add_status_log(f"🗑️ 正在删除临时文件夹: {dir_path}")
                    shutil.rmtree(dir_path)
                except Exception as e:
                    handler.add_error_log(f"删除文件夹 {dir_path} 时发生错误: {str(e)}")

    # 收集需要处理的文件
    files_to_process = []
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.lower().endswith(archive_extensions):
                file_path = os.path.join(root, filename)
                if file_path.endswith('.tdel'):
                    continue
                if skip_checked and file_path in check_history and check_history[file_path]['valid']:
                    handler.add_status_log(f"⏭️ 跳过已检查且完好的文件: {file_path}")
                    continue
                files_to_process.append(file_path)

    if not files_to_process:
        handler.add_status_log("✨ 没有需要处理的文件")
        return

    # 创建进度任务
    task_id = handler.create_progress_task(len(files_to_process), "检测压缩包完整性")

    # 定义单个文件处理函数
    def process_single_file(file_path):
        handler.add_status_log(f"🔍 正在检测: {file_path}")
        is_valid = check_archive(file_path)
        result = {
            'path': file_path,
            'valid': is_valid,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        return result

    # 使用线程池处理文件
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for file_path in files_to_process:
            future = executor.submit(process_single_file, file_path)
            futures.append(future)
        
        # 处理结果
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            handler.progress.update(task_id, completed=completed)
            
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
                        handler.add_status_log(f"🗑️ 删除已存在的文件: {new_path}")
                    except Exception as e:
                        handler.add_error_log(f"删除文件 {new_path} 时发生错误: {str(e)}")
                        continue
                
                try:
                    os.rename(file_path, new_path)
                    handler.add_warning_log(f"⚠️ 文件损坏,已重命名为: {new_path}")
                except Exception as e:
                    handler.add_error_log(f"重命名文件时发生错误: {str(e)}")
            else:
                handler.add_success_log(f"✅ 文件完好: {file_path}")
            
            # 定期保存检查历史
            save_check_history(check_history)

    # 处理结果的循环结束后，添加删除空文件夹的功能
    removed_count = 0
    for root, dirs, _ in os.walk(directory, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                if not os.listdir(dir_path):  # 检查文件夹是否为空
                    os.rmdir(dir_path)
                    removed_count += 1
                    handler.add_status_log(f"🗑️ 已删除空文件夹: {dir_path}")
            except Exception as e:
                handler.add_error_log(f"删除空文件夹失败 {dir_path}: {str(e)}")
    
    if removed_count > 0:
        handler.add_success_log(f"✨ 共删除了 {removed_count} 个空文件夹")

def main():
    parser = argparse.ArgumentParser(description='压缩包完整性检查工具')
    parser.add_argument('paths', nargs='*', help='要处理的路径列表')
    parser.add_argument('-c', '--clipboard', action='store_true', help='从剪贴板读取路径')
    args = parser.parse_args()

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
                print(f"⚠️ 警告：路径不存在 - {path_str}")
    else:
        default_path = Path(r"D:\3EHV")
        if default_path.exists():
            directories.append(default_path)
            print(f"📂 使用默认路径: {default_path}")
        else:
            print("❌ 默认路径不存在")
            return

    if not directories:
        print("❌ 未提供任何有效的路径")
        return

    # 创建rich handler
    with RichProgressHandler() as handler:
        skip_checked = True
        # 可以根据CPU核心数调整线程数
        max_workers = os.cpu_count() or 4
        
        # 处理每个目录
        for directory in directories:
            handler.add_status_log(f"📂 开始处理目录: {directory}")
            process_directory(directory, handler, skip_checked, max_workers=max_workers)
            handler.add_success_log(f"✅ 目录处理完成: {directory}")
    
if __name__ == "__main__":
    main()
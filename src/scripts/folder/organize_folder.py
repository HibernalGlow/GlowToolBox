import os
import shutil
import argparse
import pyperclip
from pathlib import Path
import sys
import fnmatch
import time
import psutil
from datetime import datetime, timedelta
from nodes.tui.textual_preset import create_config_app
try:
    import keyboard
except ImportError:
    print("请先安装keyboard库: pip install keyboard")
    sys.exit(1)

# 支持的视频格式
VIDEO_FORMATS = {'.mp4','.nov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.mov', '.m4v', '.mpg', '.mpeg', '.3gp', '.rmvb'}

# 支持的压缩包格式
ARCHIVE_FORMATS = {'.zip', '.rar', '.7z', '.cbz', '.cbr'}

# 在文件顶部添加删除规则配置（建议放在VIDEO_FORMATS和ARCHIVE_FORMATS附近）
DELETE_KEYWORDS = [
    ('*.bak', 'file'),     # 仅匹配文件
    ('temp_*', 'dir'),     # 仅匹配文件夹
    ('*.trash', 'both')    # 同时匹配文件和文件夹
]

def is_video_file(filename):
    """判断文件是否为视频文件"""
    return any(filename.lower().endswith(ext) for ext in VIDEO_FORMATS)

def is_archive_file(filename):
    """判断文件是否为压缩包文件"""
    return any(filename.lower().endswith(ext) for ext in ARCHIVE_FORMATS)

def get_safe_path(target_path: Path, base_path: Path) -> Path:
    """获取安全的目标路径，如果目标路径已存在则添加数字后缀"""
    if not target_path.exists():
        return target_path
    
    counter = 1
    while True:
        new_name = f"{target_path.stem}_{counter}{target_path.suffix}"
        new_path = base_path / new_name
        if not new_path.exists():
            return new_path
        counter += 1

def remove_empty_folders(path, exclude_keywords=[]):
    """
    删除指定路径下的所有空文件夹

    参数:
    path (str): 目标路径
    exclude_keywords (list): 排除关键词列表
    """
    for root, dirs, files in os.walk(path, topdown=False):
        # 检查当前路径是否包含排除关键词
        if any(keyword in root for keyword in exclude_keywords):
            continue

        for dir in dirs:
            folder_path = os.path.join(root, dir)
            try:
                if not os.listdir(folder_path):
                    os.rmdir(folder_path)
                    print(f"已删除空文件夹: {folder_path}")
            except FileNotFoundError:
                print(f"路径不存在: {folder_path}")
            except Exception as e:
                print(f"删除文件夹失败: {folder_path} - {e}")

def flatten_single_subfolder(path, exclude_keywords=[]):
    """
    如果一个文件夹下只有一个文件夹，就将该文件夹的子文件夹释放掉，将其中的文件和文件夹移动到母文件夹

    参数:
    path (str): 目标路径
    exclude_keywords (list): 排除关键词列表
    """
    for root, dirs, files in os.walk(path):
        # 检查当前路径是否包含排除关键词
        if any(keyword in root for keyword in exclude_keywords):
            continue

        if len(dirs) == 1 and not files:
            subfolder_path = os.path.join(root, dirs[0])
            try:
                while True:  # 处理嵌套的单文件夹
                    # 检查子文件夹中是否只有一个文件夹且没有文件
                    sub_items = os.listdir(subfolder_path)
                    sub_dirs = [item for item in sub_items if os.path.isdir(os.path.join(subfolder_path, item))]
                    sub_files = [item for item in sub_items if os.path.isfile(os.path.join(subfolder_path, item))]
                    
                    if len(sub_dirs) == 1 and not sub_files:
                        # 更新子文件夹路径到更深一层
                        subfolder_path = os.path.join(subfolder_path, sub_dirs[0])
                        continue
                    break  # 如果不是单文件夹，退出循环
                
                # 移动最深层子文件夹中的所有内容到母文件夹
                for item in os.listdir(subfolder_path):
                    src_item_path = os.path.join(subfolder_path, item)
                    dst_item_path = os.path.join(root, item)
                    if os.path.exists(dst_item_path):
                        base_name, ext = os.path.splitext(item)
                        counter = 1
                        while os.path.exists(dst_item_path):
                            dst_item_path = os.path.join(root, f"{base_name}_{counter}{ext}")
                            counter += 1
                    try:
                        shutil.move(src_item_path, dst_item_path)
                        print(f"已移动: {src_item_path} -> {dst_item_path}")
                    except PermissionError as e:
                        print(f"权限不足: {src_item_path} - {e}")
                    except Exception as e:
                        print(f"移动失败: {src_item_path} - {e}")
                
                # 删除空的子文件夹
                shutil.rmtree(subfolder_path)
                print(f"已删除文件夹: {subfolder_path}")
            except FileNotFoundError:
                print(f"路径不存在: {subfolder_path}")
            except Exception as e:
                print(f"处理文件夹失败: {subfolder_path} - {e}")

def release_single_media_folder(path, exclude_keywords=[]):
    """
    如果文件夹中只有一个视频文件或压缩包文件，将其释放到上层目录

    参数:
    path (str): 目标路径
    exclude_keywords (list): 排除关键词列表
    """
    print(f"\n开始处理单媒体文件夹: {path}")
    processed_count = 0
    
    for root, _, _ in os.walk(path, topdown=False):
        print(f"\n检查文件夹: {root}")
        
        # 检查当前路径是否包含排除关键词
        if any(keyword in root for keyword in exclude_keywords):
            print(f"跳过含有排除关键词的文件夹: {root}")
            continue

        try:
            # 获取文件夹中的所有项目
            items = os.listdir(root)
            
            # 分别统计文件和文件夹
            files = []
            dirs = []
            for item in items:
                item_path = os.path.join(root, item)
                if os.path.isfile(item_path):
                    files.append(item)
                elif os.path.isdir(item_path):
                    dirs.append(item)
            
            print(f"- 包含 {len(dirs)} 个子文件夹")
            print(f"- 包含 {len(files)} 个文件:")
            for f in files:
                print(f"  - {f}")

            # 过滤出视频文件和压缩包文件
            media_files = [f for f in files if is_video_file(f) or is_archive_file(f)]
            print(f"- 发现 {len(media_files)} 个媒体文件:")
            for f in media_files:
                print(f"  - {f} ({'视频' if is_video_file(f) else '压缩包'})")
            
            # 如果文件夹中只有一个媒体文件且没有其他文件和文件夹
            if len(media_files) == 1 and len(files) == 1 and len(dirs) == 0:
                print(f"\n找到符合条件的文件夹: {root}")
                print(f"- 单个媒体文件: {media_files[0]}")
                
                file_path = os.path.join(root, media_files[0])
                parent_dir = os.path.dirname(root)
                target_path = os.path.join(parent_dir, media_files[0])
                
                try:
                    # 如果目标路径已存在，添加数字后缀
                    if os.path.exists(target_path):
                        base_name, ext = os.path.splitext(media_files[0])
                        counter = 1
                        while os.path.exists(target_path):
                            target_path = os.path.join(parent_dir, f"{base_name}_{counter}{ext}")
                            counter += 1
                            print(f"- 目标文件已存在，尝试新名称: {os.path.basename(target_path)}")
                    
                    # 移动文件到上层目录
                    print(f"- 开始移动文件:")
                    print(f"  从: {file_path}")
                    print(f"  到: {target_path}")
                    shutil.move(file_path, target_path)
                    print("- 文件移动成功")
                    
                    # 删除空文件夹
                    print(f"- 删除空文件夹: {root}")
                    os.rmdir(root)
                    print("- 文件夹删除成功")
                    
                    processed_count += 1
                except Exception as e:
                    print(f"❌ 处理文件夹时出错 {root}:")
                    print(f"  错误信息: {str(e)}")
            else:
                if len(media_files) > 0:
                    print(f"不符合处理条件:")
                    print(f"- 媒体文件数: {len(media_files)} (需要为1)")
                    print(f"- 总文件数: {len(files)} (需要为1)")
                    print(f"- 子文件夹数: {len(dirs)} (需要为0)")
        except Exception as e:
            print(f"❌ 处理文件夹时出错 {root}:")
            print(f"  错误信息: {str(e)}")
    
    print(f"\n单媒体文件夹处理完成")
    print(f"- 共处理了 {processed_count} 个文件夹")
    if processed_count == 0:
        print("- 没有找到符合条件的文件夹")

def get_paths_from_clipboard():
    """从剪贴板读取多行路径"""
    try:
        clipboard_content = pyperclip.paste()
        if not clipboard_content:
            return []
        
        paths = []
        for line in clipboard_content.splitlines():
            if line := line.strip().strip('"').strip("'"):
                path = Path(line)
                if path.exists():
                    paths.append(path)
                else:
                    print(f"警告：路径不存在 - {line}")
        
        print(f"从剪贴板读取到 {len(paths)} 个有效路径")
        return paths
        
    except Exception as e:
        print(f"读取剪贴板失败: {e}")
        return []

def handle_name_conflict(target_path, is_dir=False, mode='auto'):
    """
    处理文件名冲突
    
    参数:
    target_path (Path): 目标路径
    is_dir (bool): 是否是文件夹
    mode (str): 处理模式
        - 'auto': 文件跳过，文件夹合并
        - 'skip': 跳过
        - 'overwrite': 覆盖（文件夹会合并内容）
        - 'rename': 重命名
    
    返回:
    tuple: (Path, bool) - (最终路径, 是否继续处理)
    """
    if not target_path.exists():
        return target_path, True
        
    if mode == 'auto':
        mode = 'overwrite' if is_dir else 'skip'
        
    if mode == 'skip':
        print(f"跳过已存在的{'文件夹' if is_dir else '文件'}: {target_path}")
        return target_path, False
    elif mode == 'overwrite':
        if is_dir:
            print(f"将合并到已存在的文件夹: {target_path}")
            return target_path, True
        else:
            print(f"将覆盖已存在的文件: {target_path}")
            target_path.unlink()
            return target_path, True
    else:  # rename
        counter = 1
        while True:
            new_name = f"{target_path.stem}_{counter}{target_path.suffix}"
            new_path = target_path.parent / new_name
            if not new_path.exists():
                print(f"重命名为: {new_path}")
                return new_path, True
            counter += 1

def is_file_in_use(file_path):
    """
    检查文件是否正在被使用
    
    参数:
    file_path (Path/str): 文件路径
    
    返回:
    bool: 如果文件正在被使用返回True，否则返回False
    """
    try:
        path = str(file_path)
        for proc in psutil.process_iter(['pid', 'open_files']):
            try:
                files = proc.info['open_files']
                if files:
                    for file in files:
                        if file.path == path:
                            return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    except Exception as e:
        print(f"检查文件占用状态时出错: {e}")
        return True  # 如果无法确定，则假设文件正在使用中

def handle_file_operation(file_path, operation_func, *args, **kwargs):
    """
    安全地处理文件操作，检查文件是否被占用
    
    参数:
    file_path (Path): 要操作的文件路径
    operation_func: 要执行的操作函数
    *args, **kwargs: 传递给操作函数的参数
    
    返回:
    bool: 操作是否成功
    """
    max_retries = 3
    retry_delay = 2  # 秒
    
    for attempt in range(max_retries):
        if is_file_in_use(file_path):
            print(f"文件正在被使用中: {file_path}")
            if attempt < max_retries - 1:
                print(f"等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
                continue
            return False
        
        try:
            operation_func(*args, **kwargs)
            return True
        except PermissionError:
            if attempt < max_retries - 1:
                print(f"权限不足，等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
            else:
                print(f"无法访问文件: {file_path}")
                return False
        except Exception as e:
            print(f"操作失败: {e}")
            return False
    
    return False

def dissolve_folder(path, file_conflict='auto', dir_conflict='auto'):
    """
    将指定文件夹中的所有内容移动到其父文件夹中，然后删除该文件夹
    
    参数:
    path (Path/str): 要解散的文件夹路径
    file_conflict (str): 文件冲突处理方式 ('auto'/'skip'/'overwrite'/'rename')
    dir_conflict (str): 文件夹冲突处理方式 ('auto'/'skip'/'overwrite'/'rename')
    """
    try:
        path = Path(path).resolve()  # 转换为绝对路径
        if not path.exists() or not path.is_dir():
            print(f"错误：{path} 不是一个有效的文件夹")
            return
            
        parent_dir = path.parent
        print(f"\n开始解散文件夹: {path}")
        
        # 获取所有项目并排序（文件优先）
        items = list(path.iterdir())
        items.sort(key=lambda x: (x.is_dir(), x.name))  # 文件在前，文件夹在后
        
        def move_item(src, dst):
            return handle_file_operation(src, shutil.move, str(src.absolute()), str(dst.absolute()))
        
        for item in items:
            target_path = parent_dir / item.name
            is_dir = item.is_dir()
            
            # 处理名称冲突
            conflict_mode = dir_conflict if is_dir else file_conflict
            target_path, should_proceed = handle_name_conflict(
                target_path, 
                is_dir=is_dir,
                mode=conflict_mode
            )
            
            if not should_proceed:
                continue
                
            try:
                print(f"移动: {item.name} -> {target_path}")
                if is_dir and target_path.exists():
                    # 如果是文件夹且目标存在，则移动内容而不是整个文件夹
                    for sub_item in item.iterdir():
                        sub_target = target_path / sub_item.name
                        if sub_target.exists():
                            # 对子项目递归应用相同的冲突处理策略
                            sub_is_dir = sub_item.is_dir()
                            sub_conflict_mode = dir_conflict if sub_is_dir else file_conflict
                            sub_target, sub_should_proceed = handle_name_conflict(
                                sub_target,
                                is_dir=sub_is_dir,
                                mode=sub_conflict_mode
                            )
                            if not sub_should_proceed:
                                continue
                        if not move_item(sub_item, sub_target):
                            print(f"移动失败: {sub_item}")
                else:
                    # 如果是文件或目标文件夹不存在，直接移动
                    if not move_item(item, target_path):
                        print(f"移动失败: {item}")
            except Exception as e:
                print(f"移动 {item.name} 失败: {e}")
                continue
        
        try:
            # 检查文件夹是否为空
            remaining_items = list(path.iterdir())
            if remaining_items:
                print(f"警告：文件夹 {path} 仍包含以下项目，无法删除:")
                for item in remaining_items:
                    print(f"  - {item.name}")
            else:
                path.rmdir()
                print(f"已成功解散并删除文件夹: {path}")
        except Exception as e:
            print(f"删除文件夹失败: {e}")
            
    except Exception as e:
        print(f"解散文件夹时出错: {e}")

def remove_backup_and_temp(path, exclude_keywords=[]):
    """
    删除指定路径下的备份文件(.bak)和临时文件夹(temp_开头)
    修改为根据DELETE_KEYWORDS配置进行删除
    """
    path = Path(path)
    removed_count = 0
    
    print(f"\n开始清理配置规则文件: {path}")
    
    try:
        for item in path.rglob("*"):
            # 检查路径是否包含排除关键词
            if any(keyword in str(item) for keyword in exclude_keywords):
                continue
                
            try:
                # 使用配置的关键词进行匹配
                for pattern, target_type in DELETE_KEYWORDS:
                    if target_type in ['file', 'both'] and item.is_file() and fnmatch.fnmatch(item.name, pattern):
                        print(f"删除匹配 {pattern} 的文件: {item}")
                        item.unlink()
                        removed_count += 1
                        break
                    if target_type in ['dir', 'both'] and item.is_dir() and fnmatch.fnmatch(item.name, pattern):
                        print(f"删除匹配 {pattern} 的文件夹: {item}")
                        shutil.rmtree(item)
                        removed_count += 1
                        break
            except Exception as e:
                print(f"删除失败 {item}: {e}")
                
    except Exception as e:
        print(f"清理过程出错: {e}")
    
    print(f"清理完成，共删除 {removed_count} 个项目")

def run_operations(paths, args, exclude_keywords):
    """执行所有操作的函数"""
    if not paths:
        print("没有可处理的路径")
        return False
        
    print(f"\n处理目录: {paths}")
    
    # 如果指定了dissolve模式，直接解散文件夹
    if args.dissolve:
        for path in paths:
            dissolve_folder(path, 
                          file_conflict=args.file_conflict,
                          dir_conflict=args.dir_conflict)
        return True
    
    for path in paths:
        # 1. 释放单独媒体文件夹
        if args.release_media:
            print("\n>>> 释放单独媒体文件夹...")
            release_single_media_folder(path, exclude_keywords)
        
        # 2. 解散嵌套的单独文件夹
        if args.flatten:
            print("\n>>> 解散嵌套的单独文件夹...")
            flatten_single_subfolder(path, exclude_keywords)
        
        # 3. 删除空文件夹
        if args.remove_empty:
            print("\n>>> 删除空文件夹...")
            remove_empty_folders(path, exclude_keywords)
        
        # 4. 清理备份文件和临时文件夹
        if args.clean_backup:
            print("\n>>> 清理备份文件和临时文件夹...")
            remove_backup_and_temp(path, exclude_keywords)
    
    return True

def handle_timer_mode(args, initial_paths, exclude_keywords):
    """处理定时模式"""
    print(f"\n进入定时模式，每 {args.timer} 分钟执行一次")
    if args.start_time and args.end_time:
        print(f"执行时间范围：{args.start_time} - {args.end_time}")
    
    # 保存初始路径
    last_valid_paths = initial_paths
    
    try:
        while True:
            current_time = datetime.now().time()
            
            # 检查是否在指定的时间范围内
            if args.start_time and args.end_time:
                start = datetime.strptime(args.start_time, "%H:%M").time()
                end = datetime.strptime(args.end_time, "%H:%M").time()
                
                if not (start <= current_time <= end):
                    print(f"\n当前时间 {current_time.strftime('%H:%M')} 不在执行时间范围内")
                    next_run = datetime.combine(datetime.now().date(), start)
                    if current_time > end:
                        next_run += timedelta(days=1)
                    wait_seconds = (next_run - datetime.now()).total_seconds()
                    print(f"等待到下一个执行时间：{next_run.strftime('%Y-%m-%d %H:%M')}")
                    time.sleep(wait_seconds)
                    continue
            
            print(f"\n\n开始执行任务 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 如果使用剪贴板，尝试获取新路径
            current_paths = last_valid_paths
            if args.clipboard:
                if new_paths := get_paths_from_clipboard():
                    current_paths = new_paths
                    last_valid_paths = new_paths  # 更新最后的有效路径
                else:
                    print(f"剪贴板中没有有效路径，使用上次的路径: {[str(p) for p in current_paths]}")
            
            # 执行操作
            if run_operations(current_paths, args, exclude_keywords):
                next_run = datetime.now() + timedelta(minutes=args.timer)
                print(f"\n任务完成，下次执行时间：{next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print("\n任务执行失败")
            
            time.sleep(args.timer * 60)
            
    except KeyboardInterrupt:
        print("\n检测到Ctrl+C，程序退出")

def main():
    """
    主函数：处理命令行参数并执行相应操作
    """
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description='文件夹整理工具')
        parser.add_argument('paths', nargs='*', help='要处理的路径列表')
        parser.add_argument('--clipboard', '-c', action='store_true', help='从剪贴板读取路径')
        parser.add_argument('--release-media', '-m', action='store_true', help='释放单独媒体文件夹')
        parser.add_argument('--dissolve', '-d', action='store_true', help='直接解散指定文件夹')
        parser.add_argument('--flatten', '-f', action='store_true', help='解散嵌套的单独文件夹')
        parser.add_argument('--remove-empty', '-r', action='store_true', help='删除空文件夹')
        parser.add_argument('--file-conflict', choices=['auto', 'skip', 'overwrite', 'rename'], 
                          default='auto', help='文件重名处理方式 (默认: auto - 跳过)')
        parser.add_argument('--dir-conflict', choices=['auto', 'skip', 'overwrite', 'rename'], 
                          default='auto', help='文件夹重名处理方式 (默认: auto - 覆盖)')
        parser.add_argument('--clean-backup', '-b', action='store_true', 
                           help='删除备份文件和临时文件夹')
        parser.add_argument('--exclude', help='排除关键词列表，用逗号分隔多个关键词')
        parser.add_argument('--inf', action='store_true', help='无限循环模式，按F2键重新执行操作')
        parser.add_argument('--timer', '-t', type=int, help='定时执行间隔（分钟）')
        parser.add_argument('--start-time', type=str, help='开始时间（格式：HH:MM）')
        parser.add_argument('--end-time', type=str, help='结束时间（格式：HH:MM）')
        args = parser.parse_args()
        
        # 获取要处理的路径
        paths = []
        if args.clipboard:
            paths = get_paths_from_clipboard()
        elif args.paths:  # 处理直接传入的路径
            for path_str in args.paths:
                path = Path(path_str.strip('"').strip("'"))
                if path.exists():
                    paths.append(path)
                else:
                    print(f"警告：路径不存在 - {path_str}")
        
        if not paths:
            print("请输入要处理的文件夹路径，每行一个，输入空行结束:")
            while True:
                if line := input().strip():
                    path = Path(line.strip('"').strip("'"))
                    if path.exists():
                        paths.append(path)
                    else:
                        print(f"警告：路径不存在 - {line}")
                else:
                    break
        
        if not paths:
            print("未提供任何有效的路径")
            return

        # 如果没有指定任何操作，提示用户
        if not any([args.release_media, args.flatten, args.remove_empty, 
                    args.dissolve, args.clean_backup]):
            print("错误：未指定任何操作。请使用 -h 参数查看帮助信息。")
            return
        
        # 处理每个路径
        exclude_keywords = ["单行"]  # 排除关键词
        if args.exclude:
            exclude_keywords.extend(args.exclude.split(','))

        # 处理定时模式
        if args.timer:
            handle_timer_mode(args, paths, exclude_keywords)
        else:
            run_operations(paths, args, exclude_keywords)
        return

    # 否则尝试使用TUI模式
    try:
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        
        # 定义复选框选项
        checkbox_options = [
            ("从剪贴板读取路径", "clipboard", "--clipboard", True),  # 默认开启
            ("释放单独媒体文件夹", "release_media", "--release-media"),
            ("解散嵌套的单独文件夹", "flatten", "--flatten"),
            ("删除空文件夹", "remove_empty", "--remove-empty"),
            ("删除备份和临时文件", "clean_backup", "--clean-backup"),
            ("直接解散文件夹", "dissolve", "--dissolve"),
            ("定时执行模式", "timer", "--timer"),  # 添加定时模式选项
        ]

        # 定义输入框选项
        input_options = [
            ("排除关键词", "exclude", "--exclude", "单行", "用逗号分隔多个关键词"),
            ("执行间隔(分钟)", "timer_interval", "", "30", "定时执行的间隔时间(分钟)"),
            ("开始时间", "start_time", "--start-time", "09:00", "执行时间范围的开始时间(HH:MM)"),
            ("结束时间", "end_time", "--end-time", "18:00", "执行时间范围的结束时间(HH:MM)"),
        ]

        # 预设配置
        preset_configs = {
            "全部操作(除直接解散)": {
                "description": "执行所有整理和清理操作",
                "checkbox_options": ["clipboard", "release_media", "flatten", "remove_empty", "clean_backup"],
                "input_values": {
                    "exclude": "单行",
                }
            },
            "释放媒体": {
                "description": "释放单独的媒体文件夹",
                "checkbox_options": ["clipboard", "release_media"],
                "input_values": {
                    "exclude": "单行",
                }
            },
            "解散嵌套": {
                "description": "解散嵌套的单独文件夹",
                "checkbox_options": ["clipboard", "flatten"],
                "input_values": {
                    "exclude": "单行",
                }
            },
            "删除空文件夹": {
                "description": "删除所有空文件夹",
                "checkbox_options": ["clipboard", "remove_empty"],
                "input_values": {
                    "exclude": "单行",
                }
            },
            "清理备份": {
                "description": "删除备份文件和临时文件夹",
                "checkbox_options": ["clipboard", "clean_backup"],
                "input_values": {
                    "exclude": "单行",
                }
            },
            "直接解散": {
                "description": "直接解散指定文件夹",
                "checkbox_options": ["clipboard", "dissolve"],
                "input_values": {
                    "exclude": "单行",
                }
            },
            "定时整理": {
                "description": "定时执行文件夹整理",
                "checkbox_options": ["clipboard", "release_media", "flatten", "remove_empty", "clean_backup", "timer"],
                "input_values": {
                    "exclude": "单行",
                    "timer_interval": "30",
                    "start_time": "09:00", 
                    "end_time": "18:00"
                }
            },
            "夜间整理": {
                "description": "在夜间执行文件夹整理",
                "checkbox_options": ["clipboard", "release_media", "flatten", "remove_empty", "clean_backup", "timer"],
                "input_values": {
                    "exclude": "单行",
                    "timer_interval": "60",
                    "start_time": "23:00",
                    "end_time": "06:00"
                }
            }
        }
        
        # 创建并运行配置界面
        app = create_config_app(
            program=__file__,
            checkbox_options=checkbox_options,
            input_options=input_options,
            title="文件夹整理工具配置",
            preset_configs=preset_configs
        )
        app.run()
        return
        
    except ImportError:
        print("未找到TUI模块，将使用命令行模式")
        print("提示：可以安装 textual 包来启用TUI界面\n")
        
        parser = argparse.ArgumentParser(description='文件夹整理工具')
        parser.add_argument('paths', nargs='*', help='要处理的路径列表')
        parser.add_argument('--clipboard', '-c', action='store_true', help='从剪贴板读取路径')
        parser.add_argument('--release-media', '-m', action='store_true', help='释放单独媒体文件夹')
        parser.add_argument('--dissolve', '-d', action='store_true', help='直接解散指定文件夹')
        parser.add_argument('--flatten', '-f', action='store_true', help='解散嵌套的单独文件夹')
        parser.add_argument('--remove-empty', '-r', action='store_true', help='删除空文件夹')
        parser.add_argument('--file-conflict', choices=['auto', 'skip', 'overwrite', 'rename'], 
                          default='auto', help='文件重名处理方式 (默认: auto - 跳过)')
        parser.add_argument('--dir-conflict', choices=['auto', 'skip', 'overwrite', 'rename'], 
                          default='auto', help='文件夹重名处理方式 (默认: auto - 覆盖)')
        parser.add_argument('--clean-backup', '-b', action='store_true', 
                           help='删除备份文件和临时文件夹')
        parser.add_argument('--exclude', help='排除关键词列表，用逗号分隔多个关键词')
        parser.add_argument('--inf', action='store_true', help='无限循环模式，按F2键重新执行操作')
        args = parser.parse_args()
        
        # 获取要处理的路径
        paths = []
        if args.clipboard:
            paths = get_paths_from_clipboard()
        elif args.paths:  # 处理直接传入的路径
            for path_str in args.paths:
                path = Path(path_str.strip('"').strip("'"))
                if path.exists():
                    paths.append(path)
                else:
                    print(f"警告：路径不存在 - {path_str}")
        
        if not paths:
            print("请输入要处理的文件夹路径，每行一个，输入空行结束:")
            while True:
                if line := input().strip():
                    path = Path(line.strip('"').strip("'"))
                    if path.exists():
                        paths.append(path)
                    else:
                        print(f"警告：路径不存在 - {line}")
                else:
                    break
        
        if not paths:
            print("未提供任何有效的路径")
            return

        # 如果没有指定任何操作，提示用户
        if not any([args.release_media, args.flatten, args.remove_empty, 
                    args.dissolve, args.clean_backup]):
            print("错误：未指定任何操作。请使用 -h 参数查看帮助信息。")
            return
        
        # 处理每个路径
        exclude_keywords = ["单行"]  # 排除关键词
        if args.exclude:
            exclude_keywords.extend(args.exclude.split(','))
        
        # 处理定时模式
        if args.timer:
            handle_timer_mode(args, paths, exclude_keywords)
        else:
            run_operations(paths, args, exclude_keywords)

if __name__ == "__main__":
    main()

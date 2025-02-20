import os
import shutil
import logging
import sys
import subprocess
import tempfile
from tqdm import tqdm
import argparse
from datetime import datetime
import re
import win32clipboard
import time

# 配置日志
log_file = r"D:/1VSCODE/1ehv/logs/restore_log.log"
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 文件日志处理器
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# 控制台日志处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(console_handler)

def get_clipboard_paths():
    """获取剪贴板中的路径"""
    try:
        win32clipboard.OpenClipboard()
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
            clipboard_data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            # 分割并清理路径
            paths = [path.strip().strip('"') for path in clipboard_data.splitlines() if path.strip()]
            return paths
    except Exception as e:
        logger.error(f"读取剪贴板出错: {e}")
        if 'win32clipboard' in locals():
            win32clipboard.CloseClipboard()
    return []

def clean_filename(filename):
    """清理文件名中的时间戳和下划线"""
    # 匹配以下格式：
    # 1. _YYYYMMDD_HHMMSS 格式
    # 2. _数字序列 (如 _1737475697096)
    patterns = [
        # r'_\d{8}_\d{6}',  # _YYYYMMDD_HHMMSS
        r'_\d{13}',       # _1737475697096
        r'_\d{10}',       # Unix timestamp
    ]
    
    cleaned_name = filename
    for pattern in patterns:
        cleaned_name = re.sub(pattern, '', cleaned_name)
    
    return cleaned_name

def create_temp_directory():
    """创建临时目录"""
    temp_dir = tempfile.mkdtemp()
    logger.debug(f"创建临时目录: {temp_dir}")
    return temp_dir

def run_7z_command(command, zip_path, operation="", additional_args=None):
    """执行7z命令"""
    try:
        cmd = ['7z', command, zip_path]
        if additional_args:
            cmd.extend(additional_args)
            
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.debug(f"成功执行7z {operation}: {zip_path}")
            return True, result.stdout
        else:
            logger.error(f"7z {operation}失败: {zip_path}\n错误: {result.stderr}")
            return False, result.stderr
            
    except Exception as e:
        logger.error(f"执行7z命令出错: {e}")
        return False, str(e)

def merge_trash_folders(trash_dir, temp_dir):
    """合并trash文件夹中的所有类型的文件"""
    try:
        # 定义所有可能的子目录类型
        subdirs = [
            "hash_duplicates",    # 哈希重复
            "normal_duplicates",  # 普通重复
            "small_images",       # 小图
            "white_images",       # 白图
            "other"              # 其他原因删除的文件
        ]
        
        # 检查目录是否存在
        found_any = False
        for subdir in subdirs:
            if os.path.exists(os.path.join(trash_dir, subdir)):
                found_any = True
                break
                
        if not found_any:
            logger.error(f"在 {trash_dir} 中未找到任何有效的子文件夹")
            return False
            
        # 获取原始压缩包名（不含.trash或.new.trash后缀）
        original_name = os.path.basename(trash_dir)
        if original_name.endswith('.new.trash'):
            original_name = original_name[:-10]
        elif original_name.endswith('.trash'):
            original_name = original_name[:-6]
            
        # 复制文件到临时目录，同时清理文件名
        for subdir in subdirs:
            source_dir = os.path.join(trash_dir, subdir)
            if not os.path.exists(source_dir):
                continue
                
            logger.debug(f"处理 {subdir} 文件夹...")
            # 遍历分类目录下的内容
            for item in os.listdir(source_dir):
                item_path = os.path.join(source_dir, item)
                if not os.path.isdir(item_path):
                    continue
                    
                # 检查是否是时间戳文件夹
                content_dir = item_path
                content_items = os.listdir(content_dir)
                if len(content_items) == 1 and os.path.isdir(os.path.join(content_dir, content_items[0])):
                    first_dir = content_items[0]
                    clean_first_dir = clean_filename(first_dir)
                    # 如果文件夹名与压缩包名相同，使用其内容
                    if clean_first_dir == original_name:
                        content_dir = os.path.join(content_dir, first_dir)
                
                # 复制实际内容
                for root, _, files in os.walk(content_dir):
                    for file in files:
                        src_path = os.path.join(root, file)
                        # 计算相对于content_dir的路径
                        rel_path = os.path.relpath(root, content_dir)
                        # 清理文件名中的时间戳
                        clean_file = clean_filename(file)
                        
                        if rel_path == '.':
                            # 文件在根目录
                            dst_path = os.path.join(temp_dir, clean_file)
                        else:
                            # 文件在子目录中
                            dst_path = os.path.join(temp_dir, rel_path, clean_file)
                        
                        # 创建目标目录
                        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                        # 复制文件
                        shutil.copy2(src_path, dst_path)
                        logger.debug(f"从 {subdir} 复制并清理文件: {src_path} -> {dst_path}")
                        
        return True
    except Exception as e:
        logger.error(f"合并trash文件夹时出错: {e}")
        return False

def get_original_zip_path(trash_dir):
    """根据trash文件夹名称获取原始压缩包路径"""
    try:
        # 移除.trash和.new.trash后缀
        original_name = os.path.basename(trash_dir)
        if original_name.endswith('.new.trash'):
            original_name = original_name[:-10]  # 移除.new.trash
        elif original_name.endswith('.trash'):
            original_name = original_name[:-6]   # 移除.trash
            
        original_path = os.path.join(os.path.dirname(trash_dir), f"{original_name}.zip")
        
        if os.path.exists(original_path):
            return original_path
        else:
            logger.error(f"未找到原始压缩包: {original_path}")
            return None
    except Exception as e:
        logger.error(f"获取原始压缩包路径时出错: {e}")
        return None

def get_zip_structure(zip_path):
    """获取压缩包的文件夹结构"""
    try:
        # 列出压缩包内容
        success, output = run_7z_command('l', zip_path, "列出压缩包内容")
        if not success:
            return None
            
        # 分析输出，获取文件列表
        files = []
        for line in output.splitlines():
            if '...' in line:  # 7z的输出格式中，文件路径前通常有...
                path = line.split('...', 1)[1].strip()
                if path:  # 忽略空路径
                    files.append(path)
                    
        # 如果没有文件，返回None
        if not files:
            return None
            
        # 检查是否所有文件都在同一个根目录下
        roots = set()
        for file in files:
            parts = file.split('/', 1)  # 使用/分割，因为7z输出使用/作为分隔符
            if len(parts) > 1:
                roots.add(parts[0])
            else:
                roots.add('')  # 文件在根目录
                
        # 如果只有一个根目录，且不是空，说明压缩包内容都在一个文件夹内
        if len(roots) == 1 and '' not in roots:
            return list(roots)[0]
        return ''
            
    except Exception as e:
        logger.error(f"获取压缩包结构时出错: {e}")
        return None

def get_content_structure(content_dir):
    """获取目录的文件夹结构，跳过时间戳文件夹"""
    try:
        # 首先跳过时间戳文件夹
        current_dir = content_dir
        while True:
            items = os.listdir(current_dir)
            if len(items) != 1 or not os.path.isdir(os.path.join(current_dir, items[0])):
                break
            current_dir = os.path.join(current_dir, items[0])
        
        # 现在current_dir指向实际的内容目录
        items = os.listdir(current_dir)
        if len(items) == 1 and os.path.isdir(os.path.join(current_dir, items[0])):
            return items[0]  # 返回实际的第一层文件夹名
        return ''
    except Exception as e:
        logger.error(f"获取目录结构时出错: {e}")
        return None

def merge_with_original_zip(original_zip, temp_dir):
    """将恢复的文件与原始压缩包合并"""
    try:
        # 创建新的临时压缩包
        temp_zip = original_zip + '.temp.zip'
        
        # 复制原始压缩包
        shutil.copy2(original_zip, temp_zip)
        
        # 获取原始压缩包的结构
        logger.info(f"\n处理压缩包: {original_zip}")
        original_structure = get_zip_structure(original_zip)
        success, output = run_7z_command('l', original_zip, "列出压缩包内容")
        if success:
            logger.info("原始压缩包内容:")
            for line in output.splitlines():
                if '...' in line:
                    logger.info(f"  {line.split('...', 1)[1].strip()}")
        
        # 获取压缩包名（不含扩展名）
        zip_name = os.path.splitext(os.path.basename(original_zip))[0]
        logger.info(f"压缩包名: {zip_name}")
        logger.info(f"压缩包结构: {'有根目录 '+original_structure if original_structure else '无根目录'}")
        
        # 创建一个新的临时目录，用于存放清理后的文件结构
        clean_temp_dir = tempfile.mkdtemp()
        try:
            # 获取第一层目录下的所有内容（hash_duplicates, normal_duplicates等）
            category_dirs = os.listdir(temp_dir)
            total_files_found = 0
            
            for category in category_dirs:
                category_path = os.path.join(temp_dir, category)
                if not os.path.isdir(category_path):
                    continue
                
                logger.info(f"\n处理分类目录: {category}")
                # 遍历每个分类目录下的内容
                for item in os.listdir(category_path):
                    item_path = os.path.join(category_path, item)
                    if not os.path.isdir(item_path):
                        # 如果是文件，直接复制到clean_temp_dir
                        clean_file = clean_filename(item)
                        dst_path = os.path.join(clean_temp_dir, clean_file)
                        shutil.copy2(item_path, dst_path)
                        total_files_found += 1
                        logger.info(f"  复制文件: {item} -> {clean_file}")
                        continue
                    
                    logger.info(f"\n  处理时间戳文件夹: {item}")
                    # 检查时间戳文件夹下的内容
                    first_level_items = os.listdir(item_path)
                    if len(first_level_items) == 1 and os.path.isdir(os.path.join(item_path, first_level_items[0])):
                        first_dir = first_level_items[0]
                        clean_first_dir = clean_filename(first_dir)
                        logger.info(f"  发现单一文件夹: {first_dir} (清理后: {clean_first_dir})")
                        
                        # 如果第一层文件夹名与压缩包名相同，且原始压缩包没有同名根目录，则使用其内部内容
                        if clean_first_dir == zip_name and not original_structure:
                            logger.info(f"  检测到文件夹名与压缩包名相同且压缩包无根目录，将使用内部内容")
                            item_path = os.path.join(item_path, first_dir)
                    
                    # 复制内容到临时目录
                    files_in_dir = 0
                    for root, dirs, files in os.walk(item_path):
                        # 计算相对路径
                        rel_path = os.path.relpath(root, item_path)
                        
                        # 复制文件
                        for file in files:
                            src_path = os.path.join(root, file)
                            if rel_path == '.':
                                # 文件在根目录
                                dst_path = os.path.join(clean_temp_dir, file)
                                logger.debug(f"    复制根目录文件: {file}")
                            else:
                                # 文件在子目录
                                dst_path = os.path.join(clean_temp_dir, rel_path, file)
                                logger.debug(f"    复制子目录文件: {os.path.join(rel_path, file)}")
                            
                            # 创建目标目录
                            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                            shutil.copy2(src_path, dst_path)
                            files_in_dir += 1
                            total_files_found += 1
                    
                    logger.info(f"  从 {item} 中复制了 {files_in_dir} 个文件")
            
            logger.info(f"\n总共找到 {total_files_found} 个文件")
            
            # 检查临时目录中的文件结构
            logger.info("\n准备添加到压缩包的文件结构:")
            for root, dirs, files in os.walk(clean_temp_dir):
                rel_path = os.path.relpath(root, clean_temp_dir)
                if rel_path == '.':
                    for file in files:
                        logger.info(f"  {file}")
                else:
                    for file in files:
                        logger.info(f"  {os.path.join(rel_path, file)}")
            
            # 将清理后的文件添加到临时压缩包
            logger.info("\n添加文件到压缩包...")
            success, _ = run_7z_command('a', temp_zip, "添加恢复的文件",
                                      [os.path.join(clean_temp_dir, '*')])
            
            if success:
                # 备份原始压缩包
                backup_zip = original_zip + '.bak'
                shutil.move(original_zip, backup_zip)
                logger.info(f"原始压缩包已备份为: {backup_zip}")
                
                # 将临时压缩包重命名为原始名称
                shutil.move(temp_zip, original_zip)
                logger.info(f"成功恢复文件到: {original_zip}")
                
                # 显示最终压缩包的内容
                success, output = run_7z_command('l', original_zip, "列出最终压缩包内容")
                if success:
                    logger.info("\n最终压缩包内容:")
                    for line in output.splitlines():
                        if '...' in line:
                            logger.info(f"  {line.split('...', 1)[1].strip()}")
                
                return True
            else:
                if os.path.exists(temp_zip):
                    os.remove(temp_zip)
                return False
        finally:
            # 清理额外的临时目录
            if os.path.exists(clean_temp_dir):
                shutil.rmtree(clean_temp_dir)
                
    except Exception as e:
        logger.error(f"合并压缩包时出错: {e}")
        if os.path.exists(temp_zip):
            os.remove(temp_zip)
        return False

def cleanup_temp_directory(temp_dir):
    """清理临时目录"""
    try:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.debug(f"清理临时目录: {temp_dir}")
    except Exception as e:
        logger.error(f"清理临时目录时出错: {e}")

def restore_from_trash(trash_dir):
    """从trash文件夹恢复文件到原始压缩包"""
    temp_dir = None
    try:
        # 获取原始压缩包路径
        original_zip = get_original_zip_path(trash_dir)
        if not original_zip:
            return False
            
        # 创建临时目录
        temp_dir = create_temp_directory()
        
        # 合并trash文件夹
        if not merge_trash_folders(trash_dir, temp_dir):
            return False
            
        # 与原始压缩包合并
        if not merge_with_original_zip(original_zip, temp_dir):
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"恢复过程出错: {e}")
        return False
    finally:
        if temp_dir:
            cleanup_temp_directory(temp_dir)

def process_directory(directories):
    """处理多个目录中的所有trash文件夹"""
    try:
        # 查找所有.trash文件夹
        trash_dirs = []
        for directory in directories:
            if not os.path.exists(directory):
                logger.error(f"目录不存在: {directory}")
                continue
                
            for root, dirs, _ in os.walk(directory):
                for dir_name in dirs:
                    if dir_name.endswith('.trash'):
                        trash_dirs.append(os.path.join(root, dir_name))
        
        if not trash_dirs:
            logger.info("未找到任何.trash文件夹")
            return
            
        # 显示找到的trash文件夹
        logger.info(f"\n找到 {len(trash_dirs)} 个trash文件夹:")
        for i, trash_dir in enumerate(trash_dirs, 1):
            logger.info(f"{i}. {trash_dir}")
            
        # 确认是否继续
        response = input("\n是否继续恢复这些文件夹? (y/n): ").strip().lower()
        if response != 'y':
            logger.info("操作已取消")
            return
            
        # 处理每个trash文件夹
        success_count = 0
        with tqdm(total=len(trash_dirs), desc="恢复进度") as pbar:
            for trash_dir in trash_dirs:
                if restore_from_trash(trash_dir):
                    success_count += 1
                pbar.update(1)
                
        logger.info(f"\n恢复完成: 成功 {success_count}/{len(trash_dirs)}")
        
    except Exception as e:
        logger.error(f"处理目录时出错: {e}")

def main():
    parser = argparse.ArgumentParser(description='从trash文件夹恢复文件到原始压缩包')
    parser.add_argument('directories', nargs='*', help='要处理的目录路径列表')
    args = parser.parse_args()
    
    directories = []
    
    # 首先检查剪贴板
    clipboard_paths = get_clipboard_paths()
    if clipboard_paths:
        directories.extend(clipboard_paths)
    
    # 然后检查命令行参数
    if args.directories:
        directories.extend([d.strip().strip('"') for d in args.directories])
    
    # 如果都没有，请求用户输入
    if not directories:
        user_input = input("请输入要处理的目录路径（多个路径用换行分隔）:\n").strip()
        if user_input:
            directories.extend([d.strip().strip('"') for d in user_input.splitlines() if d.strip()])
    
    if not directories:
        logger.error("未提供任何有效的目录路径")
        return
        
    process_directory(directories)
    
    # 等待用户按回车键退出
    input("\n按回车键退出程序...")

if __name__ == "__main__":
    main() 
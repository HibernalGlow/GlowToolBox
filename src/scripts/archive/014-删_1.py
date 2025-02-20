import os
import re
import shutil
from pathlib import Path
import logging
from colorama import init, Fore, Style
from tqdm import tqdm
import zipfile
import py7zr
import rarfile
import patoolib

# 初始化 colorama
init()

# 配置日志
class ColoredFormatter(logging.Formatter):
    def format(self, record):
        if "移动" in record.msg:
            record.msg = f"🔄 {Fore.YELLOW}{record.msg}{Style.RESET_ALL}"
        elif "错误" in record.msg:
            record.msg = f"❌ {Fore.RED}{record.msg}{Style.RESET_ALL}"
        elif "保留" in record.msg:
            record.msg = f"✅ {Fore.GREEN}{record.msg}{Style.RESET_ALL}"
        elif "检查目录" in record.msg:
            record.msg = f"📂 {Fore.BLUE}{record.msg}{Style.RESET_ALL}"
        else:
            record.msg = f"ℹ️ {Fore.WHITE}{record.msg}{Style.RESET_ALL}"
        return super().format(record)

# 配置日志处理器
logging.basicConfig(level=logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColoredFormatter('%(message)s'))
logging.getLogger('').handlers = [console_handler]

def normalize_filename(filename):
    """标准化文件名（去除数字后缀和空格）"""
    # 去除扩展名
    base, ext = os.path.splitext(filename)
    
    # 去除数字后缀
    base = re.sub(r'_\d', '', base)
    
    # 去除所有空格
    base = re.sub(r'\s+', '', base)
    
    return base.lower() + ext.lower()

def count_images_in_archive(archive_path):
    """统计压缩包中的图片文件数量"""
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.jxl', '.avif'}
    count = 0
    
    try:
        if archive_path.lower().endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                for name in zip_ref.namelist():
                    if any(name.lower().endswith(ext) for ext in image_extensions):
                        count += 1
        elif archive_path.lower().endswith('.7z'):
            with py7zr.SevenZipFile(archive_path, 'r') as sz_ref:
                for name in sz_ref.getnames():
                    if any(name.lower().endswith(ext) for ext in image_extensions):
                        count += 1
        elif archive_path.lower().endswith('.rar'):
            with rarfile.RarFile(archive_path, 'r') as rar_ref:
                for name in rar_ref.namelist():
                    if any(name.lower().endswith(ext) for ext in image_extensions):
                        count += 1
        return count
    except Exception as e:
        logging.error(f"读取压缩包 {os.path.basename(archive_path)} 时出错: {str(e)}")
        return -1

def get_directory_depth(path, base_path):
    """获取目录相对于基础路径的深度"""
    rel_path = os.path.relpath(path, base_path)
    return len(Path(rel_path).parts)

def process_directory(dir_path, source_dir, trash_dir):
    """处理单个目录中的重复文件"""
    # 用于存储当前目录下的文件
    file_groups = {}
    total_files = 0
    moved_count = 0
    duplicate_groups = 0
    
    # 获取当前目录下的所有文件（包括子目录中的文件）
    all_files = []
    for root, _, files in os.walk(dir_path):
        # 如果是当前目录下的文件，直接添加
        if root == dir_path:
            all_files.extend((root, f) for f in files)
    
    # 收集压缩文件
    for root, file in all_files:
        if file.lower().endswith(('.zip', '.rar', '.7z')):
            total_files += 1
            normalized_name = normalize_filename(file)
            full_path = os.path.join(root, file)
            
            if normalized_name not in file_groups:
                file_groups[normalized_name] = []
            file_groups[normalized_name].append(full_path)
    
    # 处理重复文件
    if total_files > 0:
        rel_path = os.path.relpath(dir_path, source_dir)
        logging.info(f"\n检查目录: {rel_path} ({total_files} 个压缩文件)")
        
        for base_name, files in file_groups.items():
            if len(files) > 1:
                duplicate_groups += 1
                # 获取每个文件的图片数量
                file_info = []
                
                # 打印重复文件组信息
                logging.info(f"\n发现重复文件组:")
                for file_path in files:
                    image_count = count_images_in_archive(file_path)
                    is_original = not bool(re.search(r"_\d+\.", os.path.basename(file_path)))
                    file_info.append((file_path, image_count, is_original))
                    logging.info(f"  - {os.path.basename(file_path)} (图片数: {image_count}, {'原始文件' if is_original else '非原始文件'})")
                
                # 按图片数量排序
                file_info.sort(key=lambda x: (-x[1], x[2]))  # 按图片数量降序，原始文件优先
                
                # 找出要保留的文件
                files_to_keep = []
                max_count = file_info[0][1]  # 最大图片数量
                
                # 找出原始文件和图片数量最多的文件
                original_file = next((f for f in file_info if f[2]), None)  # 找原始文件
                max_count_file = file_info[0]  # 图片最多的文件
                
                if original_file:
                    if original_file[1] >= max_count:  # 如果原始文件图片数量最多或相等
                        files_to_keep = [original_file]
                        logging.info(f"\n保留原始文件 (图片数最多): {os.path.basename(original_file[0])} (图片数: {original_file[1]})")
                    else:  # 如果原始文件图片数量不是最多
                        files_to_keep = [original_file, max_count_file]
                        logging.info(f"\n同时保留:")
                        logging.info(f"  - 原始文件: {os.path.basename(original_file[0])} (图片数: {original_file[1]})")
                        logging.info(f"  - 图片最多的文件: {os.path.basename(max_count_file[0])} (图片数: {max_count_file[1]})")
                else:  # 如果没有原始文件，保留图片最多的
                    files_to_keep = [max_count_file]
                    logging.info(f"\n保留图片最多的文件: {os.path.basename(max_count_file[0])} (图片数: {max_count_file[1]})")
                
                # 移动其他文件
                for file_path, img_count, is_original in file_info:
                    if not any(file_path == keep_file[0] for keep_file in files_to_keep):
                        try:
                            # 构建目标路径，保持原有的目录结构
                            rel_path = os.path.relpath(os.path.dirname(file_path), source_dir)
                            target_dir = os.path.join(trash_dir, rel_path)
                            Path(target_dir).mkdir(parents=True, exist_ok=True)
                            
                            target_path = os.path.join(target_dir, os.path.basename(file_path))
                            
                            # 如果目标文件已存在，添加数字后缀
                            if os.path.exists(target_path):
                                base, ext = os.path.splitext(target_path)
                                counter = 1
                                while os.path.exists(f"{base}_{counter}{ext}"):
                                    counter += 1
                                target_path = f"{base}_{counter}{ext}"
                            
                            # 移动文件
                            shutil.move(file_path, target_path)
                            moved_count += 1
                            rel_source_path = os.path.relpath(file_path, source_dir)
                            rel_target_path = os.path.relpath(target_path, trash_dir)
                            logging.info(f"移动: {rel_source_path} -> {rel_target_path} (图片数: {img_count})")
                            
                        except Exception as e:
                            logging.error(f"移动文件时出错 {os.path.relpath(file_path, source_dir)}: {str(e)}")
    
    return total_files, duplicate_groups, moved_count

def process_duplicates(source_dir, trash_dir):
    """处理所有目录下的重复文件，从最深层开始"""
    # 确保trash目录存在
    Path(trash_dir).mkdir(parents=True, exist_ok=True)
    
    # 收集所有目录及其深度
    all_dirs = []
    for root, dirs, _ in os.walk(source_dir):
        # 跳过trash目录
        if os.path.abspath(root) == os.path.abspath(trash_dir):
            continue
        all_dirs.append((root, get_directory_depth(root, source_dir)))
    
    # 按深度降序排序目录（最深的先处理）
    all_dirs.sort(key=lambda x: (-x[1], x[0]))
    
    total_files = 0
    total_duplicate_groups = 0
    total_moved = 0
    
    print(f"\n🔍 扫描目录: {source_dir}")
    
    # 遍历处理每个目录
    with tqdm(total=len(all_dirs), desc="处理目录", unit="dir") as pbar:
        for dir_path, depth in all_dirs:
            files, duplicates, moved = process_directory(dir_path, source_dir, trash_dir)
            total_files += files
            total_duplicate_groups += duplicates
            total_moved += moved
            pbar.update(1)
    
    # 打印总体统计信息
    print(f"\n✨ 处理完成:")
    print(f"- 扫描了 {total_files} 个压缩文件")
    print(f"- 发现了 {total_duplicate_groups} 组重复文件")
    print(f"- 移动了 {total_moved} 个重复文件到 {trash_dir}")

if __name__ == "__main__":
    source_directory = r"E:\1EHV"
    trash_directory = os.path.join(source_directory, "trash")
    process_duplicates(source_directory, trash_directory) 
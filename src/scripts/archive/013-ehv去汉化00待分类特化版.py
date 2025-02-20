import os
import zipfile
import shutil
from PIL import Image
import imagehash
import io
import logging
import json
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import sys
import warnings
from tqdm import tqdm
import yaml
import subprocess
import pillow_jxl
import pillow_avif
from PIL import Image, ExifTags
import re  # 用于匹配哈希值的正则表达式
import datetime


# 配置日志记录
log_file = "process_log.log"
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 配置文件日志处理器，使用 UTF-8 编码
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# 配置控制台日志处理器，使用 UTF-8 编码
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

# 禁用 zipfile 模块的重复文件名警告
warnings.filterwarnings('ignore', category=UserWarning, module='zipfile')

def load_processed_zips_uuid(processed_zips_file):
    """从 YAML 文件中加载已处理的压缩包 UUID 集合。"""
    if os.path.exists(processed_zips_file):
        with open(processed_zips_file, 'r', encoding='utf-8') as file:
            try:
                # 只加载 UUID，不加载文件名
                return set(yaml.safe_load(file) or [])
            except yaml.YAMLError as e:
                logger.error(f"Error reading processed UUIDs from {processed_zips_file}: {e}")
    return set()

def save_processed_zips_uuid(processed_zips_file, processed_zips_set):
    """将处理过的压缩包 UUID 集合保存到 YAML 文件中。"""
    with open(processed_zips_file, 'w', encoding='utf-8') as file:
        try:
            # 只保存 UUID 集合
            yaml.safe_dump(list(processed_zips_set), file)
        except yaml.YAMLError as e:
            logger.error(f"Error saving processed UUIDs to {processed_zips_file}: {e}")

def load_hashes(hash_file):
    if os.path.exists(hash_file):
        try:
            with open(hash_file, 'r') as f:
                data = json.load(f)
                if data:
                    return set(imagehash.hex_to_hash(h) for h in data)
        except json.JSONDecodeError:
            pass
    return set()

def save_hashes(hash_file, hashes):
    with open(hash_file, 'w') as f:
        json.dump([str(h) for h in hashes], f)

def load_yaml_uuid_from_archive(archive_path):
    """尝试从压缩包内加载 YAML 文件以获取 UUID（文件名）。"""
    try:
        command = ['7z', 'l', archive_path]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.endswith('.yaml'):
                parts = line.split()
                yaml_filename = parts[-1]
                yaml_uuid = os.path.splitext(yaml_filename)[0]
                return yaml_uuid
    except Exception as e:
        print(f"无法加载压缩包中的 YAML 文件: {e}")
    return None

def get_image_hash(img_bytes):
    try:
        img = Image.open(io.BytesIO(img_bytes))
        return imagehash.phash(img)
    except Exception as e:
        # 捕获所有异常并记录错误，然后跳过该图片
        # logger.error(f"Error processing image: {e}")
        return None

# 判断两张图片是否相似
def are_images_similar(hash1, hash2, threshold):
    return abs(hash1 - hash2) <= threshold

# 使用7z命令行工具列出压缩包内容（隐藏日志）
import subprocess
import locale
locale.setlocale(locale.LC_COLLATE, 'zh_CN.UTF-8')  # 根据你的操作系统设置合适的locale

def natural_sort_key(s):
    """将字符串s转换成一个用于自然排序的键"""
    return [int(text) if text.isdigit() else locale.strxfrm(text) for text in re.split('([0-9]+)', s)]

def list_zip_contents(zip_path):
    """使用7z列出压缩包内的所有文件，并按照自然顺序排序"""
    try:
        result = subprocess.run(['7z', 'l', zip_path], capture_output=True, text=True, check=True)
        file_list = []
        for line in result.stdout.splitlines():
            if line.endswith(('.png', '.jpg', '.jpeg', '.webp', '.avif', '.avif', '.jxl')):
                file_list.append(line.split()[-1])

        # 使用自然排序进行排序
        sorted_file_list = sorted(file_list, key=natural_sort_key)

        return sorted_file_list

    except subprocess.CalledProcessError as e:
        logger.error(f"Error listing zip contents: {e}")
        return []

# 示例调用
# sorted_files = list_zip_contents('example.zip')
# print(sorted_files)
# 设置locale为中文，通常在程序开始时进行设置

# 使用7z提取部分文件（隐藏日志、异步处理）
def extract_files(zip_path, files_to_extract, output_dir):
    """使用7z提取部分文件"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        subprocess.run(['7z', 'e', zip_path, '-o' + output_dir] + files_to_extract, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # print(f"Extracted files: {files_to_extract}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error extracting files: {e}")

# 使用7z统一删除和更新压缩包文件（隐藏日志）
def update_zip(zip_path, files_to_delete, files_to_add):
    """使用7z删除旧文件并更新新文件"""
    try:
        # 删除压缩包中的原文件
        if files_to_delete:
            subprocess.run(['7z', 'd', zip_path] + files_to_delete, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # print(f"Deleted from {zip_path}")

        # 添加新文件到压缩包
        if files_to_add:
            subprocess.run(['7z', 'u', zip_path] + files_to_add, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # print(f"Updated {zip_path}")

    except subprocess.CalledProcessError as e:
        logger.error(f"Error updating zip: {e}")
        pass


# def generate_unique_filename(file_name,uuid):
#     """生成唯一文件名"""
#     name, ext = os.path.splitext(file_name)
#     return f"{name}_{uuid}{ext}"


def process_zip(zip_path, compare_images_hashes, processed_zips_set, processed_zips_file, threshold, num_start=3, num_end=3):
    try:
        # 生成基于压缩包名称的临时文件夹名
        original_stat = os.stat(zip_path)
        base_name = os.path.basename(zip_path)
        output_dir = os.path.join(os.path.dirname(zip_path), base_name + '_temp')

        # 提取压缩包的 UUID
        uuid = load_yaml_uuid_from_archive(zip_path)

        # 检查是否已经处理过该压缩包，如果是则直接跳过
        if uuid and uuid in processed_zips_set:
            return

        # 列出压缩包中的所有文件
        all_files = list_zip_contents(zip_path)

        # 处理列表为空的情况
        if not all_files:
            logger.warning(f"No files found in {zip_path} or the zip file is corrupted.")
            return

        # 筛选前 num_start 和后 num_end 个图片文件
        img_files = [f for f in all_files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.avif', '.avif', '.jxl'))]

        # 确保不超过列表长度
        num_files_to_process = min(len(img_files), num_start + num_end)  # 获取要处理的文件总数
        img_files_to_process = img_files[:num_files_to_process] if num_files_to_process > 0 else []

        # 优化切片，确保获取前 num_start 和后 num_end 个文件
        if num_files_to_process == 0:
            logger.warning(f"No valid image files found in {zip_path}.")
        else:
            start_files = img_files[:num_start]
            end_files = img_files[-num_end:] if num_files_to_process > num_start else img_files[num_start:]  # 确保不会同时取出超出范围的文件
            img_files_to_process = start_files + end_files

        # 提取这些图片到临时目录
        extract_files(zip_path, img_files_to_process, output_dir)

        files_to_delete = []
        files_to_add = []
        hash_pattern = re.compile(r"\[hash-(?P<hash>[0-9a-fA-F]+)\]")
        save_uuid_needed = False

        # 处理每个提取出的文件
        for file_name in img_files_to_process:
            file_path = os.path.join(output_dir, file_name)

            # 检查文件是否可读
            if not os.access(file_path, os.R_OK):
                logger.warning(f"File is not readable and may be in use: {file_path}")
                continue

            hash_file_name_changed = False

            # 检查文件名是否已包含哈希
            match = hash_pattern.search(file_name)
            if match:
                img_hash = imagehash.hex_to_hash(match.group('hash'))
            else:
                with open(file_path, 'rb') as f:
                    img_bytes = f.read()
                img_hash = get_image_hash(img_bytes)

                # 如果哈希计算失败，则跳过该图片
                if img_hash is None:
                    continue

                # 更新文件名，添加哈希
                if file_name not in files_to_delete:
                    files_to_delete.append(file_name)
                name, ext = os.path.splitext(file_name)
                hash_file_name = f"{name}[hash-{img_hash}]{ext}"
                hash_file_path = os.path.join(output_dir, hash_file_name)
                os.rename(file_path, hash_file_path)
                file_name = hash_file_name
                file_path = hash_file_path
                hash_file_name_changed = True
            
            if any(are_images_similar(img_hash, compare_hash, threshold) for compare_hash in compare_images_hashes):
                new_file_name = file_name + ".tdel"
                save_uuid_needed = True
                new_file_path = os.path.join(output_dir, new_file_name)
                os.rename(file_path, new_file_path)
                if file_name not in files_to_delete:
                    files_to_delete.append(file_name)
                if new_file_path not in files_to_add:
                    files_to_add.append(new_file_path)
            elif hash_file_name_changed:
                files_to_add.append(file_path)

        # 更新压缩包（先删除，再添加）
        if files_to_delete or files_to_add:
            update_zip(zip_path, files_to_delete, files_to_add)

        if save_uuid_needed:
            processed_zips_set.add(uuid)
            save_processed_zips_uuid(processed_zips_file, processed_zips_set)

        # 清理临时文件
        shutil.rmtree(output_dir)
        os.utime(zip_path, (original_stat.st_atime, original_stat.st_mtime))

    except Exception as e:
        logger.error(f"Error processing zip file {zip_path}: {e}")

def process_zip_batch(zip_paths, compare_images_hashes, processed_zips_set, processed_zips_file, threshold, num_start=3, num_end=3):
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(process_zip, zip_path, compare_images_hashes, processed_zips_set, processed_zips_file, threshold, num_start, num_end)
            for zip_path in zip_paths
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error processing zip file: {e}")

def process_all_zips(root_folder, compare_images_hashes, processed_zips_set, processed_zips_file, threshold, enable_processed_zips, exclude_keywords, max_workers=8, num_start=3, num_end=3):
    zip_paths = []
    lock = Lock()

    for foldername, subfolders, filenames in os.walk(root_folder):
        if any(keyword in foldername for keyword in exclude_keywords):
            continue

        for filename in filenames:
            if filename.lower().endswith('.zip'):
                zip_path = os.path.join(foldername, filename)

                # # 自定义路径
                # custom_path = 'E:\\1EHV\\[黒輪]\\(COMIC快楽天ビースト 19-7) デリガール [就變態 x 我尻故我在 #50][黒輪].zip' 

                # # 用绝对路径进行比较
                # zip_path = os.path.abspath(zip_path)
                # custom_path = os.path.abspath(custom_path)

                # # 字符串比较
                # if zip_path > custom_path:  
                #     zip_paths.append(zip_path)
                # else:
                #     logger.info(f"Skipping zip file before custom path: {zip_path}")
                
                zip_paths.append(zip_path)

    total_files = len(zip_paths)
    with tqdm(total=total_files, desc="Processing zips", unit="zip") as pbar:
        def update_progress():
            pbar.update(1)

        def process_zip_with_progress(zip_path, compare_images_hashes, processed_zips_set, processed_zips_file, threshold, num_start, num_end):
            process_zip(zip_path, compare_images_hashes, processed_zips_set, processed_zips_file, threshold, num_start, num_end)
            update_progress()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(process_zip_with_progress, zip_path, compare_images_hashes, processed_zips_set, processed_zips_file, threshold, num_start, num_end)
                for zip_path in zip_paths
            ]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error processing zip file: {e}")

    # # 批处理结束后，保存 UUID 集合（这一行可以保留，虽然已经在 process_zip 里做了处理）
    # save_processed_zips_uuid(processed_zips_file, processed_zips_set)
def record_folder_timestamps(target_directory):
    """记录target_directory下所有文件夹的时间戳。"""
    folder_timestamps = {}
    for root, dirs, files in os.walk(target_directory):
        for dir in dirs:
            folder_path = os.path.join(root, dir)
            folder_stat = os.stat(folder_path)
            folder_timestamps[folder_path] = (folder_stat.st_atime, folder_stat.st_mtime)
            
        
        # # 记录文件的时间戳
        # for file in files:
        #     file_path = os.path.join(root, file)
        #     file_stat = os.stat(file_path)
        #     folder_timestamps[file_path] = (file_stat.st_atime, file_stat.st_mtime)
    
    return folder_timestamps

def restore_folder_timestamps(folder_timestamps):
    """恢复之前记录的文件夹时间戳。"""
    for folder_path, (atime, mtime) in folder_timestamps.items():
        if os.path.exists(folder_path):
            os.utime(folder_path, (atime, mtime))

# 文件时间戳要考虑重命名文件导致的变化
# def restore_folder_and_file_timestamps(timestamps):
#     """恢复之前记录的所有文件夹和文件的时间戳。"""
#     for path, (atime, mtime) in timestamps.items():
#         if os.path.exists(path):
#             os.utime(path, (atime, mtime))

def get_filter_date():
    """获取用户输入的过滤日期"""
    date_str = input("请输入日期 (yyyy-mm-dd): ")
    return datetime.datetime.strptime(date_str, "%Y-%m-%d")
def main():
    zip_folder = r"E:\1EHV\[00待分类]"  # 压缩包所在的目录
    older_timestamps = record_folder_timestamps(zip_folder)
    compare_folder = 'E:\\1EHV\\[00去图]'
    processed_zips_file = 'E:\\1EHV\\[00去图]\\processed_zips_uuid.yaml'
    hash_file = 'E:\\1EHV\\[00去图]\\image_hashes.json'
    threshold = 8 # 相似度阈值，越小越严格
    enable_processed_zips = True
    exclude_keywords = ["美少女万華鏡", "00去图", "图集","00去图","fanbox","02COS","02杂"]
    max_workers = 14
    update_hashes = True

    num_start = 3  # 自定义处理前多少张图片
    num_end = 3  # 自定义处理后多少张图片

    # 获取过滤日期
    # filter_date = get_filter_date()

    compare_images_hashes = load_hashes(hash_file)
    for file_name in os.listdir(compare_folder):
        if file_name.lower().endswith(('.png', '.jpg', '.webp', '.jpeg', '.avif', '.avif', '.jxl')):
            with open(os.path.join(compare_folder, file_name), 'rb') as f:
                img_bytes = f.read()
                img_hash = get_image_hash(img_bytes)
                compare_images_hashes.add(img_hash)
    if update_hashes:
        save_hashes(hash_file, compare_images_hashes)

    processed_zips_set = load_processed_zips_uuid(processed_zips_file) if enable_processed_zips else {}
    process_all_zips(zip_folder, compare_images_hashes, processed_zips_set, processed_zips_file, threshold, enable_processed_zips, exclude_keywords, max_workers, num_start, num_end)
    restore_folder_timestamps(older_timestamps)

if __name__ == "__main__":
    main()
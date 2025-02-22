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
from logging.handlers import RotatingFileHandler
import argparse
import pyperclip
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Button, Header, Footer, RadioSet, RadioButton, Static, Label
from textual.screen import Screen
from textual import events
from textual.binding import Binding
from textual.widgets._radio_button import RadioButton
from rich.text import Text
from textual.widgets import RichLog
from textual.coordinate import Coordinate
from textual.scroll_view import ScrollView
from textual.reactive import reactive
from textual.message import Message
from textual.worker import Worker, get_current_worker
from textual.widgets import DataTable
from textual.design import ColorSystem
from nodes.record.logger_config import setup_logger
config = {
    'script_name': 'recruit_remove',
}
logger, config_info = setup_logger(config)

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
    hash_pattern = re.compile(r"\[hash-(?P<hash>[0-9a-fA-F]+)\]")
    compare_images_hashes = set()
    files_to_rename = []  # 存储需要重命名的文件信息
    
    # 从 hash_file 加载已保存的哈希值
    if os.path.exists(hash_file):
        try:
            with open(hash_file, 'r') as f:
                data = json.load(f)
                if data:
                    compare_images_hashes.update(imagehash.hex_to_hash(h) for h in data)
        except json.JSONDecodeError:
            pass
    
    # 从文件名中提取哈希值或计算新的哈希值
    compare_folder = 'E:\\1EHV\\[00去图]'
    for file_name in os.listdir(compare_folder):
        if file_name.lower().endswith(('.png', '.jpg', '.webp', '.jpeg','.avif', '.jxl')):
            # 检查文件名中是否已包含哈希值
            match = hash_pattern.search(file_name)
            if match:
                # 直接从文件名中提取哈希值
                img_hash = imagehash.hex_to_hash(match.group('hash'))
                compare_images_hashes.add(img_hash)
            else:
                # 计算新的哈希值
                file_path = os.path.join(compare_folder, file_name)
                try:
                    with open(file_path, 'rb') as f:
                        img_bytes = f.read()
                        img_hash = get_image_hash(img_bytes)
                        if img_hash:
                            compare_images_hashes.add(img_hash)
                            # 将需要重命名的文件信息存储起来
                            name, ext = os.path.splitext(file_name)
                            new_name = f"{name}[hash-{img_hash}]{ext}"
                            files_to_rename.append((file_path, os.path.join(compare_folder, new_name)))
                except Exception as e:
                    logger.error(f"处理文件 {file_path} 时出错: {e}")
                    continue
    
    # 保存需要重命名的文件信息
    rename_info_file = os.path.join(compare_folder, 'files_to_rename.json')
    try:
        with open(rename_info_file, 'w', encoding='utf-8') as f:
            json.dump(files_to_rename, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存重命名信息时出错: {e}")
    
    return compare_images_hashes

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

# 使用7z命令行工具列出压缩内容（隐藏日志）
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
        all_files = []
        image_files = []
        
        # 支持的图片格式和关键词文件
        image_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.avif', '.jxl')
        
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 1:
                file_name = parts[-1]
                # 记录所有文件（包括文件夹路径）
                all_files.append(file_name)
                # 记录图片文件
                if any(file_name.lower().endswith(ext) for ext in image_extensions):
                    image_files.append(file_name)

        # 使用自然排序进行排序
        sorted_image_files = sorted(image_files, key=natural_sort_key)
        return all_files, sorted_image_files

    except subprocess.CalledProcessError as e:
        logger.error(f"无法处理压缩包 {zip_path}: {e}")
        return [], []
    except Exception as e:
        logger.error(f"处理压缩包时发生意外错误 {zip_path}: {e}")
        return [], []

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

def init_folder_stats():
    return {
        'total_files': 0,
        'processed_files': 0,
        'modified_files': 0,
        'skipped_files': 0,
        'errors': [],
        'start_time': datetime.datetime.now()
    }

def process_zip(zip_path, compare_images_hashes, processed_zips_set, processed_zips_file, 
               threshold, folder_stats, num_start=3, num_end=3, ignore_processed_zips=False, 
               use_tdel=True, use_trash=True):
    try:
        folder_stats['total_files'] += 1
        output_dir = os.path.join(os.path.dirname(zip_path), os.path.basename(zip_path) + '_temp')
        
        try:
            original_stat = os.stat(zip_path)
        except Exception as e:
            logger.error(f"无法访问压缩包 {zip_path}: {e}")
            folder_stats['skipped_files'] += 1
            folder_stats['processed_files'] += 1
            return

        logger.info(f"开始处理压缩包: {zip_path}")
        
        # 获取压缩包内所有文件和图片文件列表
        all_files, img_files = list_zip_contents(zip_path)
        logger.info(f"压缩包内文件总数: {len(all_files)}, 图片文件数: {len(img_files)}")
        
        # 定义需要删除的关键词
        keywords_to_delete = ['绅士的快乐', '招募','汉化组']
        files_to_delete = []
        needs_modification = False
        save_uuid_needed = False
        
        # 检查文件名中是否包含关键词
        for file_path in all_files:
            for keyword in keywords_to_delete:
                if keyword in file_path:
                    files_to_delete.append(file_path)
                    logger.info(f"发现包含关键词'{keyword}'的文件: {file_path}")
                    break
        
        # 检查.tdel文件
        tdel_files = [f for f in all_files if f.endswith('.tdel')]
        if not use_tdel and tdel_files:
            files_to_delete.extend(tdel_files)
            logger.info(f"发现.tdel文件: {', '.join(tdel_files)}")

        # 如果有文件需要删除，执行删除操作
        if files_to_delete:
            try:
                logger.info(f"准备删除以下文件: {', '.join(files_to_delete)}")
                delete_command = ['7z', 'd', zip_path] + files_to_delete
                logger.debug(f"执行命令: {' '.join(delete_command)}")
                
                result = subprocess.run(delete_command, 
                                      capture_output=True,
                                      text=True,
                                      check=True)
                
                logger.info(f"删除命令输出: {result.stdout}")
                if result.stderr:
                    logger.warning(f"删除命令错误输出: {result.stderr}")
                
                logger.info(f"已从压缩包删除 {len(files_to_delete)} 个文件")
                needs_modification = True
                save_uuid_needed = True
            except subprocess.CalledProcessError as e:
                logger.error(f"删除文件时出错: {e}")
                logger.error(f"错误输出: {e.stderr if hasattr(e, 'stderr') else '无错误输出'}")

        # 只在需要检查已处理文件时才加载 UUID
        uuid = None
        if not ignore_processed_zips:
            uuid = load_yaml_uuid_from_archive(zip_path)
            if uuid and uuid in processed_zips_set:
                return

        # 获取图片文件列表（现在使用之前获取的 img_files）
        tdel_files = [f for f in img_files if f.endswith('.tdel')]
        
        # 如果发现 .tdel 文件且 use_tdel 为 False，则删除这些文件
        if not use_tdel and tdel_files:
            logger.info(f"发现 .tdel 文件在压缩包中: {zip_path}")
            needs_modification = True
            files_to_delete.extend(tdel_files)
            save_uuid_needed = True

        if not img_files:
            logger.warning(f"压缩包中未找到图片文件: {zip_path}")
            folder_stats['skipped_files'] += 1
            folder_stats['processed_files'] += 1
            return

        # 修改文件选择逻辑
        files_to_process = []
        total_images = len(img_files)
        
        if total_images <= (num_start + num_end):
            # 如果总数小于或等于要处理的总数量，处理所有图片
            files_to_process = img_files
            # logger.debug(f"图片总数({total_images})小于或等于指定处理数量({num_start}+{num_end})，处理所有图片")
        else:
            # 分别获取前num_start和后num_end张图片
            files_to_process = img_files[:num_start]  # 前面的图片
            files_to_process.extend(img_files[-num_end:])  # 后面的图片
            # logger.debug(f"处理前{num_start}张和后{num_end}张图片，总共{len(files_to_process)}/{total_images}张")

        # 提取选定的文件
        extract_files(zip_path, files_to_process, output_dir)

        files_to_delete = []
        files_to_add = []
        hash_pattern = re.compile(r"\[hash-(?P<hash>[0-9a-fA-F]+)\]")
        save_uuid_needed = False
        needs_modification = False  # 新增标志位,用于标记是否需要修改压缩包

        # 处理提取的文件
        for file_name in files_to_process:
            file_path = os.path.join(output_dir, file_name)
            
            if not os.path.exists(file_path):
                continue

            # 添加处理开始的日志
            # logger.info(f"正在处理: {os.path.basename(zip_path)} -> {file_name}")

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
            
            # 检查哈希是否为全白或全黑
            if is_hash_all_white_or_black(img_hash):
                logger.info(f"检测到全白/全黑图片: {file_path}")
                needs_modification = True
                if use_tdel:
                    new_file_name = file_name + ".tdel"
                    logger.info(f"添加.tdel后缀: {file_path} -> {new_file_name}")
                    new_file_path = os.path.join(output_dir, new_file_name)
                    os.rename(file_path, new_file_path)
                    if file_name not in files_to_delete:
                        files_to_delete.append(file_name)
                    if new_file_path not in files_to_add:
                        files_to_add.append(new_file_path)
                else:
                    logger.info(f"将删除文件: {file_path}")
                    if file_name not in files_to_delete:
                        files_to_delete.append(file_name)
                save_uuid_needed = True
            
            elif any(are_images_similar(img_hash, compare_hash, threshold) for compare_hash in compare_images_hashes):
                logger.info(f"检测到相似图片: {file_path}")
                needs_modification = True
                if use_tdel:
                    new_file_name = file_name + ".tdel"
                    logger.info(f"添加.tdel后缀: {file_path} -> {new_file_name}")
                    new_file_path = os.path.join(output_dir, new_file_name)
                    os.rename(file_path, new_file_path)
                    if file_name not in files_to_delete:
                        files_to_delete.append(file_name)
                    if new_file_path not in files_to_add:
                        files_to_add.append(new_file_path)
                else:
                    logger.info(f"将删除文件: {file_path}")
                    if file_name not in files_to_delete:
                        files_to_delete.append(file_name)
                save_uuid_needed = True
            
            elif hash_file_name_changed:
                logger.info(f"更新文件名: {file_path} in {os.path.basename(zip_path)}")
                needs_modification = True  # 文件名改变也需要更新压缩包
                files_to_add.append(file_path)

        # 只有当需要修改时才更新压缩包
        if needs_modification and (files_to_delete or files_to_add):
            update_zip(zip_path, files_to_delete, files_to_add)
            
            if save_uuid_needed:
                processed_zips_set.add(uuid)
                save_processed_zips_uuid(processed_zips_file, processed_zips_set)
                
            # 更新统计信息
            folder_stats['modified_files'] += 1

        # 在完成压缩包处理时添加总结日志
        if needs_modification:
            logger.info(f"完成压缩包处理: {os.path.basename(zip_path)}")
            if files_to_delete:
                logger.info(f"删除的文件: {', '.join(files_to_delete)}")
            if files_to_add:
                logger.info(f"添加的文件: {', '.join([os.path.basename(f) for f in files_to_add])}")

        # 清理临时文件
        shutil.rmtree(output_dir)
        os.utime(zip_path, (original_stat.st_atime, original_stat.st_mtime))

        # 更新统计信息
        folder_stats['processed_files'] += 1
        if files_to_delete or files_to_add:
            folder_stats['modified_files'] += 1
        if uuid and uuid in processed_zips_set:
            folder_stats['skipped_files'] += 1

    except Exception as e:
        error_msg = f"处理压缩包时出错 {zip_path}: {e}"
        logger.error(error_msg)
        folder_stats['errors'].append(error_msg)
        folder_stats['skipped_files'] += 1
        folder_stats['processed_files'] += 1

def print_folder_report(folder_path, stats):
    # 检查是否有任何修改操作
    if stats['modified_files'] == 0:
        return

    end_time = datetime.datetime.now()
    duration = end_time - stats['start_time']
    
    print(f"\n{'='*50}")
    print(f"文件夹处理报告: {folder_path}")
    print(f"{'='*50}")
    print(f"开始时间: {stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"处理时长: {duration}")
    print(f"\n统计信息:")
    print(f"- 总文件数: {stats['total_files']}")
    print(f"- 已处理: {stats['processed_files']}")
    print(f"- 已修改: {stats['modified_files']}")
    print(f"- 已跳过: {stats['skipped_files']}")
    print(f"- 错误数: {len(stats['errors'])}")
    
    if stats['errors']:
        print("\n错误日志:")
        for error in stats['errors']:
            print(f"- {error}")
    print(f"{'='*50}\n")

def process_all_zips(root_folder, compare_images_hashes, processed_zips_set, processed_zips_file, 
                     threshold, enable_processed_zips, exclude_keywords, max_workers=8, 
                     num_start=3, num_end=3, ignore_processed_zips=False, use_tdel=True, use_trash=True):
    folder_stats_dict = {}
    
    all_zip_files = []
    for foldername, _, filenames in os.walk(root_folder):
        if any(keyword in foldername for keyword in exclude_keywords):
            continue
        zip_files = [os.path.join(foldername, f) for f in filenames 
                    if f.lower().endswith(('.zip', '.cbz'))]
        all_zip_files.extend(zip_files)

    if not all_zip_files:
        logger.info("没有找到需要处理的ZIP文件")
        return

    # 创建总进度条
    total_pbar = tqdm(total=len(all_zip_files), 
                     desc="总进度", 
                     position=0, 
                     leave=True,
                     ncols=100,
                     bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]')
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for zip_path in all_zip_files:
            foldername = os.path.dirname(zip_path)
            if foldername not in folder_stats_dict:
                folder_stats_dict[foldername] = init_folder_stats()
            
            future = executor.submit(
                process_zip, 
                zip_path, 
                compare_images_hashes, 
                processed_zips_set,
                processed_zips_file, 
                threshold, 
                folder_stats_dict[foldername],
                num_start, 
                num_end,
                ignore_processed_zips,
                use_tdel,
                use_trash
            )
            futures[future] = zip_path

        # 当前处理文件的状态行
        current_status = tqdm(total=0, 
                            desc="当前文件", 
                            position=1, 
                            leave=False,
                            bar_format='{desc}: {postfix}')

        for future in as_completed(futures):
            zip_path = futures[future]
            try:
                future.result()
                logger.info(f"处理完成: {os.path.basename(zip_path)}")
            except Exception as e:
                logger.error(f"跳过处理出错的压缩包 {os.path.basename(zip_path)}: {e}")
            finally:
                total_pbar.update(1)
                current_status.set_postfix_str(os.path.basename(zip_path))

        current_status.close()
    total_pbar.close()

    # 打印所有文件夹的报告
    for foldername, stats in folder_stats_dict.items():
        print_folder_report(foldername, stats)

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

def batch_rename_files():
    """批量重命名文件的独立函数"""
    rename_info_file = 'E:\\1EHV\\[00去图]\\files_to_rename.json'
    if not os.path.exists(rename_info_file):
        return
    
    try:
        with open(rename_info_file, 'r', encoding='utf-8') as f:
            files_to_rename = json.load(f)
        
        success_count = 0
        for old_path, new_path in files_to_rename:
            try:
                if os.path.exists(old_path) and not os.path.exists(new_path):
                    os.rename(old_path, new_path)
                    success_count += 1
            except Exception as e:
                logger.error(f"重命名文件时出错 {old_path}: {e}")
        
        logger.info(f"成功重命名 {success_count}/{len(files_to_rename)} 个文件")
        
        # 重命名完成后删除记录文件
        if success_count == len(files_to_rename):
            os.remove(rename_info_file)
            
    except Exception as e:
        logger.error(f"读取重命名信息时出错: {e}")

def is_hash_all_white_or_black(img_hash):
    """检查哈希是否对应全白或全黑的图片"""
    # 预定义的全白或全黑哈希值列表
    hash_list = ['ffffffffffffffff', '0000000000000000', '0000000000000000', '0000000000000001']
    return str(img_hash) in hash_list

def move_to_trash(original_path, zip_folder, use_trash=True):
    """将文件移动到统一的 .trash 文件夹，保持原有目录结构"""
    if not use_trash:
        logger.info(f"use_trash为False，直接删除文件: {original_path}")
        os.remove(original_path)
        return

    # 创建统一的 .trash 目录
    trash_base = os.path.join(zip_folder, '.trash')
    logger.info(f"创建回收站目录: {trash_base}")
    
    try:
        # 获取相对于 zip_folder 的路径
        rel_path = os.path.relpath(original_path, zip_folder)
        logger.info(f"计算相对路径: {rel_path}")
    except ValueError as e:
        # 如果文件不在 zip_folder 下，使用完整路径结构
        logger.warning(f"计算相对路径失败: {e}")
        rel_path = original_path.lstrip(os.path.sep)
        logger.info(f"使用完整路径: {rel_path}")
    
    # 构建目标路径
    trash_path = os.path.join(trash_base, rel_path)
    logger.info(f"构建目标路径: {trash_path}")
    
    try:
        # 确保目标目录存在
        os.makedirs(os.path.dirname(trash_path), exist_ok=True)
        logger.info(f"创建目标目录: {os.path.dirname(trash_path)}")
        
        # 如果目标文件已存在，添加时间戳
        if os.path.exists(trash_path):
            name, ext = os.path.splitext(trash_path)
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            trash_path = f"{name}_{timestamp}{ext}"
            logger.info(f"文件已存在，添加时间戳: {trash_path}")
        
        # 移动文件
        shutil.move(original_path, trash_path)
        logger.info(f"成功移动文件到回收站: {trash_path}")
    except Exception as e:
        logger.error(f"移动文件到回收站失败: {e}")
        raise

def process_single_image(image_path, compare_images_hashes, threshold, folder_stats, zip_folder, use_tdel=True, use_trash=True):
    """处理单个图片文件"""
    try:
        folder_stats['total_files'] += 1
        
        # 检查文件名中是否已包含哈希值
        hash_pattern = re.compile(r"\[hash-(?P<hash>[0-9a-fA-F]+)\]")
        base_name = os.path.basename(image_path)
        match = hash_pattern.search(base_name)
        
        if match:
            img_hash = imagehash.hex_to_hash(match.group('hash'))
        else:
            with open(image_path, 'rb') as f:
                img_bytes = f.read()
            img_hash = get_image_hash(img_bytes)
            
            if img_hash is None:
                logger.error(f"无法处理图片: {image_path}")
                folder_stats['errors'].append(f"无法处理图片: {image_path}")
                folder_stats['skipped_files'] += 1
                return

            # 更新文件名，添加哈希
            name, ext = os.path.splitext(base_name)
            new_name = f"{name}[hash-{img_hash}]{ext}"
            new_path = os.path.join(os.path.dirname(image_path), new_name)
            
            # 如果目标文件已存在，添加计数后缀
            counter = 1
            while os.path.exists(new_path):
                new_name = f"{name}[hash-{img_hash}]_{counter}{ext}"
                new_path = os.path.join(os.path.dirname(image_path), new_name)
                counter += 1
                
            os.rename(image_path, new_path)
            image_path = new_path
            
        # 检查是否为全白/全黑图片
        if is_hash_all_white_or_black(img_hash):
            logger.info(f"检测到全白/全黑图片: {image_path}")
            if use_tdel:
                new_path = image_path + ".tdel"
                os.rename(image_path, new_path)
            else:
                move_to_trash(image_path, zip_folder, use_trash)
            folder_stats['modified_files'] += 1
            
        # 检查是否与比较集中的图片相似
        elif any(are_images_similar(img_hash, compare_hash, threshold) for compare_hash in compare_images_hashes):
            logger.info(f"检测到相似图片: {image_path}")
            if use_tdel:
                new_path = image_path + ".tdel"
                os.rename(image_path, new_path)
            else:
                move_to_trash(image_path, zip_folder, use_trash)
            folder_stats['modified_files'] += 1
            
        folder_stats['processed_files'] += 1
        
    except Exception as e:
        error_msg = f"处理图片时出错 {image_path}: {e}"
        logger.error(error_msg)
        folder_stats['errors'].append(error_msg)
        folder_stats['skipped_files'] += 1

def process_directory(directory_path, compare_images_hashes, threshold, zip_folder, max_workers=8, use_tdel=True, use_trash=True):
    """处理目录中的所有图片文件"""
    folder_stats = init_folder_stats()
    image_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.avif', '.jxl')
    
    # 获取所有图片文件，排除 .trash 目录
    image_files = []
    for root, _, files in os.walk(directory_path):
        # 跳过 .trash 目录
        if '.trash' in root:
            continue
            
        for file in files:
            if file.lower().endswith(image_extensions):
                image_files.append(os.path.join(root, file))
    
    if not image_files:
        logger.info("没有找到需要处理的图片文件")
        return
    
    # 创建进度条
    with tqdm(total=len(image_files), desc="处理图片", ncols=100) as pbar:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for image_path in image_files:
                future = executor.submit(
                    process_single_image,
                    image_path,
                    compare_images_hashes,
                    threshold,
                    folder_stats,
                    zip_folder,
                    use_tdel,
                    use_trash
                )
                futures.append(future)
            
            for future in as_completed(futures):
                try:
                    future.result()
                    pbar.update(1)
                except Exception as e:
                    logger.error(f"处理图片时出错: {e}")
    
    print_folder_report(directory_path, folder_stats)

def get_paths_from_clipboard():
    """从剪贴板获取路径列表"""
    try:
        import pyperclip
        text = pyperclip.paste()
        if text:
            return [path.strip().strip('"') for path in text.splitlines() if path.strip()]
    except:
        return []
    return []

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='图片压缩包去重工具')
    parser.add_argument('--clipboard', '-c', 
                       action='store_true',
                       help='从剪贴板读取路径')
    return parser.parse_args()

class ProcessTypeScreen(Screen):
    """处理类型选择界面"""
    
    BINDINGS = [
        Binding("q", "quit", "退出", show=True),
        Binding("enter", "submit", "确认", show=True),
        Binding("escape", "quit", "取消", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="dialog-background"):
            with Container(id="dialog"):
                yield Static("EHV 图片处理工具", id="title", classes="text")
                yield Static("请选择处理模式", classes="text")
                yield RadioSet(
                    RadioButton("🗃️  压缩包处理", value=True),
                    RadioButton("🖼️  图片文件夹处理"),
                    RadioButton("🔄  两者都处理"),
                    id="process_type"
                )
                with Horizontal(classes="button-container"):
                    yield Button("确定", variant="primary", id="confirm")
                    yield Button("取消", variant="error", id="cancel")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self._confirm_selection()
        elif event.button.id == "cancel":
            self.app.exit(None)
            
    def _confirm_selection(self) -> None:
        radio_set = self.query_one("#process_type")
        selected_index = radio_set.pressed_index
        self.app.selected_type = str(selected_index + 1)
        self.app.exit(self.app.selected_type)
            
    def action_submit(self) -> None:
        self._confirm_selection()

class ProcessTypeSelector(App):
    """处理类型选择应用"""
    
    THEME = "tokyo-night"
    
    CSS = """
    Screen {
        align: center middle;
    }

    #dialog-background {
        width: 100%;
        height: 100%;
        align: center middle;
    }

    #dialog {
        background: $surface;
        padding: 1 2;
        width: 60;
        height: auto;
        border: tall $primary;
        align: center middle;
    }

    #title {
        text-style: bold;
        margin-bottom: 1;
    }

    .text {
        width: 100%;
        content-align: center middle;
    }

    RadioSet {
        width: 100%;
        margin: 1 0;
    }

    .button-container {
        width: 100%;
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    Button {
        min-width: 16;
        margin: 0 1;
    }

    #confirm {
        border: tall $success;
    }

    #confirm:hover {
        background: $success;
    }

    #cancel {
        border: tall $error;
    }

    #cancel:hover {
        background: $error;
    }
    """
    
    def __init__(self, title: str = ""):
        super().__init__()
        self.title = title
        self.selected_type = None

    def on_mount(self) -> None:
        self.push_screen(ProcessTypeScreen())

def select_process_type(zip_folder):
    """使用 TUI 界面选择处理类型"""
    app = ProcessTypeSelector(f"处理目录: {zip_folder}")
    process_type = app.run()
    return process_type

def main():
    args = parse_arguments()
    directories = []
    
    # 根据命令行参数决定是否使用剪贴板
    if args.clipboard:
        directories = get_paths_from_clipboard()
        process_type = '3'  # 剪贴板模式下默认选择3
    
    # 如果剪贴板为空或未启用剪贴板，则从用户输入读取
    if not directories:
        print("请输入要处理的文件夹或压缩包完整路径，每行一个路径，输入空行结束:")
        while True:
            directory = input().strip().strip('"')
            if not directory:
                break
            directories.append(directory)

    if not directories:
        print("未提供任何路径，程序退出")
        return

    # 处理每个输入的路径
    for zip_folder in directories:
        older_timestamps = record_folder_timestamps(zip_folder)
        compare_folder = 'E:\\1EHV\\[00去图]'
        processed_zips_file = 'E:\\1EHV\\[00去图]\\processed_zips_uuid.yaml'
        hash_file = 'E:\\1EHV\\[00去图]\\image_hashes.json'
        threshold = 12
        enable_processed_zips = True
        exclude_keywords = ["美少女万華鏡", "00去图", "图集","00去图","fanbox","02COS","02杂"]
        max_workers = 14
        update_hashes = True
        ignore_processed_zips = True
        num_start = 2
        num_end = 3
        use_tdel = False  # 不使用.tdel后缀
        use_trash = True  # 使用回收站功能
        
        logger.info(f"处理参数设置: use_tdel={use_tdel}, use_trash={use_trash}")

        compare_images_hashes = load_hashes(hash_file)
        if update_hashes:
            save_hashes(hash_file, compare_images_hashes)

        batch_rename_files()

        processed_zips_set = load_processed_zips_uuid(processed_zips_file) if enable_processed_zips else {}

        if not args.clipboard:  # 非剪贴板模式才显示 TUI 界面
            process_type = select_process_type(zip_folder)
            if process_type is None:  # 用户取消
                continue
        
        if process_type in ('1', '3'):
            process_all_zips(zip_folder, compare_images_hashes, processed_zips_set, processed_zips_file,
                            threshold, enable_processed_zips, exclude_keywords, max_workers,
                            num_start, num_end, ignore_processed_zips, use_tdel, use_trash)
        
        if process_type in ('2', '3'):
            process_directory(zip_folder, compare_images_hashes, threshold, zip_folder, max_workers, use_tdel, use_trash)
        
        restore_folder_timestamps(older_timestamps)

if __name__ == "__main__":
    main()
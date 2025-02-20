from PIL import Image
from charset_normalizer import from_bytes
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from io import BytesIO
from rich.progress import Progress
from rich.progress import track, Progress
from send2trash import send2trash
from threading import Lock
from tqdm import tqdm
import argparse
import cv2
import imagehash
import jaconv
import logging
import numpy as np
import os
import pillow_avif
import pillow_jxl
import pyperclip
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import warnings
import yaml
import zipfile



class Config:
    """
    类描述
    """
    min_size = 631
    white_threshold = 2
    white_score_threshold = 0.96
    similarity_level = 1
    max_workers = min(4, os.cpu_count() or 4)
    use_multithreading = True
    exclude_paths = ['00待分类', '00去图', '单行', '01fanbox画集', '02COS', '汉化', '官方', '中文', '漢化', '掃', '修正', '制', '譯', '个人', '翻', '製', '嵌', '訳', '淫书馆']
    artbook_keywords = []
    handle_artbooks = False
    filter_height_enabled = True
    filter_white_enabled = False
    backup_removed_files_enabled = True
    add_processed_comment_enabled = False
    add_processed_log_enabled = True
    ignore_yaml_log = True
    ignore_processed_log = True
    processed_files_yaml = 'E:\\1EHV\\processed_files.yaml'

class Logger:
    """
    类描述
    """
    @staticmethod
    def generate_summary_report(processed_archives):
        if not processed_archives:
            logger.info('没有处理任何压缩包。')
            return
        common_path_prefix = os.path.commonpath([archive['file_path'] for archive in processed_archives])
        tree_structure = {}
        for archive in processed_archives:
            relative_path = os.path.relpath(archive['file_path'], common_path_prefix)
            path_parts = relative_path.split(os.sep)
            current_level = tree_structure
            for part in path_parts:
                current_level = current_level.setdefault(part, {})
            current_level['_summary'] = f"删除了 {archive['duplicates_removed']} 张重图, {archive['small_images_removed']} 张小图, {archive['white_images_removed']} 张白图, 减少了 {archive['size_reduction_mb']} MB"
        print(f"\n处理摘要 (基于路径前缀 '{common_path_prefix}'):\n")
        Logger.print_tree_structure(tree_structure)

    @staticmethod
    def print_tree_structure(level, indent=''):
        for name, content in level.items():
            if name == '_summary':
                print(f'{indent}{content}')
            else:
                print(f'{indent}├─ {name}')
                Logger.print_tree_structure(content, indent + '│   ')

    @staticmethod
    def log_verbose(message):
        if verbose_logging:
            logger.debug(message)

    @staticmethod
    def print_config(args, max_workers):
        """打印当前配置信息"""
        print('\n=== 当前配置信息 ===')
        print('启用的功能:')
        print(f"  - 小图过滤: {('是' if args.remove_small else '否')}")
        if args.remove_small:
            print(f'    最小尺寸: {args.min_size}x{args.min_size} 像素')
        print(f"  - 黑白图过滤: {('是' if args.remove_grayscale else '否')}")
        if args.remove_grayscale:
            print(f'    白图阈值: {args.white_threshold}')
            print(f'    白图得分阈值: {args.white_score_threshold}')
        print(f"  - 重复图片过滤: {('是' if args.remove_duplicates else '否')}")
        if args.remove_duplicates:
            print(f'    重复判定档位: {args.similarity_level}')
        print(f"  - 合并压缩包处理: {('是' if args.merge_archives else '否')}")
        print(f"  - 直接删除到回收站: {('是' if args.no_trash else '否')}")
        print(f"从剪贴板读取: {('是' if args.clipboard else '否')}")
        print(f'备份文件处理模式: {args.bak_mode}')
        print(f'线程数: {max_workers}')
        print('==================\n')

class PathManager:
    """
    类描述
    """
    @staticmethod
    def create_temp_directory(file_path):
        """
        为每个压缩包创建唯一的临时目录，使用压缩包原名+时间戳
        
        Args:
            file_path: 源文件路径（压缩包路径）
        """
        original_dir = os.path.dirname(file_path)
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        timestamp = int(time.time() * 1000)
        temp_dir = os.path.join(original_dir, f'{file_name}_{timestamp}')
        os.makedirs(temp_dir, exist_ok=True)
        Logger.log_verbose(f'创建临时目录: {temp_dir}')
        return temp_dir

    @staticmethod
    def cleanup_temp_files(temp_dir, new_zip_path, backup_file_path):
        """清理临时文件和目录"""
        try:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                Logger.log_verbose(f'已删除临时目录: {temp_dir}')
            if new_zip_path and os.path.exists(new_zip_path):
                os.remove(new_zip_path)
                Logger.log_verbose(f'已删除临时压缩包: {new_zip_path}')
        except Exception as e:
            logger.error(f'清理临时文件时出错: {e}')

class ImageAnalyzer:
    """
    类描述
    """
    @staticmethod
    def calculate_grayscale_score(image, black_threshold=20, white_threshold=235):
        """
        计算图片的黑白灰度得分，考虑纯黑和纯白区域
        
        Args:
            image: PIL图像对象
            black_threshold: 黑色阈值
            white_threshold: 白色阈值
        Returns:
            float: 黑白得分 (0-1之间，1表示完全黑白)
        """
        image_np = np.array(image.convert('L'))
        black_pixels = np.sum(image_np <= black_threshold)
        white_pixels = np.sum(image_np >= white_threshold)
        total_pixels = image_np.size
        return (black_pixels + white_pixels) / total_pixels if total_pixels > 0 else 0

    @staticmethod
    def is_greyscale(image):
        image_np = np.array(image)
        return len(image_np.shape) == 2 or (np.array_equal(image_np[..., 0], image_np[..., 1]) and np.array_equal(image_np[..., 1], image_np[..., 2]))

    @staticmethod
    def calculate_white_score_fast(image, white_threshold=240):
        image_np = np.array(image.convert('L'))
        white_pixels = np.sum(image_np >= white_threshold)
        total_pixels = image_np.size
        return white_pixels / total_pixels if total_pixels > 0 else 0

class ImageProcessor:
    """
    类描述
    """

    def process_images_in_directory(self, temp_dir, params):
        """处理目录中的图片"""
        try:
            image_files = FileNameHandler.get_image_files(temp_dir)
            if not image_files:
                logger.warning(f'未找到图片文件')
                return (set(), set())
            removed_files = set()
            duplicate_files = set()
            lock = threading.Lock()
            existing_file_names = set()
            with ThreadPoolExecutor(max_workers=params['max_workers']) as executor:
                futures = []
                for file_path in image_files:
                    rel_path = os.path.relpath(file_path, os.path.dirname(file_path))
                    future = executor.submit(self.process_single_image, file_path, rel_path, existing_file_names, params, lock)
                    futures.append((future, file_path))
                image_hashes = []
                for future, file_path in futures:
                    try:
                        img_hash, img_data, rel_path, reason = future.result()
                        if reason in ['small_image', 'white_image']:
                            removed_files.add(file_path)
                        elif img_hash is not None:
                            image_hashes.append((img_hash, img_data, file_path, reason))
                    except Exception as e:
                        logger.error(f'处理图片失败 {file_path}: {e}')
                if params['remove_duplicates'] and image_hashes:
                    unique_images, _ = DuplicateDetector.remove_duplicates_in_memory(image_hashes, params)
                    processed_files = {img[2] for img in unique_images}
                    for img_hash, _, file_path, _ in image_hashes:
                        if file_path not in processed_files:
                            duplicate_files.add(file_path)
            return (removed_files, duplicate_files)
        except Exception as e:
            logger.error(f'处理目录中的图片时出错: {e}')
            return (set(), set())

    def process_single_image(self, file_path, rel_path, existing_file_names, params, lock):
        """处理单个图片文件"""
        try:
            if not file_path or not os.path.exists(file_path):
                logger.error(f'文件不存在: {file_path}')
                return (None, None, None, 'file_not_found')
            try:
                with open(file_path, 'rb') as f:
                    file_data = f.read()
            except Exception as e:
                logger.error(f'读取文件失败 {rel_path}: {e}')
                return (None, None, None, 'read_error')
            if file_path.lower().endswith(('png', 'webp', 'jxl', 'avif', 'jpg', 'jpeg', 'bmp', 'tiff', 'tif', 'heic', 'heif', 'bmp')):
                processed_data, reason = self.process_image_in_memory(file_data, params)
                if processed_data is not None:
                    try:
                        img_hash = imagehash.phash(Image.open(BytesIO(processed_data)))
                        with lock:
                            existing_file_names.add(file_path)
                        return (img_hash, processed_data, file_path, None)
                    except Exception as e:
                        logger.error(f'生成图片哈希失败 {rel_path}: {e}')
                        return (None, processed_data, file_path, 'hash_error')
                else:
                    with lock:
                        existing_file_names.add(file_path)
                    return (None, file_data, file_path, reason)
            else:
                return (None, file_data, file_path, 'non_image_file')
        except Exception as e:
            logger.error(f'处理文件时出错 {rel_path}: {e}')
            return (None, None, None, 'processing_error')

    def process_image_in_memory(self, image_data, params):
        """
        处理内存中的图片数据
        
        Args:
            image_data: 图片二进制数据
            params: 参数字典,包含:
                - min_size: 最小图片尺寸
                - white_threshold: 白色阈值
                - white_score_threshold: 白色得分阈值
                - filter_height_enabled: 是否启用高度过滤
                - filter_white_enabled: 是否启用白色过滤
        """
        try:
            img = Image.open(BytesIO(image_data))
            width, height = img.size
            if params['filter_height_enabled'] and (width < params['min_size'] or height < params['min_size']):
                logger.info(f"图片尺寸过小: {width}x{height} < {params['min_size']}x{params['min_size']}")
                return (None, 'small_image')
            if params['filter_white_enabled']:
                try:
                    white_score = ImageAnalyzer.calculate_grayscale_score(img, black_threshold=20, white_threshold=235)
                    if white_score >= params['white_score_threshold']:
                        logger.info(f'检测到白图: white_score={white_score:.3f}')
                        return (None, 'white_image')
                except Exception as e:
                    logger.error(f'检查白色图片时出错: {e}')
            return (image_data, None)
        except Exception as e:
            logger.error(f'处理图片时出错: {e}')
            return (None, 'processing_error')

class DuplicateDetector:
    """
    类描述
    """
    @staticmethod
    def remove_duplicates_in_memory(image_hashes, params):
        """
        处理重复图片，确保每组相似图片保留文件大小最大的一张（通常质量更好）
        
        Args:
            image_hashes: 图片哈希列表
            params: 参数字典,包含:
                - similarity_level: 相似度级别
        """
        unique_images = []
        removed_count = 0
        skipped_images = {'hash_error': 0, 'small_images': 0, 'white_images': 0}
        processed_indices = set()
        for i, (hash1, img_data1, file_name1, reason) in enumerate(image_hashes):
            if i in processed_indices:
                continue
            if hash1 is None:
                if reason == 'small_image':
                    skipped_images['small_images'] += 1
                elif reason == 'white_image':
                    skipped_images['white_images'] += 1
                else:
                    skipped_images['hash_error'] += 1
                continue
            similar_images = [(i, hash1, img_data1, file_name1)]
            for j, (hash2, img_data2, file_name2, _) in enumerate(image_hashes[i + 1:], start=i + 1):
                if hash2 is not None and abs(hash1 - hash2) <= params['similarity_level']:
                    similar_images.append((j, hash2, img_data2, file_name2))
            if len(similar_images) > 1:
                image_sizes = []
                for idx, _, img_data, file_name in similar_images:
                    file_size = len(img_data)
                    image_sizes.append((file_size, idx, img_data, file_name))
                image_sizes.sort(reverse=True)
                kept_idx = image_sizes[0][1]
                kept_image = similar_images[similar_images.index(next((x for x in similar_images if x[0] == kept_idx)))]
                unique_images.append((image_hashes[kept_idx][0], image_hashes[kept_idx][1], image_hashes[kept_idx][2]))
                processed_indices.add(kept_idx)
                for size, idx, _, file_name in image_sizes[1:]:
                    processed_indices.add(idx)
                    removed_count += 1
                    Logger.log_verbose(f'Removed duplicate image: {file_name} (duplicate of {kept_image[3]}, file size: {size / 1024:.1f}KB)')
            else:
                unique_images.append((hash1, img_data1, file_name1))
                processed_indices.add(i)
        logger.info(f'Total duplicates removed: {removed_count}')
        logger.info(f"Total small images removed: {skipped_images['small_images']}")
        logger.info(f"Total white images removed: {skipped_images['white_images']}")
        logger.info(f"Total hash errors skipped: {skipped_images['hash_error']}")
        return (unique_images, skipped_images)

class FileNameHandler:
    """
    类描述
    """
    @staticmethod
    def get_image_files(directory):
        """获取目录中的所有图片文件"""
        image_files = []
        for root, _, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.jxl', '.avif', '.bmp')):
                    image_files.append(os.path.join(root, file))
        return image_files

    @staticmethod
    def try_decoding_with_multiple_encodings(file_name):
        encodings_to_try = ['utf-8', 'shift_jis', 'gbk', 'big5', 'euc-jp', 'iso-8859-1']
        for encoding in encodings_to_try:
            try:
                if not file_name:
                    logger.error('Empty file name encountered.')
                    return (file_name, None)
                decoded_name = file_name.encode('cp437').decode(encoding)
                return (decoded_name, encoding)
            except Exception as e:
                continue
        return FileNameHandler.decode_japanese_filename(file_name)

    @staticmethod
    def decode_japanese_filename(file_name):
        try:
            if not file_name:
                logger.error('Empty file name encountered.')
                return (file_name, None)
            decoded_name = jaconv.h2z(file_name)
            decoded_name = jaconv.kata2hira(decoded_name)
            return (decoded_name, 'utf-8')
        except Exception as e:
            logger.error(f'Error decoding file name with jaconv: {e}')
            return (file_name, None)

class DirectoryHandler:
    """
    类描述
    """
    @staticmethod
    def remove_empty_directories(path, exclude_keywords=[]):
        """
        删除指定路径下的所有空文件夹
        
        Args:
            path (str): 目标路径
            exclude_keywords (list): 排除关键词列表
        """
        removed_count = 0
        for root, dirs, _ in os.walk(path, topdown=False):
            if any((keyword in root for keyword in exclude_keywords)):
                continue
            for dir_name in dirs:
                folder_path = os.path.join(root, dir_name)
                try:
                    if not os.listdir(folder_path):
                        os.rmdir(folder_path)
                        removed_count += 1
                        Logger.log_verbose(f'已删除空文件夹: {folder_path}')
                except Exception as e:
                    logger.error(f'删除空文件夹失败 {folder_path}: {e}')
        if removed_count > 0:
            logger.info(f'共删除 {removed_count} 个空文件夹')
        return removed_count

    @staticmethod
    def restore_files(backup_dir):
        for root, _, files in os.walk(backup_dir):
            for file in tqdm(files, desc='Restoring files', unit='file'):
                if file.endswith('.bak'):
                    original_file = file[:-4]
                    backup_file_path = os.path.join(root, file)
                    restore_path = os.path.join(root, original_file)
                    try:
                        shutil.copy(backup_file_path, restore_path)
                        Logger.log_verbose(f'已恢复文件: {restore_path} 来自备份文件: {backup_file_path}')
                    except Exception as e:
                        logger.error(f'恢复文件出错: {backup_file_path} - 错误: {e}')

    @staticmethod
    def remove_files(file_paths):
        """删除指定的文件列表"""
        removed_count = 0
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    removed_count += 1
                    Logger.log_verbose(f'已删除文件: {file_path}')
            except Exception as e:
                logger.error(f'删除文件失败 {file_path}: {e}')
        return removed_count

    @staticmethod
    def flatten_single_subfolder(path, exclude_keywords=[]):
        """
        如果一个文件夹下只有一个文件夹，就将该文件夹的子文件夹释放掉
        
        Args:
            path (str): 目标路径
            exclude_keywords (list): 排除关键词列表
        """
        flattened_count = 0
        for root, dirs, files in os.walk(path):
            if any((keyword in root for keyword in exclude_keywords)):
                continue
            if len(dirs) == 1 and (not files):
                subfolder_path = os.path.join(root, dirs[0])
                try:
                    while True:
                        sub_items = os.listdir(subfolder_path)
                        sub_dirs = [item for item in sub_items if os.path.isdir(os.path.join(subfolder_path, item))]
                        sub_files = [item for item in sub_items if os.path.isfile(os.path.join(subfolder_path, item))]
                        if len(sub_dirs) == 1 and (not sub_files):
                            subfolder_path = os.path.join(subfolder_path, sub_dirs[0])
                            continue
                        break
                    for item in os.listdir(subfolder_path):
                        src_path = os.path.join(subfolder_path, item)
                        dst_path = os.path.join(root, item)
                        if os.path.exists(dst_path):
                            base_name, ext = os.path.splitext(item)
                            counter = 1
                            while os.path.exists(dst_path):
                                dst_path = os.path.join(root, f'{base_name}_{counter}{ext}')
                                counter += 1
                        try:
                            shutil.move(src_path, dst_path)
                            Logger.log_verbose(f'已移动: {src_path} -> {dst_path}')
                        except Exception as e:
                            logger.error(f'移动文件失败 {src_path}: {e}')
                            continue
                    shutil.rmtree(subfolder_path)
                    flattened_count += 1
                    Logger.log_verbose(f'已删除文件夹: {subfolder_path}')
                except Exception as e:
                    logger.error(f'处理子文件夹失败 {subfolder_path}: {e}')
        if flattened_count > 0:
            logger.info(f'共释放 {flattened_count} 个单层文件夹')
        return flattened_count

class ArchiveExtractor:
    """
    类描述
    """
    @staticmethod
    def extract_file_from_zip(zip_path, file_name, temp_dir):
        """压缩包中取单个文件"""
        extract_path = os.path.join(temp_dir, file_name)
        success, _ = ArchiveCompressor.run_7z_command('e', zip_path, '提取文件', [f'-o{temp_dir}', file_name, '-y'])
        if success and os.path.exists(extract_path):
            with open(extract_path, 'rb') as f:
                data = f.read()
            os.remove(extract_path)
            return data
        return None

    @staticmethod
    def read_zip_contents(zip_path):
        """读取压缩包中的文件列表"""
        try:
            cmd = ['7z', 'l', '-slt', zip_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f'读取压缩包失败: {zip_path}\n错误: {result.stderr}')
                return []
            files = []
            current_file = None
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line.startswith('Path = '):
                    current_file = line[7:]
                    if current_file and (not current_file.endswith('/')):
                        files.append(current_file)
            Logger.log_verbose(f'Found {len(files)} files in archive: {zip_path}')
            return files
        except Exception as e:
            logger.error(f'读取压缩包内容时出错 {zip_path}: {e}')
            return []

    @staticmethod
    def prepare_archive(file_path):
        """准备压缩包处理环境"""
        temp_dir = PathManager.create_temp_directory(file_path)
        backup_file_path = file_path + '.bak'
        new_zip_path = os.path.join(os.path.dirname(file_path), f'{os.path.splitext(os.path.basename(file_path))[0]}.new.zip')
        try:
            shutil.copy(file_path, backup_file_path)
            Logger.log_verbose(f'创建备份: {backup_file_path}')
            cmd = ['7z', 'x', file_path, f'-o{temp_dir}', '-y']
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f'解压失败: {file_path}\n错误: {result.stderr}')
                PathManager.cleanup_temp_files(temp_dir, new_zip_path, backup_file_path)
                return (None, None, None)
            return (temp_dir, backup_file_path, new_zip_path)
        except Exception as e:
            logger.error(f'准备环境失败 {file_path}: {e}')
            PathManager.cleanup_temp_files(temp_dir, new_zip_path, backup_file_path)
            return (None, None, None)

class ArchiveCompressor:
    """
    类描述
    """
    @staticmethod
    def run_7z_command(command, zip_path, operation='', additional_args=None):
        """
        执7z命令的通函数
        
        Args:
            command: 主命令 (如 'a', 'x', 'l' 等)
            zip_path: 压缩包路径
            operation: 操作描述（用于日志）
            additional_args: 额外的命令行参数
        """
        try:
            cmd = ['7z', command, zip_path]
            if additional_args:
                cmd.extend(additional_args)
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                Logger.log_verbose(f'成功执行7z {operation}: {zip_path}')
                return (True, result.stdout)
            else:
                logger.error(f'7z {operation}失败: {zip_path}\n错误: {result.stderr}')
                return (False, result.stderr)
        except Exception as e:
            logger.error(f'执行7z命令出错: {e}')
            return (False, str(e))

    @staticmethod
    def create_new_zip(zip_path, temp_dir):
        """
        从临时目录创建新的压缩包
        
        Args:
            zip_path: 新压缩包的路径
            temp_dir: 临时目录路径
        """
        try:
            if not any(os.scandir(temp_dir)):
                logger.error(f'临时目录为空: {temp_dir}')
                return False
            cmd = ['7z', 'a', '-tzip', zip_path, os.path.join(temp_dir, '*')]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                if not os.path.exists(zip_path):
                    logger.error(f'压缩包创建失败: {zip_path}')
                    return False
                logger.info(f'成功创建新压缩包: {zip_path} ({os.path.getsize(zip_path) / 1024 / 1024:.2f} MB)')
                return True
            else:
                logger.error(f'创建压缩包失败: {result.stderr}')
                return False
        except Exception as e:
            logger.error(f'创建压缩包时出错: {e}')
            return False

    @staticmethod
    def create_new_archive(temp_dir, new_zip_path):
        """创建新的压缩包"""
        cmd = ['7z', 'a', '-tzip', new_zip_path, os.path.join(temp_dir, '*')]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0

class ArchiveProcessor:
    """
    类描述
    """
    @staticmethod
    def merge_archives(paths, params):
        """
        合并压缩包为一个临时压缩包进行处理
        
        Args:
            paths: 压缩包路径列表或文件夹路径列表
            params: 参数字典
        
        Returns:
            (temp_dir, merged_zip_path, archive_paths): 临时目录、合并后的压缩包路径和原始压缩包路径列表
        """
        temp_dir = None
        try:
            archive_paths = []
            for path in paths:
                if os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        archive_paths.extend((os.path.join(root, file) for file in files if file.lower().endswith('.zip')))
                elif path.lower().endswith('.zip'):
                    archive_paths.append(path)
            if not archive_paths:
                logger.error('没有找到要处理的压缩包')
                return (None, None, None)
            directories = {os.path.dirname(path) for path in archive_paths}
            if len(directories) > 1:
                logger.error('所选压缩包不在同一目录')
                return (None, None, None)
            base_dir = list(directories)[0]
            timestamp = int(time.time() * 1000)
            temp_dir = os.path.join(base_dir, f'temp_merge_{timestamp}')
            os.makedirs(temp_dir, exist_ok=True)
            for zip_path in archive_paths:
                logger.info(f'解压: {zip_path}')
                archive_name = os.path.splitext(os.path.basename(zip_path))[0]
                archive_temp_dir = os.path.join(temp_dir, archive_name)
                os.makedirs(archive_temp_dir, exist_ok=True)
                success, error = ArchiveCompressor.run_7z_command('x', zip_path, '解压文件', [f'-o{archive_temp_dir}', '-y'])
                if not success:
                    logger.error(f'解压失败: {zip_path}\n错误: {error}')
                    PathManager.cleanup_temp_files(temp_dir, None, None)
                    return (None, None, None)
            merged_zip_path = os.path.join(base_dir, f'merged_{timestamp}.zip')
            logger.info('创建合并压缩包')
            success, error = ArchiveCompressor.run_7z_command('a', merged_zip_path, '创建合并压缩包', ['-tzip', os.path.join(temp_dir, '*')])
            if not success:
                logger.error(f'创建合并压缩包失败: {error}')
                PathManager.cleanup_temp_files(temp_dir, None, None)
                return (None, None, None)
            return (temp_dir, merged_zip_path, archive_paths)
        except Exception as e:
            logger.error(f'合并压缩包时出错: {e}')
            if temp_dir and os.path.exists(temp_dir):
                PathManager.cleanup_temp_files(temp_dir, None, None)
            return (None, None, None)

    @staticmethod
    def process_single_archive(file_path, params):
        """处理单个压缩包文件"""
        try:
            logger.debug(f'开始处理文件: {file_path}')
            logger.debug(f'文件是否存在: {os.path.exists(file_path)}')
            if not os.path.exists(file_path):
                logger.error(f'文件不存在: {file_path}')
                return []
            cmd = ['7z', 'l', file_path]
            result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                logger.error(f'压缩包可能损坏: {file_path}')
                return []
            if result.stdout is None:
                logger.error(f'无法读取压缩包内容: {file_path}')
                return []
            has_images = any((line.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.jxl', '.avif', '.jxl')) for line in result.stdout.splitlines()))
            if not has_images:
                logger.info(f'跳过无图片的压缩包: {file_path}')
                return []
            processed_archives = []
            if not params['ignore_yaml_log'] and file_path in params['processed_files_set']:
                logger.debug(f'文件在YAML记录中已存在: {file_path}')
                return processed_archives
            if not params['ignore_processed_log']:
                logger.debug(f'检查processed.log: {file_path}')
                if ProcessedLogHandler.has_processed_log(file_path):
                    logger.debug(f'文件已有处理记录: {file_path}')
                    return processed_archives
            logger.debug(f'开始处理压缩包内容: {file_path}')
            processed_archives.extend(ArchiveProcessor.process_archive_in_memory(file_path, params))
            if params['add_processed_comment_enabled']:
                logger.debug(f'添加处理注释: {file_path}')
                Utils.add_processed_comment(file_path)
            if params['add_processed_log_enabled'] and processed_archives:
                logger.debug(f'添加处理日志: {file_path}')
                processed_info = {'duplicates_removed': processed_archives[-1]['duplicates_removed'], 'small_images_removed': processed_archives[-1]['small_images_removed'], 'white_images_removed': processed_archives[-1]['white_images_removed']}
                ProcessedLogHandler.add_processed_log(file_path, processed_info)
            backup_file_path = file_path + '.bak'
            if os.path.exists(backup_file_path):
                BackupHandler.handle_bak_file(backup_file_path, params)
            return processed_archives
        except UnicodeDecodeError as e:
            logger.error(f'处理压缩包时出现编码错误 {file_path}: {e}')
            return []
        except Exception as e:
            logger.exception(f'处理文件时发生异常: {file_path}')
            return []

    @staticmethod
    def split_merged_archive(processed_zip, original_archives, temp_dir, params):
        """
        将处理后的合并压缩包拆分回原始压缩包
        
        Args:
            processed_zip: 处理后的合并压缩包路径
            original_archives: 原始压缩包路径列表
            temp_dir: 临时目录路径
            params: 参数字典
        """
        try:
            logger.info('开始拆分处理后的压缩包')
            extract_dir = os.path.join(temp_dir, 'processed')
            os.makedirs(extract_dir, exist_ok=True)
            success, error = ArchiveCompressor.run_7z_command('x', processed_zip, '解压处理后的压缩包', [f'-o{extract_dir}', '-y'])
            if not success:
                logger.error(f'解压处理后的压缩包失败: {error}')
                return False
            for original_zip in original_archives:
                archive_name = os.path.splitext(os.path.basename(original_zip))[0]
                source_dir = os.path.join(extract_dir, archive_name)
                if not os.path.exists(source_dir):
                    logger.warning(f'找不到对应的目录: {source_dir}')
                    continue
                new_zip = original_zip + '.new'
                success, error = ArchiveCompressor.run_7z_command('a', new_zip, '创建新压缩包', ['-tzip', os.path.join(source_dir, '*')])
                if success:
                    try:
                        if params.get('backup_removed_files_enabled', True):
                            send2trash(original_zip)
                        else:
                            os.remove(original_zip)
                        os.rename(new_zip, original_zip)
                        logger.info(f'成功更新压缩包: {original_zip}')
                    except Exception as e:
                        logger.error(f'替换压缩包失败 {original_zip}: {e}')
                else:
                    logger.error(f'创建新压缩包失败 {new_zip}: {error}')
            return True
        except Exception as e:
            logger.error(f'拆分压缩包时出错: {e}')
            return False

    @staticmethod
    def handle_size_comparison(file_path, new_zip_path, backup_file_path):
        """
        比较新旧文件大小并处理替换
        
        Args:
            file_path: 原始文件路径
            new_zip_path: 新压缩包路径
            backup_file_path: 备份文件路径
        
        Returns:
            (success, size_change): 处理是否成功和文件大小变化(MB)
        """
        try:
            if not os.path.exists(new_zip_path):
                logger.error(f'新压缩包不存在: {new_zip_path}')
                return (False, 0)
            original_size = os.path.getsize(file_path)
            new_size = os.path.getsize(new_zip_path)
            REDUNDANCY_SIZE = 1 * 1024 * 1024
            if new_size >= original_size + REDUNDANCY_SIZE:
                logger.warning(f'新压缩包 ({new_size / 1024 / 1024:.2f}MB) 未比原始文件 ({original_size / 1024 / 1024:.2f}MB) 小超过1MB，还原备份')
                os.remove(new_zip_path)
                if os.path.exists(backup_file_path):
                    os.replace(backup_file_path, file_path)
                return (False, 0)
            os.replace(new_zip_path, file_path)
            size_change = (original_size - new_size) / (1024 * 1024)
            logger.info(f'更新压缩包: {file_path} (减少 {size_change:.2f}MB)')
            return (True, size_change)
        except Exception as e:
            logger.error(f'比较文件大小时出错: {e}')
            if os.path.exists(backup_file_path):
                os.replace(backup_file_path, file_path)
            if os.path.exists(new_zip_path):
                os.remove(new_zip_path)
            return (False, 0)

    @staticmethod
    def process_archive_in_memory(file_path, params):
        """处理单个压缩包的主函数"""
        processed_archives = []
        temp_dir = None
        backup_file_path = None
        new_zip_path = None
        try:
            temp_dir, backup_file_path, new_zip_path = ArchiveExtractor.prepare_archive(file_path)
            if not temp_dir:
                logger.error(f'准备环境失败: {file_path}')
                return []
            image_files = FileNameHandler.get_image_files(temp_dir)
            if not image_files:
                logger.warning(f'未找到图片文件')
                PathManager.cleanup_temp_files(temp_dir, new_zip_path, backup_file_path)
                return []
            removed_files = set()
            duplicate_files = set()
            lock = threading.Lock()
            existing_file_names = set()
            image_processor = ImageProcessor()
            with ThreadPoolExecutor(max_workers=params['max_workers']) as executor:
                futures = []
                for img_path in image_files:
                    rel_path = os.path.relpath(img_path, temp_dir)
                    future = executor.submit(image_processor.process_single_image, img_path, rel_path, existing_file_names, params, lock)
                    futures.append((future, img_path))
                image_hashes = []
                for future, img_path in futures:
                    try:
                        img_hash, img_data, _, reason = future.result()
                        if reason in ['small_image', 'white_image']:
                            removed_files.add(img_path)
                        elif img_hash is not None and params['remove_duplicates']:
                            image_hashes.append((img_hash, img_data, img_path, reason))
                    except Exception as e:
                        logger.error(f'处理图片失败 {img_path}: {e}')
                if params['remove_duplicates'] and image_hashes:
                    unique_images, _ = DuplicateDetector.remove_duplicates_in_memory(image_hashes, params)
                    processed_files = {img[2] for img in unique_images}
                    for img_hash, _, img_path, _ in image_hashes:
                        if img_path not in processed_files:
                            duplicate_files.add(img_path)
            if not ArchiveProcessor.cleanup_and_compress(temp_dir, removed_files, duplicate_files, new_zip_path, params):
                logger.error(f'清理和压缩失败: {file_path}')
                if os.path.exists(backup_file_path):
                    os.replace(backup_file_path, file_path)
                return []
            if not os.path.exists(new_zip_path):
                logger.error(f'新压缩包不存在: {new_zip_path}')
                if os.path.exists(backup_file_path):
                    os.replace(backup_file_path, file_path)
                return []
            original_size = os.path.getsize(file_path)
            new_size = os.path.getsize(new_zip_path)
            REDUNDANCY_SIZE = 1 * 1024 * 1024
            if new_size >= original_size + REDUNDANCY_SIZE:
                logger.warning(f'新压缩包 ({new_size / 1024 / 1024:.2f}MB) 不小于原始文件 ({original_size / 1024 / 1024:.2f}MB)，还原备份')
                os.remove(new_zip_path)
                if os.path.exists(backup_file_path):
                    os.replace(backup_file_path, file_path)
                return []
            os.replace(new_zip_path, file_path)
            if os.path.exists(backup_file_path):
                os.remove(backup_file_path)
            result = {'file_path': file_path, 'duplicates_removed': len(duplicate_files), 'small_images_removed': len(removed_files - duplicate_files), 'white_images_removed': 0, 'size_reduction_mb': (original_size - new_size) / (1024 * 1024)}
            processed_archives.append(result)
        except Exception as e:
            logger.error(f'处理压缩包时出错 {file_path}: {e}')
            if backup_file_path and os.path.exists(backup_file_path):
                os.replace(backup_file_path, file_path)
            return []
        finally:
            PathManager.cleanup_temp_files(temp_dir, new_zip_path, backup_file_path)
        return processed_archives

    @staticmethod
    def cleanup_and_compress(temp_dir, removed_files, duplicate_files, new_zip_path, params):
        """清理文件并创建新压缩包"""
        try:
            if removed_files is None:
                removed_files = set()
            if duplicate_files is None:
                duplicate_files = set()
            if not isinstance(removed_files, set) or not isinstance(duplicate_files, set):
                logger.error(f'无效的参数类型: removed_files={type(removed_files)}, duplicate_files={type(duplicate_files)}')
                return False
            BackupHandler.backup_removed_files(new_zip_path, removed_files, duplicate_files, params)
            all_files_to_remove = removed_files | duplicate_files
            removed_count = 0
            for file_path in all_files_to_remove:
                try:
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                        removed_count += 1
                        Logger.log_verbose(f'已删除文件: {file_path}')
                except Exception as e:
                    logger.error(f'删除文件失败 {file_path}: {e}')
                    continue
            if removed_count > 0:
                logger.info(f'已删除 {removed_count} 个文件')
            empty_dirs_removed = DirectoryHandler.remove_empty_directories(temp_dir)
            if empty_dirs_removed > 0:
                logger.info(f'已删除 {empty_dirs_removed} 个空文件夹')
            if not os.path.exists(temp_dir) or not any(os.scandir(temp_dir)):
                logger.info(f'临时目录为空或不存在: {temp_dir}')
                temp_empty_file = os.path.join(temp_dir, '.empty')
                os.makedirs(temp_dir, exist_ok=True)
                with open(temp_empty_file, 'w') as f:
                    pass
                success, error = ArchiveCompressor.run_7z_command('a', new_zip_path, '创建空压缩包', ['-tzip', temp_empty_file])
                os.remove(temp_empty_file)
                if success and os.path.exists(new_zip_path):
                    logger.info(f'成功创建空压缩包: {new_zip_path}')
                    return True
                else:
                    logger.error(f'创建空压缩包失败: {error}')
                    return False
            success, error = ArchiveCompressor.run_7z_command('a', new_zip_path, '创建新压缩包', ['-tzip', os.path.join(temp_dir, '*')])
            if success:
                if not os.path.exists(new_zip_path):
                    logger.error(f'压缩包创建失败: {new_zip_path}')
                    return False
                logger.info(f'成功创建新压缩包: {new_zip_path}')
                return True
            else:
                logger.error(f'创建压缩包失败: {error}')
                return False
        except Exception as e:
            logger.error(f'清理和压缩时出错: {e}')
            return False

class ProcessedLogHandler:
    """
    类描述
    """
    @staticmethod
    def has_processed_log(zip_path):
        command = ['7z', 'l', zip_path]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            if 'processed.log' in result.stdout:
                processed_files = ProcessedLogHandler.load_processed_files()
                if zip_path not in processed_files:
                    ProcessedLogHandler.save_processed_file(zip_path)
                return True
        else:
            logger.error(f'Failed to list contents of {zip_path}: {result.stderr}')
        return False

    @staticmethod
    def add_processed_log(zip_path, processed_info):
        try:
            log_file_path = os.path.join(os.path.dirname(zip_path), 'processed.log')
            with open(log_file_path, 'a', encoding='utf-8') as log_file:
                log_file.write(f'{os.path.basename(zip_path)} - 处理时间: {datetime.now()} - 处理情况:\n')
                log_file.write(f" - 删除的重图数量: {processed_info['duplicates_removed']}\n")
                log_file.write(f" - 小图数量: {processed_info['small_images_removed']}\n")
                log_file.write(f" - 白图数量: {processed_info['white_images_removed']}\n")
            logger.info(f'Added log entry to {log_file_path}')
            command = ['7z', 'a', log_file_path, log_file_path]
            result = subprocess.run(command, capture_output=True, text=True)
            os.remove(log_file_path)
            if result.returncode == 0:
                logger.info(f'Successfully added {log_file_path} to {zip_path}')
            else:
                logger.error(f'Failed to add log to {zip_path}: {result.stderr}')
        except Exception as e:
            logger.error(f'Error adding log to {zip_path}: {e}')

    @staticmethod
    def save_processed_file(zip_path):
        processed_files = ProcessedLogHandler.load_processed_files()
        if zip_path not in processed_files:
            processed_files.add(zip_path)
            with open(processed_files_yaml, 'w', encoding='utf-8') as file:
                yaml.dump(list(processed_files), file, allow_unicode=True)

    @staticmethod
    def load_processed_files():
        """从 YAML 文件加载已处理的文件路径。"""
        if os.path.exists(processed_files_yaml):
            with open(processed_files_yaml, 'r', encoding='utf-8') as file:
                return set(yaml.safe_load(file) or [])
        return set()

class BackupHandler:
    """
    类描述
    """
    @staticmethod
    def restore_bak_files(restore_path):
        """恢复指定路径下的所有bak文件"""
        restored_count = 0
        try:
            if not os.path.exists(restore_path):
                logger.error(f'恢复路径不存在: {restore_path}')
                return 0
            for root, _, files in os.walk(restore_path):
                for file in files:
                    if file.endswith('.bak'):
                        bak_path = os.path.join(root, file)
                        original_path = bak_path[:-4]
                        try:
                            shutil.copy2(bak_path, original_path)
                            logger.info(f'已恢复文件: {original_path}')
                            restored_count += 1
                        except Exception as e:
                            logger.error(f'恢复文件失败 {bak_path}: {e}')
            logger.info(f'共恢复了 {restored_count} 个文件')
            return restored_count
        except Exception as e:
            logger.error(f'恢复bak文件时出错: {e}')
            return 0

    @staticmethod
    def delete_backup_if_successful(backup_path):
        if os.path.exists(backup_path) and backup_path.endswith('.bak'):
            try:
                logger.info(f'Sending backup to recycle bin: {backup_path}')
                send2trash(backup_path)
            except Exception as e:
                logger.error(f'Error sending backup to recycle bin: {backup_path} - {e}')

    @staticmethod
    def handle_bak_file(bak_path, params):
        """
        根据指定模式处理bak文件
        
        Args:
            bak_path: 备份文件路径
            params: 参数字典，包含:
                - bak_mode: 备份文件处理模式 ('keep', 'recycle', 'delete')
                - backup_removed_files_enabled: 是否使用回收站
        """
        try:
            mode = params.get('bak_mode', 'keep')
            if mode == 'keep':
                logger.debug(f'保留备份文件: {bak_path}')
                return
            if not os.path.exists(bak_path):
                logger.debug(f'备份文件不存在: {bak_path}')
                return
            if mode == 'recycle' or params.get('backup_removed_files_enabled', True):
                try:
                    send2trash(bak_path)
                    logger.info(f'已将备份文件移至回收站: {bak_path}')
                except Exception as e:
                    logger.error(f'移动备份文件到回收站失败 {bak_path}: {e}')
            elif mode == 'delete':
                try:
                    os.remove(bak_path)
                    logger.info(f'已删除备份文件: {bak_path}')
                except Exception as e:
                    logger.error(f'删除备份文件失败 {bak_path}: {e}')
        except Exception as e:
            logger.error(f'处理备份文件时出错 {bak_path}: {e}')

    @staticmethod
    def backup_removed_files(zip_path, removed_files, duplicate_files, params):
        """
        将删除的文件备份到trash文件夹中，保持原始目录结构
        
        Args:
            zip_path: 原始压缩包路径
            removed_files: 被删除的小图/白图文件集合
            duplicate_files: 被删除的重复图片文件集合
            params: 参数字典，包含:
                - backup_removed_files_enabled: 是否备份删除的文件
        """
        try:
            if not params.get('backup_removed_files_enabled', True):
                logger.debug('跳过备份删除的文件')
                return
            if not removed_files and (not duplicate_files):
                return
            zip_name = os.path.splitext(os.path.basename(zip_path))[0]
            trash_dir = os.path.join(os.path.dirname(zip_path), f'{zip_name}.trash')
            os.makedirs(trash_dir, exist_ok=True)
            if removed_files:
                BackupHandler.backup_files_to_dir(removed_files, trash_dir, 'removed', os.path.dirname(zip_path))
            if duplicate_files:
                BackupHandler.backup_files_to_dir(duplicate_files, trash_dir, 'duplicates', os.path.dirname(zip_path))
            logger.info(f'已备份删除的文件到: {trash_dir}')
        except Exception as e:
            logger.error(f'备份删除文件时出错: {e}')

    @staticmethod
    def backup_files_to_dir(files, trash_dir, subdir, base_path):
        """
        将文件备份到指定目录
        
        Args:
            files: 要备份的文件集合
            trash_dir: trash目录路径
            subdir: 子目录名称
            base_path: 基准路径，用于计算相对路径
        """
        for file_path in files:
            try:
                rel_path = os.path.relpath(file_path, base_path)
                dest_path = os.path.join(trash_dir, subdir, rel_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(file_path, dest_path)
            except Exception as e:
                logger.error(f'备份文件失败 {file_path}: {e}')
                continue

class ContentFilter:
    """
    类描述
    """
    @staticmethod
    def is_artbook(file_path, artbook_keywords):
        file_name = os.path.basename(file_path).lower()
        return any((keyword.lower() in file_name or keyword.lower() in file_path.lower() for keyword in artbook_keywords))

    @staticmethod
    def should_process_file(file_path, params):
        """判断文件是否需要处理"""
        logger.debug(f'\n开始检查文件是否需要处理: {file_path}')
        if params['exclude_paths']:
            for exclude_path in params['exclude_paths']:
                if exclude_path in file_path:
                    logger.debug(f'文件在排除路径中 (排除关键词: {exclude_path})')
                    return False
        logger.debug('文件通过所有检查，将进行处理')
        return True

class ProgressHandler:
    """
    处理进度显示的类
    """
    def __init__(self, progress, task):
        self.progress = progress
        self.task = task
        self.processed_count = 0
        self.total_count = 0

    def increment(self):
        self.processed_count += 1
        self.progress.update(self.task, description=f'Processing Archives ({self.processed_count}/{self.total_count})')
        self.progress.advance(self.task)

    def set_total(self, total):
        self.total_count = total

class Application:
    """
    类描述
    """

    def main(self):
        """主函数"""
        args = InputHandler.parse_arguments()
        Logger.print_config(args, max_workers)
        if not InputHandler.validate_args(args):
            sys.exit(1)
        if args.restore_bak:
            ProcessManager.handle_restore_mode(args)
            return
        directories = InputHandler.get_input_paths(args.clipboard)
        if not directories:
            logger.error('未提供任何输入路径')
            return
        if args.merge_archives:
            ProcessManager.process_merged_archives(directories, args)
        else:
            ProcessManager.process_normal_archives(directories, args)
        logger.info('Processing completed.')

class InputHandler:
    """
    类描述
    """
    @staticmethod
    def parse_arguments():
        """解析命令行参数"""
        parser = argparse.ArgumentParser(description='图片压缩包去重工具')
        feature_group = parser.add_argument_group('功能开关')
        feature_group.add_argument('--remove-small', '-rs', action='store_true', help='启用小图过滤')
        feature_group.add_argument('--remove-grayscale', '-rg', action='store_true', help='启用黑白图过滤')
        feature_group.add_argument('--remove-duplicates', '-rd', action='store_true', help='启用重复图片过滤')
        feature_group.add_argument('--merge-archives', '-ma', action='store_true', help='合并同一文件夹下的多个压缩包进行处理')
        feature_group.add_argument('--no-trash', '-nt', action='store_true', help='不保留trash文件夹，直接删除到回收站')
        small_group = parser.add_argument_group('小图过滤参数')
        small_group.add_argument('--min-size', '-ms', type=int, default=631, help='最小图片尺寸（宽度和高度），默认为631')
        grayscale_group = parser.add_argument_group('黑白图过滤参数')
        grayscale_group.add_argument('--white-threshold', '-wt', type=int, default=2, help='白图阈值，默认为2')
        grayscale_group.add_argument('--white-score-threshold', '-ws', type=float, default=0.96, help='白图得分阈值，默认为0.96')
        duplicate_group = parser.add_argument_group('重复图片过滤参数')
        duplicate_group.add_argument('--similarity-level', '-sl', type=int, choices=[1, 2, 3, 4, 5], default=1, help='重复图片判定档位，数值越大越宽松：\n                                  1 = 严格 (几乎完全相同)\n                                  2 = 标准 (轻微差异容许)\n                                  3 = 宽松 (允许一定差异)\n                                  4 = 很宽松 (允许较大差异)\n                                  5 = 最宽松 (允许显著差异)')
        parser.add_argument('--clipboard', '-c', action='store_true', help='从剪贴板读取路径')
        parser.add_argument('--bak-mode', '-bm', choices=['recycle', 'delete', 'keep'], default='keep', help='bak文件处理模式：recycle=移到回收站，delete=直接删除，keep=保留（默认）')
        parser.add_argument('--restore-bak', '-rb', action='store_true', help='恢复bak文件（将覆盖同名文件）')
        parser.add_argument('--restore-path', '-rp', type=str, help='指定要恢复bak文件的路径')
        return parser.parse_args()

    @staticmethod
    def validate_args(args):
        """验证参数是否有效"""
        if not any([args.remove_small, args.remove_grayscale, args.remove_duplicates]):
            print('警告: 未启用任何过滤功能，将不会对图片进行处理')
            if not args.restore_bak:
                print('请使用 -rs, -rg, -rd 参数启用相应的过滤功能')
                return False
        return True

    @staticmethod
    def prepare_params(args):
        """
        统一准备参数字典
        
        Args:
            args: 命令行参数对象
            
        Returns:
            dict: 包含所有处理参数的字典
        """
        return {
            'min_size': args.min_size,
            'white_threshold': args.white_threshold,
            'white_score_threshold': args.white_score_threshold,
            'similarity_level': args.similarity_level,
            'filter_height_enabled': args.remove_small,
            'filter_white_enabled': args.remove_grayscale,
            'handle_artbooks': handle_artbooks,
            'artbook_keywords': artbook_keywords or ['画集', 'fanbox', 'ex-hentai', 'twitter', 'PATREON', 'pixiv', 'fantia', '作品集', '图集'],
            'exclude_paths': exclude_paths,
            'processed_files_set': ProcessedLogHandler.load_processed_files(),
            'ignore_processed_log': ignore_processed_log,
            'add_processed_comment_enabled': add_processed_comment_enabled,
            'add_processed_log_enabled': add_processed_log_enabled,
            'ignore_yaml_log': ignore_yaml_log,
            'use_multithreading': use_multithreading,
            'max_workers': max_workers,
            'bak_mode': args.bak_mode,
            'remove_duplicates': args.remove_duplicates,
            'backup_removed_files_enabled': not args.no_trash
        }

    @staticmethod
    def get_input_paths(use_clipboard):
        """获取输入路径"""
        directories = []
        if use_clipboard:
            directories = InputHandler.get_paths_from_clipboard()
        if not directories:
            print('请输入要处理的文件夹或压缩包完整路径，每行一个路径，输入空行结束:')
            while True:
                directory = input().strip().strip('"')
                if not directory:
                    break
                directories.append(directory)
        return directories

    @staticmethod
    def get_paths_from_clipboard():
        """从剪贴板读取多行路径"""
        try:
            clipboard_content = pyperclip.paste()
            if not clipboard_content:
                return []
            paths = [path.strip().strip('"') for path in clipboard_content.splitlines() if path.strip()]
            valid_paths = [path for path in paths if os.path.exists(path)]
            if valid_paths:
                logger.info(f'从剪贴板读取到 {len(valid_paths)} 个有效路径')
            else:
                logger.warning('剪贴板中没有有效路径')
            return valid_paths
        except ImportError:
            logger.error('未安装 pyperclip 模块，无法读取剪贴板')
            return []
        except Exception as e:
            logger.error(f'读取剪贴板时出错: {e}')
            return []

class ProcessManager:
    """
    类描述
    """
    @staticmethod
    def handle_restore_mode(args):
        """处理恢复模式"""
        restore_path = args.restore_path
        if not restore_path and args.clipboard:
            directories = InputHandler.get_paths_from_clipboard()
            if directories:
                restore_path = directories[0]
        if not restore_path:
            restore_path = input('请输入要恢复bak文件的路径: ').strip().strip('"')
        if restore_path:
            restored_count = BackupHandler.restore_bak_files(restore_path)
            if restored_count > 0:
                print(f'\n成功恢复了 {restored_count} 个文件')
            else:
                print('\n未恢复任何文件')

    @staticmethod
    def process_normal_archives(directories, args):
        """处理普通模式的压缩包或目录"""
        for directory in directories:
            if os.path.exists(directory):
                params = InputHandler.prepare_params(args)
                ProcessManager.process_all_archives([directory], params)
                if args.bak_mode != 'keep':
                    for root, _, files in os.walk(directory):
                        for file in files:
                            if file.endswith('.bak'):
                                bak_path = os.path.join(root, file)
                                BackupHandler.handle_bak_file(bak_path, args)
                DirectoryHandler.remove_empty_directories(directory)
            else:
                logger.error(f'输入的路径不存在: {directory}')

    @staticmethod
    def process_merged_archives(directories, args):
        """处理合并模式的压缩包"""
        temp_dir, merged_zip, archive_paths = ArchiveProcessor.merge_archives(directories, args)
        if temp_dir and merged_zip:
            try:
                params = InputHandler.prepare_params(args)
                ProcessManager.process_all_archives([merged_zip], params)
                if ArchiveProcessor.split_merged_archive(merged_zip, archive_paths, temp_dir, params):
                    logger.info('成功完成压缩包的合并处理和拆分')
                else:
                    logger.error('拆分压缩包失败')
            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                if os.path.exists(merged_zip):
                    os.remove(merged_zip)

    @staticmethod
    def process_all_archives(directories, params):
        """
        主处理函数
        
        Args:
            directories: 要处理的目录列表
            params: 参数字典，包含所有必要的处理参数:
                - min_size: 最小图片尺寸
                - white_threshold: 白图阈值
                - white_score_threshold: 白图得分阈值
                - similarity_level: 相似度级别
                - filter_height_enabled: 是否启用高度过滤
                - filter_white_enabled: 是否启用白图过滤
                - max_workers: 最大线程数
                - handle_artbooks: 是否处理画集
                - artbook_keywords: 画集关键词列表
                - exclude_paths: 排除路径列表
                - ignore_processed_log: 是否忽略处理日志
                - ignore_yaml_log: 是否忽略YAML日志
                - use_multithreading: 是否使用多线程
                - bak_mode: 备份文件处理模式
                - remove_duplicates: 是否去除重复
                - backup_removed_files_enabled: 是否备份删除的文件
        """
        processed_archives = []
        logger.info('开始处理拖入的目录或文件')
        total_zip_files = sum((1 for directory in directories for root, _, files in os.walk(directory) for file in files if file.lower().endswith('zip')))
        with Progress() as progress:
            task = progress.add_task('Processing Archives', total=total_zip_files)
            progress_handler = ProgressHandler(progress, task)
            Utils.progress = progress
            Utils.task = task
            Utils.processed_count = 0
            Utils.set_total(total_zip_files)
            for directory in directories:
                archives = ProcessManager.process_directory(directory, params, progress_handler)
                processed_archives.extend(archives)
        Logger.generate_summary_report(processed_archives)
        logger.info('所有目录处理完成')
        return processed_archives

    @staticmethod
    def process_directory(directory, params, progress_handler):
        """处理单个目录"""
        try:
            logger.info(f'\n开始处理目录: {directory}')
            processed_archives = []
            if os.path.isfile(directory):
                logger.info(f'处理单个文件: {directory}')
                if directory.lower().endswith('zip'):
                    if ContentFilter.should_process_file(directory, params):
                        logger.info(f'开始处理压缩包: {directory}')
                        archives = ProcessManager.process_single_archive(directory, params)
                        processed_archives.extend(archives)
                    else:
                        logger.info(f'跳过文件（根据过滤规则）: {directory}')
                    Utils.increment()
                else:
                    logger.info(f'跳过非zip文件: {directory}')
            elif os.path.isdir(directory):
                logger.info(f'扫描目录中的文件: {directory}')
                files_to_process = []
                for root, _, files in os.walk(directory):
                    logger.debug(f'扫描子目录: {root}')
                    for file in files:
                        if file.lower().endswith('zip'):
                            file_path = os.path.join(root, file)
                            logger.debug(f'发现zip文件: {file_path}')
                            if ContentFilter.should_process_file(file_path, params):
                                logger.info(f'添加到处理列表: {file_path}')
                                files_to_process.append(file_path)
                            else:
                                logger.info(f'跳过文件（根据过滤规则）: {file_path}')
                                Utils.increment()
                logger.info(f'扫描完成: 找到 {len(files_to_process)} 个要处理的文件')
                for file_path in files_to_process:
                    try:
                        logger.info(f'\n正在处理压缩包: {file_path}')
                        archives = ProcessManager.process_single_archive(file_path, params)
                        if archives:
                            logger.info(f'成功处理压缩包: {file_path}')
                        else:
                            logger.info(f'压缩包处理完成，但没有变化: {file_path}')
                        processed_archives.extend(archives)
                    except Exception as e:
                        logger.error(f'处理压缩包出错: {file_path}\n错误: {e}')
                    finally:
                        Utils.increment()
            if os.path.isdir(directory):
                exclude_keywords = params.get('exclude_paths', [])
            return processed_archives
        except Exception as e:
            logger.exception(f'处理目录时发生异常: {directory}')
            return []

    @staticmethod
    def process_single_archive(file_path, params):
        """处理单个压缩包文件"""
        try:
            logger.debug(f'开始处理文件: {file_path}')
            logger.debug(f'文件是否存在: {os.path.exists(file_path)}')
            if not os.path.exists(file_path):
                logger.error(f'文件不存在: {file_path}')
                return []
            cmd = ['7z', 'l', file_path]
            result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                logger.error(f'压缩包可能损坏: {file_path}')
                return []
            if result.stdout is None:
                logger.error(f'无法读取压缩包内容: {file_path}')
                return []
            has_images = any((line.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.jxl', '.avif', '.jxl')) for line in result.stdout.splitlines()))
            if not has_images:
                logger.info(f'跳过无图片的压缩包: {file_path}')
                return []
            processed_archives = []
            if not params['ignore_yaml_log'] and file_path in params['processed_files_set']:
                logger.debug(f'文件在YAML记录中已存在: {file_path}')
                return processed_archives
            if not params['ignore_processed_log']:
                logger.debug(f'检查processed.log: {file_path}')
                if ProcessedLogHandler.has_processed_log(file_path):
                    logger.debug(f'文件已有处理记录: {file_path}')
                    return processed_archives
            logger.debug(f'开始处理压缩包内容: {file_path}')
            processed_archives.extend(ArchiveProcessor.process_archive_in_memory(file_path, params))
            if params['add_processed_comment_enabled']:
                logger.debug(f'添加处理注释: {file_path}')
                Utils.add_processed_comment(file_path)
            if params['add_processed_log_enabled'] and processed_archives:
                logger.debug(f'添加处理日志: {file_path}')
                processed_info = {'duplicates_removed': processed_archives[-1]['duplicates_removed'], 'small_images_removed': processed_archives[-1]['small_images_removed'], 'white_images_removed': processed_archives[-1]['white_images_removed']}
                ProcessedLogHandler.add_processed_log(file_path, processed_info)
            backup_file_path = file_path + '.bak'
            if os.path.exists(backup_file_path):
                BackupHandler.handle_bak_file(backup_file_path, params)
            return processed_archives
        except UnicodeDecodeError as e:
            logger.error(f'处理压缩包时出现编码错误 {file_path}: {e}')
            return []
        except Exception as e:
            logger.exception(f'处理文件时发生异常: {file_path}')
            return []

class Utils:
    """
    未分类的函数集合
    """
    @staticmethod
    def increment():
        Utils.processed_count += 1
        Utils.progress.update(Utils.task, description=f'Processing Archives ({Utils.processed_count}/{Utils.total_count})')
        Utils.progress.advance(Utils.task)

    @staticmethod
    def add_processed_comment(zip_path, comment='Processed'):
        try:
            with zipfile.ZipFile(zip_path, 'a') as zip_ref:
                zip_ref.comment = comment.encode('utf-8')
            logger.info(f"Added comment '{comment}' to {zip_path}")
        except Exception as e:
            logger.error(f'Error adding comment to {zip_path}: {e}')

    @staticmethod
    def set_total(total):
        Utils.total_count = total

    # 类变量
    progress = None
    task = None
    processed_count = 0
    total_count = 0

# 全局变量和配置
log_file = 'process_log.log'
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)
warnings.filterwarnings('ignore', category=UserWarning, module='zipfile')

# 配置参数
verbose_logging = True
use_direct_path_mode = True
restore_enabled = False
use_multithreading = True
filter_height_enabled = True
filter_white_enabled = False
handle_artbooks = False
add_processed_comment_enabled = False
add_processed_log_enabled = True
ignore_yaml_log = True
ignore_processed_log = True
processed_files_yaml = 'E:\\1EHV\\processed_files.yaml'
artbook_keywords = []
exclude_paths = ['00待分类', '00去图', '单行', '01fanbox画集', '02COS', '汉化', '官方', '中文', '漢化', '掃', '修正', '制', '譯', '个人', '翻', '製', '嵌', '訳', '淫书馆']
min_size = 631
white_threshold = 2
white_score_threshold = 0.96
similarity_level = 1
max_workers = min(4, os.cpu_count() or 4)
backup_removed_files_enabled = True
use_clipboard = False

if __name__ == '__main__':
    app = Application()
    app.main()
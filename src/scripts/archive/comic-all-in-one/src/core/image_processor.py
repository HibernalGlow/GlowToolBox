from PIL import Image
from src.utils.hash_utils import HashUtils
from src.services.logging_service import LoggingService
import logging
from src.utils.hash_utils import HashFileHandler
import os
from src.core.duplicate_detector import DuplicateDetector
from src.utils.hash_utils import ImageHashCalculator
from src.utils.path_utils import PathURIGenerator
from src.utils.archive_utils import ArchiveExtractor
from src.utils.hash_utils import ImageHashCalculator
from src.utils.path_utils import PathURIGenerator
from src.utils.hash_utils import ImageHashCalculator
from src.utils.path_utils import PathURIGenerator
from src.utils.hash_utils import ImageHashCalculator
from src.utils.path_utils import PathURIGenerator
from io import BytesIO
from pics.grayscale_detector import GrayscaleDetector
from concurrent.futures import ThreadPoolExecutor
import threading
from pathlib import Path




class ImageProcessor:
    """
    类描述
    """
    def __init__(self):
        """初始化图片处理器"""
        self.grayscale_detector = GrayscaleDetector()
        self.global_hashes = {}  # 初始化为空字典
        self.temp_hashes = {}  # 临时存储当前压缩包的哈希值

    def set_global_hashes(self, hashes):
        """设置全局哈希缓存"""
        self.global_hashes = hashes

    @staticmethod
    def calculate_phash(image_path_or_data):
        """使用感知哈希算法计算图片哈希值
        
        Args:
            image_path_or_data: 可以是图片路径(str/Path)或BytesIO对象
            
        Returns:
            str: 16进制格式的感知哈希值，失败时返回None
        """
        try:
            hash_value = ImageHashCalculator.calculate_phash(image_path_or_data)
            if isinstance(image_path_or_data, (str, Path)):
                logging.info( f"[#hash_calc]计算图片哈希值: {os.path.basename(str(image_path_or_data))} -> {hash_value}")
            return hash_value
        except Exception as e:
            logging.info(f"[#hash_calc]计算图片哈希值失败: {e}")
            return None

    def process_images_in_directory(self, temp_dir, params):
        """处理目录中的图片"""
        try:
            # 清空临时哈希存储
            self.temp_hashes.clear()
            
            image_files = ArchiveExtractor.get_image_files(temp_dir)
            if not image_files:
                logging.info( f"⚠️ 未找到图片文件")
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
                        logging.info( f"❌ 处理图片失败 {file_path}: {e}")
            if params['remove_duplicates'] and image_hashes:
                unique_images, _, removal_reasons = DuplicateDetector.remove_duplicates_in_memory(image_hashes, params)
                processed_files = {img[2] for img in unique_images}
                for img_hash, _, file_path, _ in image_hashes:
                    if file_path not in processed_files:
                        duplicate_files.add(file_path)
                        
                # # 处理完成后，将临时哈希更新到全局哈希
                # if self.temp_hashes:
                #     with lock:
                #         self.global_hashes.update(self.temp_hashes)
                #         logging.info(f"[#hash_calc]已批量添加 {len(self.temp_hashes)} 个哈希到全局缓存")
                #         # 清空临时存储
                #         self.temp_hashes.clear()
                        
            return (removed_files, duplicate_files)
        except Exception as e:
            logging.info( f"❌ 处理目录中的图片时出错: {e}")
            return (set(), set())

    def process_single_image(self, file_path, rel_path, existing_file_names, params, lock): 
        """处理单个图片文件"""
        try:
            if not file_path or not os.path.exists(file_path):
                logging.info(f"[#file_ops]❌ 文件不存在: {file_path}")
                return (None, None, None, 'file_not_found')
                            
            try:
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                    logging.info(f"[#file_ops]📷读图: {file_path}")  # 添加面板标识
            except (IOError, OSError) as e:
                logging.info(f"[#file_ops]❌ 图片文件损坏或无法读取 {rel_path}: {e}")
                return (None, None, None, 'corrupted_image')
            except Exception as e:
                logging.info(f"[#file_ops]❌ 读取文件失败 {rel_path}: {e}")
                return (None, None, None, 'read_error')
                
            if file_path.lower().endswith(('png', 'webp', 'jxl', 'avif', 'jpg', 'jpeg', 'bmp', 'tiff', 'tif', 'heic', 'heif', 'bmp')):
                # === 独立处理步骤 ===
                processed_data = file_data
                removal_reason = None

                # 步骤1: 小图检测 (独立判断)
                if params.get('filter_height_enabled', False):
                    logging.info(f"[#image_processing]🖼️ 正在检测小图: {os.path.basename(file_path)}")
                    processed_data, removal_reason = self.detect_small_image(processed_data, params)
                    if removal_reason:
                        return (None, file_data, file_path, removal_reason)

                # 步骤2: 白图检测 (独立判断)
                if params.get('remove_grayscale', False):
                    logging.info(f"[#image_processing]🎨 正在检测白图: {os.path.basename(file_path)}")
                    processed_data, removal_reason = self.detect_grayscale_image(processed_data)
                    if removal_reason:
                        return (None, file_data, file_path, removal_reason)

                # 步骤3: 重复检测 - 直接计算哈希,不检查全局匹配
                if params.get('remove_duplicates', False):
                    img_hash = self.handle_duplicate_detection(file_path, rel_path, params, lock, processed_data)
                    if not img_hash:
                        return (None, file_data, file_path, 'hash_error')
                    return (img_hash, file_data, file_path, None)

                return (None, file_data, file_path, None)
            else:
                return (None, file_data, file_path, 'non_image_file')
        except Exception as e:
            logging.info(f"[#file_ops]❌ 处理文件时出错 {rel_path}: {e}")
            return (None, None, None, 'processing_error')

       # 修改后的独立小图检测方法
    def detect_small_image(self, image_data, params):
        """独立的小图检测"""
        try:
            # 如果是PIL图像对象，先转换为字节数据
            if isinstance(image_data, Image.Image):
                img_byte_arr = BytesIO()
                image_data.save(img_byte_arr, format=image_data.format)
                img_data = img_byte_arr.getvalue()
            else:
                img_data = image_data
                
            img = Image.open(BytesIO(img_data))
            width, height = img.size
            if height < params.get('min_size', 631):
                return None, 'small_image'
            return img_data, None
        except Exception as e:
            return None, 'size_detection_error'

    def detect_grayscale_image(self, image_data):
        """独立的白图检测"""
        white_keywords = ['pure_white', 'white', 'pure_black', 'grayscale']
        try:
            result = self.grayscale_detector.analyze_image(image_data)
            if result is None:
                logging.info( f"灰度分析返回None")
                return (None, 'grayscale_detection_error')
                
            # 详细记录分析结果
            # logging.info( f"灰度分析结果: {result}")
            
            if hasattr(result, 'removal_reason') and result.removal_reason:
                logging.info( f"检测到移除原因: {result.removal_reason}")
                
                # 检查是否匹配任何关键字
                matched_keywords = [keyword for keyword in white_keywords 
                                  if keyword in result.removal_reason]
                if matched_keywords:
                    logging.info( f"匹配到白图关键字: {matched_keywords}")
                    return (None, 'white_image')
                    
                # 如果有removal_reason但不匹配关键字，记录这种情况
                logging.info( f"未匹配关键字的移除原因: {result.removal_reason}")
                return (None, result.removal_reason)
                
            return (image_data, None)
            
        except ValueError as ve:
            logging.info( f"灰度检测发生ValueError: {str(ve)}")
            return (None, 'grayscale_detection_error')
        except Exception as e:
            logging.info( f"灰度检测发生错误: {str(e)}")
            return None, 'grayscale_detection_error'

    def handle_duplicate_detection(self, file_path, rel_path, params, lock, image_data):
        """处理重复检测 - 只计算哈希"""
        try:
            # 计算新的哈希值
            img_hash = ImageHashCalculator.calculate_phash(image_data)
            if img_hash:
                # 获取压缩包路径并构建URI
                zip_path = params.get('zip_path')
                if zip_path:
                    img_uri = PathURIGenerator.generate(f"{zip_path}!{rel_path}")
                    # 添加哈希操作面板标识
                    logging.info(f"[#hash_calc]计算哈希值: {img_uri} -> {img_hash['hash']}")  
            return img_hash
            
        except Exception as e:
            # 错误日志也指向哈希操作面板
            logging.info(f"[#hash_calc]❌ 计算哈希值失败: {str(e)}")  
            return None

import os
import logging
from typing import List, Set, Dict, Tuple
from .calculate_hash_custom import ImageHashCalculator, PathURIGenerator
from .watermark_detector import WatermarkDetector
from PIL import Image
from io import BytesIO
import json

logger = logging.getLogger(__name__)

class ImageFilter:
    """图片过滤器，支持多种独立的过滤功能"""
    
    def __init__(self, hash_file: str = None, cover_count: int = 3, hamming_threshold: int = 12, ref_hamming_threshold: int = None):
        """
        初始化过滤器
        
        Args:
            hash_file: 哈希文件路径
            cover_count: 处理的封面图片数量
            hamming_threshold: 汉明距离阈值
            ref_hamming_threshold: 哈希文件过滤的汉明距离阈值，默认使用hamming_threshold
        """
        self.hash_file = hash_file
        self.cover_count = cover_count
        self.hamming_threshold = hamming_threshold
        self.ref_hamming_threshold = ref_hamming_threshold if ref_hamming_threshold is not None else hamming_threshold
        self.hash_cache = self._load_hash_file()
        self.watermark_detector = WatermarkDetector()
        
    def _load_hash_file(self) -> Dict:
        """加载哈希文件"""
        try:
            if os.path.exists(self.hash_file):
                with open(self.hash_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"成功加载哈希文件: {self.hash_file}")
                return data.get('hashes', {})
            else:
                logger.error(f"哈希文件不存在: {self.hash_file}")
                return {}
        except Exception as e:
            logger.error(f"加载哈希文件失败: {e}")
            return {}

    def _process_small_images(self, cover_files: List[str], min_size: int) -> Tuple[Set[str], Dict[str, Dict]]:
        """处理小图过滤"""
        to_delete = set()
        removal_reasons = {}
        
        small_images = self._filter_small_images(cover_files, min_size)
        for img in small_images:
            to_delete.add(img)
            removal_reasons[img] = {
                'reason': 'small_image',
                'details': f'小于{min_size}像素'
            }
            logger.info(f"标记删除小图: {os.path.basename(img)}")
            
        return to_delete, removal_reasons
        
    def _process_grayscale_images(self, cover_files: List[str]) -> Tuple[Set[str], Dict[str, Dict]]:
        """处理黑白图过滤"""
        to_delete = set()
        removal_reasons = {}
        
        grayscale_images = self._filter_grayscale_images(cover_files)
        for img in grayscale_images:
            to_delete.add(img)
            removal_reasons[img] = {
                'reason': 'grayscale',
                'details': '黑白图片'
            }
            logger.info(f"标记删除黑白图片: {os.path.basename(img)}")
            
        return to_delete, removal_reasons
        
    def _process_watermark_images(self, group: List[str], watermark_keywords: List[str] = None) -> Tuple[Set[str], Dict[str, Dict]]:
        """处理水印过滤"""
        to_delete = set()
        removal_reasons = {}
        
        deleted_files = self._apply_watermark_filter(group, watermark_keywords)
        for img, texts in deleted_files:
            to_delete.add(img)
            removal_reasons[img] = {
                'reason': 'watermark',
                'watermark_texts': texts,
                'matched_keywords': [kw for kw in (watermark_keywords or []) if any(kw in text for text in texts)]
            }
            logger.info(f"标记删除有水印图片: {os.path.basename(img)}")
            
        return to_delete, removal_reasons
        
    def _process_quality_images(self, group: List[str]) -> Tuple[Set[str], Dict[str, Dict]]:
        """处理质量过滤"""
        to_delete = set()
        removal_reasons = {}
        
        deleted_files = self._apply_quality_filter(group)
        for img, size_diff in deleted_files:
            to_delete.add(img)
            removal_reasons[img] = {
                'reason': 'quality',
                'size_diff': size_diff
            }
            logger.info(f"标记删除较小图片: {os.path.basename(img)}")
            
        return to_delete, removal_reasons

    def process_images(
        self, 
        image_files: List[str],
        enable_small_filter: bool = None,
        enable_grayscale_filter: bool = None,
        enable_duplicate_filter: bool = None,
        min_size: int = 631,
        duplicate_filter_mode: str = 'quality',  # 'quality' or 'watermark'
        watermark_keywords: List[str] = None,  # 水印关键词列表
        ref_hamming_threshold: int = None,  # 哈希文件过滤的汉明距离阈值
        **kwargs
    ) -> Tuple[Set[str], Dict[str, Dict]]:
        """
        处理图片列表，支持多种独立的过滤功能
        
        Args:
            image_files: 图片文件路径列表
            enable_small_filter: 是否启用小图过滤
            enable_grayscale_filter: 是否启用黑白图过滤
            enable_duplicate_filter: 是否启用重复图片过滤
            min_size: 最小图片尺寸
            duplicate_filter_mode: 重复图片过滤模式 ('quality' 或 'watermark')
            watermark_keywords: 水印关键词列表，None时使用默认列表
            ref_hamming_threshold: 哈希文件过滤的汉明距离阈值，None时使用初始化时的值
            **kwargs: 其他可扩展的参数
            
        Returns:
            Tuple[Set[str], Dict[str, Dict]]: (要删除的文件集合, 删除原因字典)
        """
        logger.info("[#cur_progress]开始分析图片质量...")
        sorted_files = sorted(image_files)
        cover_files = sorted_files[:self.cover_count]
        
        if not cover_files:
            return set(), {}
            
        logger.info(f"处理前{self.cover_count}张图片")
        
        to_delete = set()
        removal_reasons = {}
        
        # 1. 小图过滤
        if enable_small_filter:
            small_to_delete, small_reasons = self._process_small_images(cover_files, min_size)
            to_delete.update(small_to_delete)
            removal_reasons.update(small_reasons)
        
        # 2. 黑白图过滤
        if enable_grayscale_filter:
            gray_to_delete, gray_reasons = self._process_grayscale_images(cover_files)
            # 避免重复添加
            gray_to_delete = {img for img in gray_to_delete if img not in to_delete}
            to_delete.update(gray_to_delete)
            removal_reasons.update({k: v for k, v in gray_reasons.items() if k in gray_to_delete})
        
        # 3. 重复图片过滤
        if enable_duplicate_filter:
            # 获取未被其他过滤器删除的文件
            remaining_files = [f for f in cover_files if f not in to_delete]
            if remaining_files:
                similar_groups = self._find_similar_images(remaining_files)
                
                for group in similar_groups:
                    if len(group) <= 1:
                        continue
                        
                    if duplicate_filter_mode == 'watermark':
                        # 水印过滤模式
                        watermark_to_delete, watermark_reasons = self._process_watermark_images(group, watermark_keywords)
                        to_delete.update(watermark_to_delete)
                        removal_reasons.update(watermark_reasons)
                    else:
                        # 质量过滤模式（默认）
                        quality_to_delete, quality_reasons = self._process_quality_images(group)
                        to_delete.update(quality_to_delete)
                        removal_reasons.update(quality_reasons)
        
        return to_delete, removal_reasons

    def _filter_small_images(self, images: List[str], min_size: int) -> Set[str]:
        """小图过滤"""
        small_images = set()
        for img_path in images:
            try:
                with Image.open(img_path) as img:
                    width, height = img.size
                    if width < min_size or height < min_size:
                        small_images.add(img_path)
                        logger.info(f"发现小图: {os.path.basename(img_path)} ({width}x{height})")
            except Exception as e:
                logger.error(f"检查图片尺寸失败 {img_path}: {e}")
        return small_images

    def _filter_grayscale_images(self, images: List[str]) -> Set[str]:
        """黑白图过滤"""
        grayscale_images = set()
        for img_path in images:
            try:
                with Image.open(img_path) as img:
                    if img.mode == "L":  # 直接是灰度图
                        grayscale_images.add(img_path)
                        continue
                    if img.mode in ["RGB", "RGBA"]:
                        rgb_img = img.convert("RGB")
                        pixels = list(rgb_img.getdata())
                        if all(p[0] == p[1] == p[2] for p in pixels):
                            grayscale_images.add(img_path)
                            logger.info(f"发现黑白图片: {os.path.basename(img_path)}")
            except Exception as e:
                logger.error(f"检查黑白图片失败 {img_path}: {e}")
        return grayscale_images

    def _find_similar_images(self, images: List[str]) -> List[List[str]]:
        """查找相似的图片组"""
        similar_groups = []
        processed = set()
        
        for i, img1 in enumerate(images):
            if img1 in processed:
                continue
                
            hash1 = self._get_image_hash(img1)
            if not hash1:  # 跳过无效哈希
                logger.warning(f"跳过无效哈希的图片: {os.path.basename(img1)}")
                continue
                
            current_group = [img1]
            
            for j, img2 in enumerate(images[i+1:], i+1):
                if img2 in processed:
                    continue
                    
                hash2 = self._get_image_hash(img2)
                if not hash2:  # 跳过无效哈希
                    logger.warning(f"跳过无效哈希的图片: {os.path.basename(img2)}")
                    continue
                    
                try:
                    distance = ImageHashCalculator.calculate_hamming_distance(hash1, hash2)
                    if distance <= self.hamming_threshold:
                        current_group.append(img2)
                        logger.info(f"找到相似图片: {os.path.basename(img2)} (距离: {distance})")
                except Exception as e:
                    logger.error(f"计算汉明距离失败 {img1} vs {img2}: {str(e)}")
                    continue
                    
            if len(current_group) > 1:
                similar_groups.append(current_group)
                processed.update(current_group)
                logger.info(f"找到相似图片组: {len(current_group)}张")
                
        return similar_groups

    def _get_image_hash(self, image_path: str) -> str:
        """获取图片哈希值，优先从缓存读取"""
        try:
            # 增加路径有效性检查
            if not os.path.exists(image_path):
                logger.error(f"图片路径不存在: {image_path}")
                return None
            
            image_uri = PathURIGenerator.generate(image_path)
            if not image_uri:  # 处理生成URI失败的情况
                logger.error(f"生成图片URI失败: {image_path}")
                return None

            # 增加缓存键存在性检查
            if image_uri in self.hash_cache:
                hash_data = self.hash_cache[image_uri]
                # 处理不同的缓存数据结构
                if isinstance(hash_data, dict):
                    return hash_data.get('hash')
                return str(hash_data)  # 兼容旧版本字符串格式

            # 计算新哈希
            hash_value = ImageHashCalculator.calculate_phash(image_path)
            if not hash_value:
                logger.error(f"计算图片哈希失败: {image_path}")
                return None

            # 更新缓存
            self.hash_cache[image_uri] = {'hash': hash_value}
            return hash_value
        
        except Exception as e:
            logger.error(f"获取图片哈希异常 {image_path}: {str(e)}")
            return None

    def _apply_watermark_filter(self, group: List[str], watermark_keywords: List[str] = None) -> List[Tuple[str, List[str]]]:
        """
        应用水印过滤，返回要删除的图片和水印文字
        
        Args:
            group: 相似图片组
            watermark_keywords: 水印关键词列表，None时使用默认列表
        """
        to_delete = []
        watermark_results = {}
        
        # 检测每张图片的水印
        for img_path in group:
            has_watermark, texts = self.watermark_detector.detect_watermark(img_path, watermark_keywords)
            watermark_results[img_path] = (has_watermark, texts)
            if has_watermark:
                logger.info(f"发现水印: {os.path.basename(img_path)} -> {texts}")
            
        # 找出无水印的图片
        clean_images = [img for img, (has_mark, _) in watermark_results.items() if not has_mark]
        
        if clean_images:
            # 如果有无水印图片，保留其中最大的一张
            keep_image = max(clean_images, key=lambda x: os.path.getsize(x))
            # 删除其他有水印的图片
            for img in group:
                if img != keep_image and watermark_results[img][0]:
                    to_delete.append((img, watermark_results[img][1]))
                    
        return to_delete

    def _apply_quality_filter(self, group: List[str]) -> List[Tuple[str, str]]:
        """应用质量过滤（基于文件大小），返回要删除的图片和大小差异"""
        to_delete = []
        # 获取文件大小
        file_sizes = {img: os.path.getsize(img) for img in group}
        # 保留最大的文件
        keep_image = max(group, key=lambda x: file_sizes[x])
        
        # 删除其他较小的文件
        for img in group:
            if img != keep_image:
                size_diff = f"{file_sizes[keep_image] - file_sizes[img]} bytes"
                to_delete.append((img, size_diff))
                
        return to_delete
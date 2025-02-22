import os
import logging
from typing import List, Set, Dict, Tuple
from .calculate_hash_custom import ImageHashCalculator, PathURIGenerator
from .watermark_detector import WatermarkDetector
import json

logger = logging.getLogger(__name__)

class ImageFilter:
    """图片过滤器"""
    
    def __init__(self, hash_file: str = None, cover_count: int = 3, hamming_threshold: int = 12):
        """
        初始化过滤器
        
        Args:
            hash_file: 哈希文件路径
            cover_count: 处理的封面图片数量
            hamming_threshold: 汉明距离阈值
        """
        self.hash_file = hash_file
        self.cover_count = cover_count
        self.hamming_threshold = hamming_threshold
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
            
    def _get_image_hash(self, image_path: str) -> str:
        """获取图片哈希值，优先从缓存读取"""
        image_uri = PathURIGenerator.generate(image_path)
        
        if image_uri in self.hash_cache:
            hash_data = self.hash_cache[image_uri]
            return hash_data.get('hash') if isinstance(hash_data, dict) else hash_data
            
        try:
            hash_value = ImageHashCalculator.calculate_phash(image_path)
            if hash_value:
                self.hash_cache[image_uri] = {'hash': hash_value}
                return hash_value
        except Exception as e:
            logger.error(f"计算图片哈希值失败 {image_path}: {e}")
            
        return None
        
    def find_similar_images(self, image_files: List[str]) -> List[List[str]]:
        """
        查找相似的图片组
        
        Args:
            image_files: 图片文件路径列表
            
        Returns:
            List[List[str]]: 相似图片组列表
        """
        similar_groups = []
        processed = set()
        
        for i, img1 in enumerate(image_files):
            if img1 in processed:
                continue
                
            hash1 = self._get_image_hash(img1)
            if not hash1:
                continue
                
            current_group = [img1]
            
            for j, img2 in enumerate(image_files[i+1:], i+1):
                if img2 in processed:
                    continue
                    
                hash2 = self._get_image_hash(img2)
                if not hash2:
                    continue
                    
                distance = ImageHashCalculator.calculate_hamming_distance(hash1, hash2)
                if distance <= self.hamming_threshold:
                    current_group.append(img2)
                    logger.info(f"找到相似图片: {os.path.basename(img2)} (距离: {distance})")
                    
            if len(current_group) > 1:
                similar_groups.append(current_group)
                processed.update(current_group)
                logger.info(f"找到相似图片组: {len(current_group)}张")
                
        return similar_groups
        
    def process_images(self, image_files: List[str]) -> Tuple[Set[str], Dict[str, Dict]]:
        """
        处理图片列表，返回要删除的图片和删除原因
        
        Args:
            image_files: 图片文件路径列表
            
        Returns:
            Tuple[Set[str], Dict[str, Dict]]: (要删除的文件集合, 删除原因字典)
        """
        sorted_files = sorted(image_files)
        cover_files = sorted_files[:self.cover_count]
        
        if not cover_files:
            return set(), {}
            
        logger.info(f"处理前{self.cover_count}张图片")
        similar_groups = self.find_similar_images(cover_files)
        
        to_delete = set()
        removal_reasons = {}
        
        for group in similar_groups:
            watermark_results = {}
            for img_path in group:
                has_watermark, texts = self.watermark_detector.detect_watermark(img_path)
                watermark_results[img_path] = (has_watermark, texts)
                logger.info(f"图片 {os.path.basename(img_path)} OCR结果: {texts}")
            
            clean_images = [img for img, (has_mark, _) in watermark_results.items() 
                          if not has_mark]
            
            if clean_images:
                keep_image = clean_images[0]
                logger.info(f"保留无水印图片: {os.path.basename(keep_image)}")
                for img in group:
                    if img != keep_image:
                        to_delete.add(img)
                        removal_reasons[img] = {
                            'reason': 'recruit_cover',
                            'watermark_texts': watermark_results[img][1]
                        }
                        logger.info(f"标记删除有水印图片: {os.path.basename(img)}")
            else:
                keep_image = group[0]
                logger.info(f"保留第一张图片: {os.path.basename(keep_image)}")
                for img in group[1:]:
                    to_delete.add(img)
                    removal_reasons[img] = {
                        'reason': 'recruit_cover',
                        'watermark_texts': watermark_results[img][1]
                    }
                    logger.info(f"标记删除重复图片: {os.path.basename(img)}")
        
        return to_delete, removal_reasons 
from pathlib import Path
import sys
import os
import json
import logging
from typing import List, Dict, Set, Tuple

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from nodes.pics.calculate_hash_custom import ImageHashCalculator, PathURIGenerator
from nodes.pics.watermark_detector import WatermarkDetector

logger = logging.getLogger(__name__)

class RecruitCoverFilter:
    """封面图片过滤器"""
    
    def __init__(self, hash_file: str, cover_count: int = 3, hamming_threshold: int = 12):
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
                return data
            else:
                logger.error(f"哈希文件不存在: {self.hash_file}")
                return {}
        except Exception as e:
            logger.error(f"加载哈希文件失败: {e}")
            return {}
            
    def _get_image_hash(self, image_path: str) -> str:
        """获取图片哈希值，优先从缓存读取"""
        image_uri = PathURIGenerator.generate(image_path)
        
        # 从缓存中查找
        if image_uri in self.hash_cache:
            return self.hash_cache[image_uri]
            
        # 计算新的哈希值
        try:
            hash_value = ImageHashCalculator.calculate_phash(image_path)
            if hash_value:
                self.hash_cache[image_uri] = hash_value
                return hash_value
        except Exception as e:
            logger.error(f"计算图片哈希值失败 {image_path}: {e}")
            
        return None
        
    def _find_similar_images(self, image_files: List[str]) -> List[List[str]]:
        """查找相似的图片组"""
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
                    
                # 计算汉明距离
                distance = ImageHashCalculator.calculate_hamming_distance(hash1, hash2)
                if distance <= self.hamming_threshold:
                    current_group.append(img2)
                    
            if len(current_group) > 1:
                similar_groups.append(current_group)
                processed.update(current_group)
                
        return similar_groups
        
    def process_images(self, image_files: List[str]) -> Tuple[Set[str], Dict[str, List[str]]]:
        """
        处理图片列表，返回要删除的图片和删除原因
        
        Args:
            image_files: 图片文件路径列表
            
        Returns:
            Tuple[Set[str], Dict[str, List[str]]]: (要删除的文件集合, 删除原因字典)
        """
        # 排序并只取前N张
        sorted_files = sorted(image_files)
        cover_files = sorted_files[:self.cover_count]
        
        if not cover_files:
            return set(), {}
            
        # 查找相似图片组
        similar_groups = self._find_similar_images(cover_files)
        
        # 处理每组相似图片
        to_delete = set()
        removal_reasons = {}
        
        for group in similar_groups:
            # 检测每张图片的水印
            watermark_results = {}
            for img_path in group:
                has_watermark, texts = self.watermark_detector.detect_watermark(img_path)
                watermark_results[img_path] = (has_watermark, texts)
            
            # 找出无水印的图片
            clean_images = [img for img, (has_mark, _) in watermark_results.items() 
                          if not has_mark]
            
            if clean_images:
                # 如果有无水印版本，删除其他版本
                keep_image = clean_images[0]
                for img in group:
                    if img != keep_image:
                        to_delete.add(img)
                        removal_reasons[img] = {
                            'reason': 'recruit_cover',
                            'watermark_texts': watermark_results[img][1]
                        }
            else:
                # 如果都有水印，保留第一个
                keep_image = group[0]
                for img in group[1:]:
                    to_delete.add(img)
                    removal_reasons[img] = {
                        'reason': 'recruit_cover',
                        'watermark_texts': watermark_results[img][1]
                    }
        
        return to_delete, removal_reasons 
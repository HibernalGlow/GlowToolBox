from pathlib import Path
import imagehash
from PIL import Image
from typing import Dict, List, Set, Tuple
from .base_filter import BaseImageFilter

class DuplicateImageFilter(BaseImageFilter):
    """重复图片过滤器"""
    
    def __init__(self, params: Dict):
        super().__init__(params)
        self.hash_cache = {}  # 存储图片哈希值
        self.reference_hashes = {}  # 存储参考哈希值
        
    def get_filter_description(self) -> str:
        return (f"重复图片过滤器 "
                f"(内部汉明距离: {self.params.get('hamming_distance', 0)}, "
                f"参考汉明距离: {self.params.get('ref_hamming_distance', 12)})")
    
    def load_reference_hashes(self, hash_file: str) -> None:
        """
        加载参考哈希文件
        
        Args:
            hash_file: 哈希文件路径
        """
        if not hash_file:
            return
            
        try:
            import json
            with open(hash_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 支持新旧两种格式
            hashes_data = data.get('hashes', {}) or data.get('results', {})
            
            for uri, info in hashes_data.items():
                if isinstance(info, dict):
                    hash_str = str(info.get('hash') or info.get('hash_value', '')).lower()
                elif isinstance(info, str):
                    hash_str = info.lower()
                else:
                    continue
                    
                if hash_str:
                    self.reference_hashes[hash_str] = uri
                    
        except Exception as e:
            print(f"加载哈希文件失败: {e}")
    
    def calculate_image_hash(self, image_path: Path) -> str:
        """
        计算图片的感知哈希值
        
        Args:
            image_path: 图片路径
            
        Returns:
            str: 哈希值
        """
        try:
            with Image.open(image_path) as img:
                hash_value = str(imagehash.average_hash(img))
                self.hash_cache[image_path] = hash_value
                return hash_value
        except Exception as e:
            return ""
    
    def calculate_hamming_distance(self, hash1: str, hash2: str) -> int:
        """
        计算两个哈希值的汉明距离
        
        Args:
            hash1: 第一个哈希值
            hash2: 第二个哈希值
            
        Returns:
            int: 汉明距离
        """
        if len(hash1) != len(hash2):
            return float('inf')
            
        return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
    
    def find_similar_reference_hash(self, target_hash: str) -> Tuple[bool, str]:
        """
        在参考哈希中查找相似哈希
        
        Args:
            target_hash: 目标哈希值
            
        Returns:
            Tuple[bool, str]: (是否找到相似值, 相似URI)
        """
        if not target_hash or not self.reference_hashes:
            return False, ""
            
        threshold = self.params.get('ref_hamming_distance', 12)
        
        for ref_hash, uri in self.reference_hashes.items():
            distance = self.calculate_hamming_distance(target_hash, ref_hash)
            if distance <= threshold:
                return True, uri
                
        return False, ""
    
    def process_image(self, image_path: Path) -> Tuple[bool, str]:
        """
        处理单个图片
        
        Args:
            image_path: 图片路径
            
        Returns:
            Tuple[bool, str]: (是否需要删除, 删除原因)
        """
        try:
            # 计算当前图片的哈希值
            current_hash = self.calculate_image_hash(image_path)
            if not current_hash:
                return False, "hash_error"
            
            # 检查是否与参考哈希相似
            if self.reference_hashes:
                is_similar, uri = self.find_similar_reference_hash(current_hash)
                if is_similar:
                    return True, f"hash_duplicate (ref: {uri})"
            
            # 检查是否与已处理的图片相似
            threshold = self.params.get('hamming_distance', 0)
            for processed_path, processed_hash in self.hash_cache.items():
                if processed_path == image_path:
                    continue
                    
                distance = self.calculate_hamming_distance(current_hash, processed_hash)
                if distance <= threshold:
                    return True, f"normal_duplicate (similar to: {processed_path.name})"
            
            return False, ""
            
        except Exception as e:
            return False, f"error: {str(e)}"
    
    def process_images(self, image_paths: List[Path]) -> Tuple[List[Path], Dict[Path, str]]:
        """
        重写process_images方法以支持批量处理
        
        Args:
            image_paths: 图片路径列表
            
        Returns:
            Tuple[List[Path], Dict[Path, str]]: (需要删除的文件列表, 删除原因字典)
        """
        # 加载参考哈希文件
        if 'hash_file' in self.params:
            self.load_reference_hashes(self.params['hash_file'])
        
        # 清空缓存
        self.hash_cache.clear()
        self.removed_files = []
        self.removal_reasons = {}
        
        # 预先计算所有图片的哈希值
        for image_path in image_paths:
            self.calculate_image_hash(image_path)
        
        # 处理每个图片
        for image_path in image_paths:
            should_remove, reason = self.process_image(image_path)
            if should_remove:
                self.removed_files.append(image_path)
                self.removal_reasons[image_path] = reason
        
        return self.removed_files, self.removal_reasons 
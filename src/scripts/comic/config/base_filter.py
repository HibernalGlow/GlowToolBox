from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any
from pathlib import Path

class BaseImageFilter(ABC):
    """基础图片过滤器类"""
    
    def __init__(self, params: Dict[str, Any]):
        """
        初始化过滤器
        
        Args:
            params: 过滤器参数字典
        """
        self.params = params
        self.removed_files = []
        self.removal_reasons = {}
        
    @abstractmethod
    def process_image(self, image_path: Path) -> Tuple[bool, str]:
        """
        处理单个图片
        
        Args:
            image_path: 图片路径
            
        Returns:
            Tuple[bool, str]: (是否需要删除, 删除原因)
        """
        pass
        
    def process_images(self, image_paths: List[Path]) -> Tuple[List[Path], Dict[Path, str]]:
        """
        处理多个图片
        
        Args:
            image_paths: 图片路径列表
            
        Returns:
            Tuple[List[Path], Dict[Path, str]]: (需要删除的文件列表, 删除原因字典)
        """
        self.removed_files = []
        self.removal_reasons = {}
        
        for image_path in image_paths:
            should_remove, reason = self.process_image(image_path)
            if should_remove:
                self.removed_files.append(image_path)
                self.removal_reasons[image_path] = reason
                
        return self.removed_files, self.removal_reasons
        
    def get_filter_name(self) -> str:
        """获取过滤器名称"""
        return self.__class__.__name__
        
    def get_filter_description(self) -> str:
        """获取过滤器描述"""
        return "基础图片过滤器" 
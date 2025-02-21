from pathlib import Path
from PIL import Image
from typing import Tuple
from .base_filter import BaseImageFilter

class SmallImageFilter(BaseImageFilter):
    """小图过滤器"""
    
    def get_filter_description(self) -> str:
        return f"小图过滤器 (最小尺寸: {self.params.get('min_size', 631)})"
    
    def process_image(self, image_path: Path) -> Tuple[bool, str]:
        """
        处理单个图片
        
        Args:
            image_path: 图片路径
            
        Returns:
            Tuple[bool, str]: (是否需要删除, 删除原因)
        """
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                min_size = self.params.get('min_size', 631)
                
                if height < min_size:
                    return True, f"small_image (height: {height} < {min_size})"
                    
                return False, ""
                
        except Exception as e:
            return False, f"error: {str(e)}" 
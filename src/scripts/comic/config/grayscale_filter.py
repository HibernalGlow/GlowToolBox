from pathlib import Path
from PIL import Image
import numpy as np
from typing import Tuple
from .base_filter import BaseImageFilter

class GrayscaleImageFilter(BaseImageFilter):
    """灰度图过滤器"""
    
    def get_filter_description(self) -> str:
        return "灰度图/白图过滤器"
    
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
                # 转换为RGB模式
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 转换为numpy数组
                img_array = np.array(img)
                
                # 检查是否为纯白图
                if np.mean(img_array) > 250:
                    return True, "pure_white"
                
                # 检查是否为灰度图
                r, g, b = img_array[:,:,0], img_array[:,:,1], img_array[:,:,2]
                is_grayscale = np.allclose(r, g, atol=5) and np.allclose(g, b, atol=5)
                
                if is_grayscale:
                    mean_value = np.mean(img_array)
                    if mean_value < 30:
                        return True, "pure_black"
                    return True, "grayscale"
                
                return False, ""
                
        except Exception as e:
            return False, f"error: {str(e)}" 
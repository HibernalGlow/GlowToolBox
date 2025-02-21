from pathlib import Path
from typing import Dict, List, Type, Tuple
from .base_filter import BaseImageFilter
from .small_filter import SmallImageFilter
from .grayscale_filter import GrayscaleImageFilter
from .duplicate_filter import DuplicateImageFilter

class FilterManager:
    """过滤器管理器"""
    
    def __init__(self):
        self.filters: Dict[str, Type[BaseImageFilter]] = {
            'small': SmallImageFilter,
            'grayscale': GrayscaleImageFilter,
            'duplicate': DuplicateImageFilter
        }
        self.active_filters: Dict[str, BaseImageFilter] = {}
        
    def create_filter(self, filter_type: str, params: Dict) -> BaseImageFilter:
        """
        创建过滤器实例
        
        Args:
            filter_type: 过滤器类型
            params: 过滤器参数
            
        Returns:
            BaseImageFilter: 过滤器实例
        """
        if filter_type not in self.filters:
            raise ValueError(f"未知的过滤器类型: {filter_type}")
            
        filter_class = self.filters[filter_type]
        return filter_class(params)
        
    def add_filter(self, filter_type: str, params: Dict) -> None:
        """
        添加过滤器
        
        Args:
            filter_type: 过滤器类型
            params: 过滤器参数
        """
        self.active_filters[filter_type] = self.create_filter(filter_type, params)
        
    def remove_filter(self, filter_type: str) -> None:
        """
        移除过滤器
        
        Args:
            filter_type: 过滤器类型
        """
        self.active_filters.pop(filter_type, None)
        
    def clear_filters(self) -> None:
        """清空所有过滤器"""
        self.active_filters.clear()
        
    def get_active_filters(self) -> List[BaseImageFilter]:
        """获取所有激活的过滤器"""
        return list(self.active_filters.values())
        
    def process_images(self, image_paths: List[Path]) -> Dict[str, Dict]:
        """
        使用所有激活的过滤器处理图片
        
        Args:
            image_paths: 图片路径列表
            
        Returns:
            Dict[str, Dict]: 每个过滤器的处理结果
                {
                    'filter_name': {
                        'removed_files': [...],
                        'removal_reasons': {...}
                    }
                }
        """
        results = {}
        
        for filter_type, filter_instance in self.active_filters.items():
            removed_files, removal_reasons = filter_instance.process_images(image_paths)
            results[filter_type] = {
                'removed_files': removed_files,
                'removal_reasons': removal_reasons
            }
            
        return results
        
    def get_all_removed_files(self, results: Dict[str, Dict]) -> Tuple[List[Path], Dict[Path, str]]:
        """
        获取所有需要删除的文件
        
        Args:
            results: process_images的返回结果
            
        Returns:
            Tuple[List[Path], Dict[Path, str]]: (所有需要删除的文件列表, 删除原因字典)
        """
        all_removed_files = set()
        all_removal_reasons = {}
        
        for filter_type, result in results.items():
            removed_files = result['removed_files']
            removal_reasons = result['removal_reasons']
            
            for file_path in removed_files:
                if file_path not in all_removed_files:
                    all_removed_files.add(file_path)
                    all_removal_reasons[file_path] = f"{filter_type}: {removal_reasons[file_path]}"
                    
        return list(all_removed_files), all_removal_reasons 
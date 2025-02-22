import os
import logging
from typing import List, Set, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class PathHandler:
    """路径处理类"""
    
    @staticmethod
    def normalize_path(path: str) -> str:
        """
        规范化路径，处理引号和转义字符
        
        Args:
            path: 原始路径
            
        Returns:
            str: 规范化后的路径
        """
        # 移除首尾的引号
        path = path.strip('"\'')
        # 处理转义字符
        path = path.replace('\\\\', '\\')
        # 转换为绝对路径
        return os.path.abspath(path)
        
    @staticmethod
    def ensure_directory(path: str) -> bool:
        """
        确保目录存在，如果不存在则创建
        
        Args:
            path: 目录路径
            
        Returns:
            bool: 是否成功
        """
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"创建目录失败 {path}: {e}")
            return False
            
    @staticmethod
    def get_file_extension(path: str) -> str:
        """
        获取文件扩展名
        
        Args:
            path: 文件路径
            
        Returns:
            str: 文件扩展名（小写）
        """
        return os.path.splitext(path)[1].lower()
        
    @staticmethod
    def filter_files_by_extension(paths: List[str], extensions: Set[str]) -> List[str]:
        """
        按扩展名过滤文件
        
        Args:
            paths: 文件路径列表
            extensions: 扩展名集合（小写）
            
        Returns:
            List[str]: 符合条件的文件列表
        """
        return [p for p in paths if PathHandler.get_file_extension(p) in extensions]
        
    @staticmethod
    def get_relative_path(path: str, base_path: str) -> str:
        """
        获取相对路径
        
        Args:
            path: 文件路径
            base_path: 基准路径
            
        Returns:
            str: 相对路径
        """
        return os.path.relpath(path, base_path)
        
    @staticmethod
    def join_paths(*paths: str) -> str:
        """
        连接路径
        
        Args:
            *paths: 路径片段
            
        Returns:
            str: 连接后的路径
        """
        return os.path.join(*paths)
        
    @staticmethod
    def get_parent_directory(path: str) -> str:
        """
        获取父目录
        
        Args:
            path: 文件或目录路径
            
        Returns:
            str: 父目录路径
        """
        return os.path.dirname(path)
        
    @staticmethod
    def get_filename(path: str, with_extension: bool = True) -> str:
        """
        获取文件名
        
        Args:
            path: 文件路径
            with_extension: 是否包含扩展名
            
        Returns:
            str: 文件名
        """
        if with_extension:
            return os.path.basename(path)
        return os.path.splitext(os.path.basename(path))[0]
        
class ExtractMode:
    """解压模式类"""
    
    ALL = "all"  # 全部解压
    FIRST_N = "first_n"  # 解压前N张
    LAST_N = "last_n"  # 解压后N张
    RANGE = "range"  # 解压指定范围
    
    @staticmethod
    def get_selected_indices(mode: str, total_files: int, params: dict) -> Set[int]:
        """
        根据解压模式获取选中的文件索引
        
        Args:
            mode: 解压模式
            total_files: 总文件数
            params: 参数字典，包含 n 或 range_str
            
        Returns:
            Set[int]: 选中的文件索引集合
        """
        if mode == ExtractMode.ALL:
            return set(range(total_files))
            
        elif mode == ExtractMode.FIRST_N:
            n = min(params.get('n', 1), total_files)
            return set(range(n))
            
        elif mode == ExtractMode.LAST_N:
            n = min(params.get('n', 1), total_files)
            return set(range(total_files - n, total_files))
            
        elif mode == ExtractMode.RANGE:
            range_str = params.get('range_str', '')
            try:
                start, end = map(int, range_str.split(':'))
                start = max(0, start)
                end = min(total_files, end)
                return set(range(start, end))
            except:
                return set()
                
        return set() 
import os
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class CbrHandler:
    """CBR文件处理器"""
    
    def __init__(self):
        self.supported_extensions = {'.cbr', '.cbz', '.zip', '.rar'}
        
    def convert_cbr_to_cbz(self, file_path: str) -> bool:
        """
        将CBR文件转换为CBZ文件
        
        Args:
            file_path: CBR文件路径
            
        Returns:
            bool: 转换是否成功
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                logger.error(f"文件不存在: {file_path}")
                return False
                
            # 检查文件扩展名
            if file_path.suffix.lower() not in self.supported_extensions:
                logger.error(f"不支持的文件格式: {file_path.suffix}")
                return False
                
            # 如果是CBR文件，直接重命名为CBZ
            if file_path.suffix.lower() == '.cbr':
                new_path = file_path.with_suffix('.cbz')
                try:
                    file_path.rename(new_path)
                    logger.info(f"已将CBR文件重命名为CBZ: {new_path}")
                    return True
                except Exception as e:
                    logger.error(f"重命名文件失败: {e}")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"处理CBR文件时出错: {e}")
            return False
            
    def process_directory(self, directory: str) -> None:
        """
        处理目录中的所有CBR文件
        
        Args:
            directory: 要处理的目录路径
        """
        try:
            directory = Path(directory)
            if not directory.exists():
                logger.error(f"目录不存在: {directory}")
                return
                
            # 遍历目录中的所有文件
            for file_path in directory.rglob('*'):
                if file_path.suffix.lower() in self.supported_extensions:
                    self.convert_cbr_to_cbz(str(file_path))
                    
        except Exception as e:
            logger.error(f"处理目录时出错: {e}") 
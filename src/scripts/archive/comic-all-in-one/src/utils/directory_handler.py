import os
import logging
from src.services.logging_service import LoggingService
from src.services.stats_service import StatsService

class DirectoryHandler:
    """
    类描述
    """
    @staticmethod
    def remove_empty_directories(path, exclude_keywords=[]):
        """
        删除指定路径下的所有空文件夹
        
        Args:
            path (str): 目标路径
            exclude_keywords (list): 排除关键词列表
        """
        removed_count = 0
        for root, dirs, _ in os.walk(path, topdown=False):
            if any((keyword in root for keyword in exclude_keywords)):
                continue
            for dir_name in dirs:
                folder_path = os.path.join(root, dir_name)
                try:
                    if not os.listdir(folder_path):
                        os.rmdir(folder_path)
                        removed_count += 1
                        logging.info(f'[#file_ops]已删除空文件夹: {folder_path}')
                except Exception as e:
                    logging.info( f"❌ 删除空文件夹失败 {folder_path}: {e}")
        if removed_count > 0:
            logging.info( f'共删除 {removed_count} 个空文件夹')
        return removed_count


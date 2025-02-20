import os
import shutil
from src.services.logging_service import LoggingService
import time
import logging

class PathManager:
    """
    类描述
    """
    @staticmethod
    def create_temp_directory(file_path):
        """
        为每个压缩包创建唯一的临时目录，使用压缩包原名+时间戳
        
        Args:
            file_path: 源文件路径（压缩包路径）
        """
        original_dir = os.path.dirname(file_path)
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        timestamp = int(time.time() * 1000)
        temp_dir = os.path.join(original_dir, f'{file_name}_{timestamp}')
        os.makedirs(temp_dir, exist_ok=True)
        logging.info( f'创建临时目录: {temp_dir}')
        return temp_dir

    @staticmethod
    def cleanup_temp_files(temp_dir, new_zip_path, backup_file_path):
        """清理临时文件和目录，但不处理备份文件"""
        try:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logging.info( f'已删除临时目录: {temp_dir}')
            if new_zip_path and os.path.exists(new_zip_path):
                os.remove(new_zip_path)
                logging.info( f'已删除临时压缩包: {new_zip_path}')
            # 不处理备份文件，让BackupHandler.handle_bak_file来处理
        except Exception as e:
            logging.info( f"❌ 清理临时文件时出错: {e}")


import os
import logging
import time
import shutil

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
                    logging.info( f"[#file_ops]{folder_path}: {e}")
        if removed_count > 0:
            logging.info( f'共删除 {removed_count} 个空文件夹')
        return removed_count
    @staticmethod
    def create_temp_directory(file_path):
        """
        为每个压缩包创建唯一的临时目录，使用压缩包原名+时间戳
        
        Args:
            file_path: 源文件路径（压缩包路径）
        """
        original_dir = os.path.dirname(file_path)
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
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

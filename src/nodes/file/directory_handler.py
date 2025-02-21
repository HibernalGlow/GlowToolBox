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
    def rename_file_in_filesystem(file_path, new_name):
        """
        重命名文件系统中的普通文件
        
        Args:
            file_path (str): 源文件路径
            new_name (str): 新的文件名（不包含路径，仅文件名部分）
        
        Returns:
            str: 重命名后的文件路径
            
        Raises:
            FileNotFoundError: 当源文件不存在时
            OSError: 当重命名操作失败时
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"源文件不存在: {file_path}")
            
            # 获取文件所在目录和扩展名
            dir_path = os.path.dirname(file_path)
            _, ext = os.path.splitext(file_path)
            
            # 构建新的文件路径
            new_file_path = os.path.join(dir_path, f"{new_name}{ext}")
            
            # 如果目标文件已存在，添加数字后缀
            counter = 1
            while os.path.exists(new_file_path):
                new_file_path = os.path.join(dir_path, f"{new_name}_{counter}{ext}")
                counter += 1
            
            # 执行重命名操作
            os.rename(file_path, new_file_path)
            logging.info(f"[#file_ops]已重命名文件: {file_path} -> {new_file_path}")
            
            return new_file_path
            
        except FileNotFoundError as e:
            logging.error(f"[#file_ops]文件不存在: {file_path}")
            raise e
        except OSError as e:
            logging.error(f"[#file_ops]重命名文件失败: {file_path} -> {new_name}, 错误: {str(e)}")
            raise e
        except Exception as e:
            logging.error(f"[#file_ops]重命名文件时发生未知错误: {str(e)}")
            raise e

    @staticmethod
    def rename_file_in_archive(file_path, new_name):
        """
        重命名压缩包内的文件
        
        Args:
            file_path (str): 压缩包内的文件路径
            new_name (str): 新的文件名（不包含路径，仅文件名部分）
        
        Returns:
            str: 重命名后的文件路径
            
        Raises:
            FileNotFoundError: 当源文件不存在时
            OSError: 当重命名操作失败时
        """
        try:
            # 获取文件所在目录和扩展名
            dir_path = os.path.dirname(file_path)
            _, ext = os.path.splitext(file_path)
            
            # 构建新的文件路径
            new_file_path = os.path.join(dir_path, f"{new_name}{ext}")
            
            # 如果目标文件已存在，添加数字后缀
            counter = 1
            while os.path.exists(new_file_path):
                new_file_path = os.path.join(dir_path, f"{new_name}_{counter}{ext}")
                counter += 1
            
            # 返回新的文件路径，实际的重命名操作由压缩包处理器执行
            logging.info(f"[#file_ops]压缩包内文件重命名路径: {file_path} -> {new_file_path}")
            return new_file_path
            
        except Exception as e:
            logging.error(f"[#file_ops]压缩包内文件重命名路径生成失败: {str(e)}")
            raise e
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

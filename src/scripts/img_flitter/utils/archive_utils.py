import os
import subprocess
from services.logging_service import LoggingService
import logging
from utils.path_utils import PathManager

import shutil
class ArchiveUtils:
    """压缩包处理工具类"""
    @staticmethod
    def get_image_files(directory):
        """获取目录中的所有图片文件"""
        image_files = []
        image_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.jxl', '.avif', '.bmp')
        
        for root, _, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(image_extensions):
                    image_files.append(os.path.join(root, file))
                    
        return image_files



    @staticmethod
    def prepare_archive(file_path):
        """准备压缩包处理环境"""
        temp_dir = PathManager.create_temp_directory(file_path)
        backup_file_path = file_path + '.bak'
        new_zip_path = os.path.join(os.path.dirname(file_path), f'{os.path.splitext(os.path.basename(file_path))[0]}.new.zip')
        try:
            shutil.copy(file_path, backup_file_path)
            logging.info( f'创建备份: {backup_file_path}')
            cmd = ['7z', 'x', file_path, f'-o{temp_dir}', '-y']
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logging.info( f"❌ 解压失败: {file_path}\n错误: {result.stderr}")
                PathManager.cleanup_temp_files(temp_dir, new_zip_path, backup_file_path)
                return (None, None, None)
            return (temp_dir, backup_file_path, new_zip_path)
        except Exception as e:
            logging.info( f"❌ 准备环境失败 {file_path}: {e}")
            PathManager.cleanup_temp_files(temp_dir, new_zip_path, backup_file_path)
            return (None, None, None)


    @staticmethod
    def run_7z_command(command, zip_path, operation='', additional_args=None):
        """
        执7z命令的通函数
        
        Args:
            command: 主命令 (如 'a', 'x', 'l' 等)
            zip_path: 压缩包路径
            operation: 操作描述（用于日志）
            additional_args: 额外的命令行参数
        """
        try:
            cmd = ['7z', command, zip_path]
            if additional_args:
                cmd.extend(additional_args)
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                logging.info( f'成功执行7z {operation}: {zip_path}')
                return (True, result.stdout)
            else:
                logging.info( f"❌ 7z {operation}失败: {zip_path}\n错误: {result.stderr}")
                return (False, result.stderr)
        except Exception as e:
            logging.info( f"❌ 执行7z命令出错: {e}")
            return (False, str(e))


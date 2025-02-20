import subprocess
import os
import logging
from datetime import datetime
from utils.hash_utils import HashFileHandler

class ProcessedLogHandler:
    """
    类描述
    """
    @staticmethod
    def has_processed_log(zip_path):
        command = ['7z', 'l', zip_path]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            if 'processed.log' in result.stdout:
                ProcessedLogHandler.save_processed_file(zip_path)
                return True
        else:
            logging.info( f"❌ Failed to list contents of {zip_path}: {result.stderr}")
        return False

    @staticmethod
    def add_processed_log(zip_path, processed_info):
        """
        将处理日志添加到压缩包中
        
        Args:
            zip_path: 压缩包路径
            processed_info: 处理信息字典，包含:
                - hash_duplicates_removed: 哈希重复数量
                - normal_duplicates_removed: 普通重复数量
                - small_images_removed: 小图数量
                - white_images_removed: 白图数量
        """
        try:
            # 创建临时目录
            temp_dir = os.path.join(os.path.dirname(zip_path), 'temp_log')
            os.makedirs(temp_dir, exist_ok=True)
            
            # 创建日志文件
            log_file_path = os.path.join(temp_dir, 'processed.log')
            with open(log_file_path, 'w', encoding='utf-8') as log_file:
                # 基本处理信息
                log_file.write(f'{os.path.basename(zip_path)} - 处理时间: {datetime.now()} - 处理情况:\n')
                log_file.write(f" - 删除的哈希重复图片: {processed_info.get('hash_duplicates_removed', 0)}\n")
                log_file.write(f" - 删除的普通重复图片: {processed_info.get('normal_duplicates_removed', 0)}\n")
                log_file.write(f" - 删除的小图数量: {processed_info.get('small_images_removed', 0)}\n")
                log_file.write(f" - 删除的白图数量: {processed_info.get('white_images_removed', 0)}\n\n")
                
                # 添加相似性记录
                similarity_records = HashFileHandler.get_similarity_records()
                if similarity_records:
                    log_file.write("相似性记录:\n")
                    for record in similarity_records:
                        log_file.write(f" - 文件: {os.path.basename(record['file_path'])}\n")
                        log_file.write(f"   相似于: {record['similar_uri']}\n")
                        log_file.write(f"   汉明距离: {record['hamming_distance']}\n")
                        log_file.write(f"   记录时间: {record['timestamp']}\n")
                    log_file.write("\n")
            
            # 将日志文件添加到压缩包
            command = ['7z', 'a', zip_path, log_file_path]
            result = subprocess.run(command, capture_output=True, text=True)
            
            # 清理临时文件和目录
            os.remove(log_file_path)
            os.rmdir(temp_dir)
            
            # 清空相似性记录，为下一个文件做准备
            HashFileHandler.clear_similarity_records()
            
            if result.returncode == 0:
                logging.info( f'成功添加处理日志到压缩包: {zip_path}')
            else:
                logging.info( f"❌ 添加日志到压缩包失败: {result.stderr}")
                
        except Exception as e:
            logging.info( f"❌ 添加日志到压缩包时出错: {e}")
            # 确保清理临时文件
            if os.path.exists(log_file_path):
                os.remove(log_file_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)


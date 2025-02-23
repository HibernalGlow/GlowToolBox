import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import logging

class LogCleaner:
    def __init__(self, log_base_path='logs', retention_days=7):
        """
        初始化日志清理器
        
        Args:
            log_base_path (str): 日志根目录
            retention_days (int): 日志保留天数
        """
        self.log_base_path = Path(log_base_path)
        self.retention_days = retention_days
        self.logger = logging.getLogger(__name__)

    def clean_old_logs(self):
        """清理指定天数之前的日志"""
        if not self.log_base_path.exists():
            return
            
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        
        try:
            # 遍历所有脚本目录
            for script_dir in self.log_base_path.iterdir():
                if not script_dir.is_dir():
                    continue
                    
                # 遍历日期目录
                for date_dir in script_dir.iterdir():
                    if not date_dir.is_dir():
                        continue
                        
                    try:
                        # 将目录名转换为日期对象
                        dir_date = datetime.strptime(date_dir.name, '%Y%m%d')
                        
                        # 如果目录日期早于截止日期，删除整个目录
                        if dir_date < cutoff_date:
                            shutil.rmtree(date_dir)
                            self.logger.info(f"已清理过期日志目录: {date_dir}")
                            
                    except ValueError:
                        # 如果目录名不符合日期格式，跳过
                        continue
                        
                # 如果脚本目录为空，也清理掉
                if not any(script_dir.iterdir()):
                    script_dir.rmdir()
                    self.logger.info(f"已清理空的脚本目录: {script_dir}")
                    
        except Exception as e:
            self.logger.error(f"清理日志时发生错误: {e}")

def clean_logs(log_path='logs', retention_days=7):
    """
    清理日志的便捷函数
    
    Args:
        log_path (str): 日志根目录
        retention_days (int): 日志保留天数
    """
    cleaner = LogCleaner(log_path, retention_days)
    cleaner.clean_old_logs() 
import os
import json
import logging
from datetime import datetime
from threading import Lock
from typing import Dict, Optional

class TimestampManager:
    """线程安全的时间戳管理器类"""
    
    def __init__(self, json_file: str):
        """
        初始化时间戳管理器
        
        Args:
            json_file (str): JSON文件路径
        """
        self.json_file = json_file
        self._lock = Lock()
        self._timestamps: Dict[str, float] = {}
        self._load_json()
    
    def _load_json(self) -> None:
        """加载JSON文件，添加错误处理"""
        try:
            if os.path.exists(self.json_file):
                with self._lock:
                    with open(self.json_file, 'r', encoding='utf-8') as file:
                        self._timestamps = json.load(file)
                logging.info(f"[#process]✅ 成功加载时间戳文件: {self.json_file}")
        except json.JSONDecodeError as e:
            logging.error(f"[#update]❌ JSON解析错误: {str(e)}")
            self._timestamps = {}
        except Exception as e:
            logging.error(f"[#update]❌ 读取时间戳文件失败: {str(e)}")
            self._timestamps = {}
    
    def save_json(self) -> None:
        """保存JSON文件，添加错误处理和线程安全"""
        try:
            with self._lock:
                # 创建临时文件
                temp_file = f"{self.json_file}.tmp"
                with open(temp_file, 'w', encoding='utf-8') as file:
                    json.dump(self._timestamps, file, ensure_ascii=False, indent=2)
                
                # 安全地替换原文件
                if os.path.exists(self.json_file):
                    os.replace(temp_file, self.json_file)
                else:
                    os.rename(temp_file, self.json_file)
                    
                logging.info(f"[#process]✅ 成功保存时间戳文件: {self.json_file}")
        except Exception as e:
            logging.error(f"[#update]❌ 保存时间戳文件失败: {str(e)}")
            # 清理临时文件
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
    
    def record_timestamp(self, file_path: str) -> None:
        """
        记录文件的时间戳
        
        Args:
            file_path (str): 文件路径
        """
        try:
            with self._lock:
                self._timestamps[file_path] = os.path.getmtime(file_path)
                self.save_json()
                logging.info(f"[#process]✅ 已记录时间戳: {file_path} -> {datetime.fromtimestamp(self._timestamps[file_path])}")
        except Exception as e:
            logging.error(f"[#update]❌ 记录时间戳失败: {str(e)}")
    
    def restore_timestamp(self, file_path: str) -> None:
        """
        恢复文件的时间戳
        
        Args:
            file_path (str): 文件路径
        """
        try:
            with self._lock:
                if file_path in self._timestamps:
                    timestamp = self._timestamps[file_path]
                    os.utime(file_path, (timestamp, timestamp))
                    logging.info(f"[#process]✅ 已恢复时间戳: {file_path} -> {datetime.fromtimestamp(timestamp)}")
                else:
                    logging.warning(f"[#update]⚠️ 未找到时间戳记录: {file_path}")
        except Exception as e:
            logging.error(f"[#update]❌ 恢复时间戳失败: {str(e)}")
    
    def get_timestamp(self, file_path: str) -> Optional[float]:
        """
        获取文件的时间戳
        
        Args:
            file_path (str): 文件路径
            
        Returns:
            Optional[float]: 时间戳，如果不存在则返回None
        """
        with self._lock:
            return self._timestamps.get(file_path)
    
    def clear_timestamps(self) -> None:
        """清除所有时间戳记录"""
        with self._lock:
            self._timestamps.clear()
            self.save_json()
            logging.info("[#process]✅ 已清除所有时间戳记录") 
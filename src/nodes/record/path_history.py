import os
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

class PathHistoryManager:
    """路径历史记录管理器"""
    
    def __init__(self, history_file: str = "path_history.json"):
        """
        初始化路径历史记录管理器
        
        Args:
            history_file: 历史记录文件路径，默认在用户目录下的 .glowtoolbox/history/path_history.json
        """
        # 确保历史记录目录存在
        self.history_dir = os.path.expanduser("~/.glowtoolbox/history")
        os.makedirs(self.history_dir, exist_ok=True)
        
        # 设置历史记录文件路径
        self.history_file = os.path.join(self.history_dir, history_file)
        
        # 初始化或加载历史记录
        self.history: Dict[str, Dict[str, List[Dict[str, Any]]]] = self._load_history()
        
    def _load_history(self) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """加载历史记录文件"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"加载历史记录文件失败: {e}")
            return {}
            
    def _save_history(self) -> None:
        """保存历史记录到文件"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存历史记录文件失败: {e}")
            
    def record_paths(self, script_name: str, paths: List[str], status: Dict[str, Any]) -> None:
        """
        记录路径处理历史
        
        Args:
            script_name: 调用脚本的名称
            paths: 处理的路径列表
            status: 处理状态信息字典
        """
        # 获取当前时间戳（人类可读格式）
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 确保脚本的历史记录存在
        if script_name not in self.history:
            self.history[script_name] = {"records": []}
            
        # 创建新的记录
        record = {
            "timestamp": timestamp,
            "paths": paths,
            "status": status
        }
        
        # 添加记录
        self.history[script_name]["records"].append(record)
        
        # 保存历史记录
        self._save_history()
        
    def get_script_history(self, script_name: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取指定脚本的历史记录
        
        Args:
            script_name: 脚本名称
            limit: 返回的记录数量限制，None表示返回所有记录
            
        Returns:
            List[Dict[str, Any]]: 历史记录列表
        """
        if script_name not in self.history:
            return []
            
        records = self.history[script_name]["records"]
        if limit is not None:
            return records[-limit:]
        return records
        
    def clear_script_history(self, script_name: str) -> bool:
        """
        清除指定脚本的历史记录
        
        Args:
            script_name: 脚本名称
            
        Returns:
            bool: 是否成功清除
        """
        if script_name in self.history:
            del self.history[script_name]
            self._save_history()
            return True
        return False
        
    def get_all_scripts(self) -> List[str]:
        """
        获取所有记录过的脚本名称
        
        Returns:
            List[str]: 脚本名称列表
        """
        return list(self.history.keys())
        
    def get_latest_record(self, script_name: str) -> Optional[Dict[str, Any]]:
        """
        获取指定脚本的最新记录
        
        Args:
            script_name: 脚本名称
            
        Returns:
            Optional[Dict[str, Any]]: 最新记录，如果没有则返回None
        """
        records = self.get_script_history(script_name)
        return records[-1] if records else None

# 使用示例
if __name__ == "__main__":
    # 创建历史记录管理器实例
    manager = PathHistoryManager()
    
    # 示例：记录路径处理
    paths = [
        "D:/example/path1",
        "D:/example/path2"
    ]
    
    status = {
        "success": True,
        "processed": 2,
        "failed": 0,
        "details": {
            "path1": {"status": "success", "time": "1.2s"},
            "path2": {"status": "success", "time": "0.8s"}
        }
    }
    
    # 记录路径处理历史
    manager.record_paths("test_script", paths, status)
    
    # 获取历史记录
    history = manager.get_script_history("test_script")
    print("历史记录:", json.dumps(history, ensure_ascii=False, indent=2)) 
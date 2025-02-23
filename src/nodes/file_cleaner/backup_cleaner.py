import os
import shutil
import fnmatch
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Set
import threading
from queue import Queue
import time

class BackupCleaner:
    def __init__(self, max_workers: int = None):
        """
        初始化备份文件清理器
        
        Args:
            max_workers: 最大工作线程数，默认为CPU核心数的2倍
        """
        self.max_workers = max_workers or (os.cpu_count() * 2)
        self._lock = threading.Lock()
        self._removed_count = 0
        self._skipped_count = 0
        
    def _is_file_in_use(self, file_path: str) -> bool:
        """检查文件是否正在使用"""
        try:
            # 创建一个临时文件名
            temp_path = str(file_path) + ".tmp"
            # 尝试重命名文件
            os.rename(file_path, temp_path)
            # 如果成功，改回原名
            os.rename(temp_path, file_path)
            return False
        except (OSError, PermissionError):
            return True
        except Exception:
            return False
            
    def _process_batch(self, items: List[Path], patterns: List[Tuple[str, str]], 
                      exclude_keywords: List[str]) -> Tuple[int, int]:
        """处理一批文件/文件夹"""
        removed = 0
        skipped = 0
        
        for item in items:
            # 检查排除关键词
            if any(keyword in str(item) for keyword in exclude_keywords):
                continue
                
            try:
                # 检查文件或文件夹是否正在使用
                if item.is_file():
                    if self._is_file_in_use(str(item)):
                        skipped += 1
                        continue
                        
                # 检查是否匹配删除模式
                for pattern, target_type in patterns:
                    matched = False
                    
                    if target_type in ['file', 'both'] and item.is_file():
                        matched = fnmatch.fnmatch(item.name, pattern)
                    elif target_type in ['dir', 'both'] and item.is_dir():
                        matched = fnmatch.fnmatch(item.name, pattern)
                        
                    if matched:
                        try:
                            if item.is_dir():
                                shutil.rmtree(item)
                            else:
                                item.unlink()
                            removed += 1
                        except Exception:
                            skipped += 1
                        break
                        
            except Exception:
                skipped += 1
                
        return removed, skipped
        
    def _update_counts(self, removed: int, skipped: int):
        """更新计数器"""
        with self._lock:
            self._removed_count += removed
            self._skipped_count += skipped
            
    def clean(self, path: Path, patterns: List[Tuple[str, str]], 
             exclude_keywords: List[str], batch_size: int = 100) -> Tuple[int, int]:
        """
        清理备份文件和临时文件
        
        Args:
            path: 要清理的路径
            patterns: 删除模式列表，每个元素为(pattern, type)元组
            exclude_keywords: 排除关键词列表
            batch_size: 批处理大小
            
        Returns:
            Tuple[int, int]: (删除数量, 跳过数量)
        """
        self._removed_count = 0
        self._skipped_count = 0
        
        # 收集所有项目
        items = []
        for item in path.rglob("*"):
            items.append(item)
            
            # 当收集到一定数量时进行批处理
            if len(items) >= batch_size:
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = []
                    for i in range(0, len(items), batch_size):
                        batch = items[i:i + batch_size]
                        future = executor.submit(self._process_batch, batch, patterns, exclude_keywords)
                        futures.append(future)
                        
                    # 收集结果
                    for future in as_completed(futures):
                        removed, skipped = future.result()
                        self._update_counts(removed, skipped)
                        
                items = []
                
        # 处理剩余项目
        if items:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for i in range(0, len(items), batch_size):
                    batch = items[i:i + batch_size]
                    future = executor.submit(self._process_batch, batch, patterns, exclude_keywords)
                    futures.append(future)
                    
                # 收集结果
                for future in as_completed(futures):
                    removed, skipped = future.result()
                    self._update_counts(removed, skipped)
                    
        return self._removed_count, self._skipped_count 
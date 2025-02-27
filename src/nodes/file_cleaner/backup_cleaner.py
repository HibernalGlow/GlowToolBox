import os
import shutil
import fnmatch
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Set
import threading
from queue import Queue
import time
import stat

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
        self._error_paths = set()  # 记录出错的路径
        
    def _force_delete(self, path: Path) -> bool:
        """强制删除文件或文件夹，处理只读等特殊情况"""
        try:
            if path.is_file():
                # 修改文件权限
                path.chmod(stat.S_IWRITE)
                path.unlink()
            else:
                # 递归修改文件夹内所有文件的权限
                for root, dirs, files in os.walk(str(path)):
                    for dir in dirs:
                        try:
                            dir_path = Path(root) / dir
                            dir_path.chmod(stat.S_IWRITE | stat.S_IEXEC)
                        except:
                            pass
                    for file in files:
                        try:
                            file_path = Path(root) / file
                            file_path.chmod(stat.S_IWRITE)
                        except:
                            pass
                shutil.rmtree(path, ignore_errors=True)
            return True
        except Exception as e:
            print(f"强制删除失败 - {e}: {path}")
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
                # 检查是否匹配删除模式
                for pattern, target_type in patterns:
                    matched = False
                    
                    if target_type in ['file', 'both'] and item.is_file():
                        matched = fnmatch.fnmatch(item.name, pattern)
                    elif target_type in ['dir', 'both'] and item.is_dir():
                        matched = fnmatch.fnmatch(item.name, pattern)
                        
                    if matched:
                        try:
                            # 特殊处理 .trash 文件
                            if item.name.endswith('.trash'):
                                if self._force_delete(item):
                                    removed += 1
                                else:
                                    skipped += 1
                            else:
                                # 常规文件的删除尝试
                                try:
                                    if item.is_dir():
                                        shutil.rmtree(item)
                                    else:
                                        item.unlink()
                                    removed += 1
                                except:
                                    # 如果常规删除失败，尝试强制删除
                                    if self._force_delete(item):
                                        removed += 1
                                    else:
                                        skipped += 1
                        except Exception as e:
                            print(f"删除失败 - {e}: {item}")
                            skipped += 1
                        break
                        
            except Exception as e:
                print(f"处理失败 - {e}: {item}")
                skipped += 1
                
        return removed, skipped
        
    def _update_counts(self, removed: int, skipped: int):
        """更新计数器"""
        with self._lock:
            self._removed_count += removed
            self._skipped_count += skipped
            
    def _safe_rglob(self, path: Path) -> List[Path]:
        """安全地遍历目录，忽略访问错误"""
        items = []
        try:
            for item in path.iterdir():
                try:
                    if item.is_dir():
                        items.extend(self._safe_rglob(item))
                    items.append(item)
                except (PermissionError, OSError) as e:
                    with self._lock:
                        self._error_paths.add(str(item))
                    print(f"警告：访问路径时出错 - {e}: {item}")
                    continue
        except (PermissionError, OSError) as e:
            with self._lock:
                self._error_paths.add(str(path))
            print(f"警告：访问目录时出错 - {e}: {path}")
        return items

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
        self._error_paths.clear()  # 清空错误路径记录
        
        # 检查路径是否存在
        if not path.exists():
            print(f"警告：路径不存在 - {path}")
            return self._removed_count, self._skipped_count
            
        try:
            # 使用安全的遍历方法收集所有项目
            items = self._safe_rglob(path)
            
            # 按批次处理项目
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for i in range(0, len(items), batch_size):
                    batch = items[i:i + batch_size]
                    future = executor.submit(self._process_batch, batch, patterns, exclude_keywords)
                    futures.append(future)
                    
                # 收集结果
                for future in as_completed(futures):
                    try:
                        removed, skipped = future.result()
                        self._update_counts(removed, skipped)
                    except Exception as e:
                        print(f"警告：处理批次时出错 - {e}")
                        continue
                            
        except Exception as e:
            print(f"警告：清理过程中出错 - {e}")
            
        # 如果有错误路径，在最后统一报告
        if self._error_paths:
            print(f"\n遇到 {len(self._error_paths)} 个无法访问的路径:")
            for error_path in sorted(self._error_paths):
                print(f"- {error_path}")
            
        return self._removed_count, self._skipped_count 
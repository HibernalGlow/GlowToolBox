import os
import yaml
import shutil
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Union
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import threading
from queue import Queue
import logging
import sys
import atexit
import inspect
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('file_operations.log', encoding='utf-8')
    ]
)

logger = logging.getLogger('FileMonitor')

@dataclass
class FileOperation:
    """文件操作记录类"""
    operation_type: str  # 操作类型：MOVE, DELETE, RENAME, CREATE
    timestamp: float  # 操作时间戳
    source_path: str  # 源路径
    target_path: Optional[str] = None  # 目标路径（用于移动和重命名操作）
    backup_path: Optional[str] = None  # 备份路径（用于删除操作）
    operation_id: Optional[str] = None  # 操作ID
    script_name: Optional[str] = None  # 执行操作的脚本名称
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'FileOperation':
        """从字典创建实例"""
        return cls(**data)

class FileSystemChangeHandler(FileSystemEventHandler):
    """文件系统变化处理器"""
    def __init__(self, monitor):
        self.monitor = monitor
        self.script_name = Path(sys.argv[0]).stem
        self._skip_paths = set()

    def skip_next_event(self, path):
        """标记要跳过的下一个事件"""
        self._skip_paths.add(str(path))

    def should_skip(self, path):
        """检查是否应该跳过这个事件"""
        path_str = str(path)
        if path_str in self._skip_paths:
            self._skip_paths.remove(path_str)
            return True
        return False

    def on_moved(self, event):
        if not self.should_skip(event.src_path):
            self.monitor.record_operation(
                "MOVE",
                event.src_path,
                event.dest_path,
                self.script_name
            )

    def on_created(self, event):
        if not self.should_skip(event.src_path):
            self.monitor.record_operation(
                "CREATE",
                event.src_path,
                script_name=self.script_name
            )

    def on_deleted(self, event):
        if not self.should_skip(event.src_path):
            self.monitor.record_operation(
                "DELETE",
                event.src_path,
                script_name=self.script_name
            )

    def on_modified(self, event):
        # 忽略修改事件，因为我们主要关注文件的创建、移动和删除
        pass

class FileOperationMonitor:
    """文件操作监控类"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化监控器"""
        if not hasattr(self, 'initialized'):
            self.operations: List[FileOperation] = []
            self.backup_dir = Path('file_operations_backup')
            self.history_file = Path('file_operations_history.yaml')
            self.operation_queue = Queue()
            self.backup_dir.mkdir(exist_ok=True)
            self.observer = None
            self.event_handler = None
            self._load_history()
            self.initialized = True
            
            # 启动异步保存线程
            self._save_thread = threading.Thread(target=self._async_save_worker, daemon=True)
            self._save_thread.start()
            
            # 注册退出时的清理函数
            atexit.register(self._cleanup)
    
    def _cleanup(self):
        """清理函数，在程序退出时调用"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self._save_history()  # 确保保存最新的操作历史
    
    def _load_history(self):
        """加载操作历史"""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or []
                    self.operations = [FileOperation.from_dict(op) for op in data]
                logger.info(f"已加载 {len(self.operations)} 条操作记录")
        except Exception as e:
            logger.error(f"加载操作历史失败: {e}")
    
    def _save_history(self):
        """保存操作历史"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(
                    [op.to_dict() for op in self.operations],
                    f,
                    allow_unicode=True,
                    sort_keys=False,
                    indent=2
                )
            logger.debug("操作历史已保存")
        except Exception as e:
            logger.error(f"保存操作历史失败: {e}")
    
    def _async_save_worker(self):
        """异步保存工作线程"""
        while True:
            try:
                # 等待新的操作
                operation = self.operation_queue.get()
                if operation:
                    self.operations.append(operation)
                    self._save_history()
            except Exception as e:
                logger.error(f"异步保存操作失败: {e}")
            finally:
                time.sleep(0.1)  # 避免过于频繁的保存
    
    def start_monitoring(self, paths: Union[str, List[str]] = None):
        """开始监控文件系统变化"""
        if self.observer:
            logger.warning("监控器已经在运行")
            return

        if paths is None:
            # 如果没有指定路径，使用当前工作目录
            paths = [os.getcwd()]
        elif isinstance(paths, str):
            paths = [paths]

        self.event_handler = FileSystemChangeHandler(self)
        self.observer = Observer()
        
        for path in paths:
            try:
                self.observer.schedule(self.event_handler, path, recursive=True)
                logger.info(f"开始监控目录: {path}")
            except Exception as e:
                logger.error(f"监控目录失败 {path}: {e}")

        self.observer.start()
    
    def stop_monitoring(self):
        """停止监控"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            self.event_handler = None
            logger.info("已停止文件监控")
    
    def _create_backup(self, source_path: Union[str, Path]) -> Optional[str]:
        """创建文件备份"""
        try:
            source_path = Path(source_path)
            if not source_path.exists():
                return None
                
            # 创建基于时间戳的备份路径
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = self.backup_dir / f"{source_path.name}_{timestamp}"
            
            # 确保备份路径唯一
            counter = 0
            while backup_path.exists():
                counter += 1
                backup_path = self.backup_dir / f"{source_path.name}_{timestamp}_{counter}"
            
            # 创建备份
            if source_path.is_file():
                shutil.copy2(source_path, backup_path)
            else:
                shutil.copytree(source_path, backup_path)
            
            return str(backup_path)
        except Exception as e:
            logger.error(f"创建备份失败 {source_path}: {e}")
            return None
    
    def record_operation(self, operation_type: str, source_path: str,
                        target_path: Optional[str] = None,
                        script_name: Optional[str] = None) -> None:
        """记录文件操作"""
        try:
            if not script_name:
                # 获取调用者的脚本名称
                frame = inspect.currentframe()
                while frame:
                    if frame.f_code.co_filename != __file__:
                        script_name = Path(frame.f_code.co_filename).stem
                        break
                    frame = frame.f_back
                
            # 创建备份（仅针对删除操作）
            backup_path = None
            if operation_type == 'DELETE':
                backup_path = self._create_backup(source_path)
            
            # 创建操作记录
            operation = FileOperation(
                operation_type=operation_type,
                timestamp=time.time(),
                source_path=str(source_path),
                target_path=str(target_path) if target_path else None,
                backup_path=backup_path,
                operation_id=f"{operation_type}_{int(time.time()*1000)}",
                script_name=script_name
            )
            
            # 将操作添加到队列中
            self.operation_queue.put(operation)
            logger.info(f"已记录操作: {operation_type} - {source_path}")
            
        except Exception as e:
            logger.error(f"记录操作失败: {e}")
    
    def undo_last_operation(self) -> bool:
        """撤销最后一次操作"""
        try:
            if not self.operations:
                logger.warning("没有可撤销的操作")
                return False
            
            last_op = self.operations[-1]
            success = self._undo_operation(last_op)
            
            if success:
                self.operations.pop()
                self._save_history()
                logger.info(f"已撤销操作: {last_op.operation_type}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"撤销操作失败: {e}")
            return False
    
    def _undo_operation(self, operation: FileOperation) -> bool:
        """执行具体的撤销操作"""
        try:
            if operation.operation_type == 'MOVE':
                if os.path.exists(operation.target_path):
                    # 标记这个操作，避免被监控系统记录
                    if self.event_handler:
                        self.event_handler.skip_next_event(operation.target_path)
                        self.event_handler.skip_next_event(operation.source_path)
                    shutil.move(operation.target_path, operation.source_path)
                    
            elif operation.operation_type == 'DELETE':
                if operation.backup_path and os.path.exists(operation.backup_path):
                    if self.event_handler:
                        self.event_handler.skip_next_event(operation.source_path)
                    if os.path.isfile(operation.backup_path):
                        shutil.copy2(operation.backup_path, operation.source_path)
                    else:
                        shutil.copytree(operation.backup_path, operation.source_path)
                        
            elif operation.operation_type == 'RENAME':
                if os.path.exists(operation.target_path):
                    if self.event_handler:
                        self.event_handler.skip_next_event(operation.target_path)
                        self.event_handler.skip_next_event(operation.source_path)
                    os.rename(operation.target_path, operation.source_path)
                    
            elif operation.operation_type == 'CREATE':
                if os.path.exists(operation.source_path):
                    if self.event_handler:
                        self.event_handler.skip_next_event(operation.source_path)
                    if os.path.isfile(operation.source_path):
                        os.remove(operation.source_path)
                    else:
                        shutil.rmtree(operation.source_path)
                        
            return True
            
        except Exception as e:
            logger.error(f"执行撤销操作失败: {e}")
            return False
    
    def undo_all_operations(self) -> bool:
        """撤销所有操作"""
        success = True
        while self.operations and success:
            success = self.undo_last_operation()
        return success
    
    def undo_script_operations(self, script_name: str) -> bool:
        """撤销指定脚本的所有操作"""
        try:
            # 找出指定脚本的所有操作
            script_ops = [op for op in reversed(self.operations) 
                         if op.script_name == script_name]
            
            if not script_ops:
                logger.warning(f"没有找到脚本 {script_name} 的操作记录")
                return False
            
            # 逐个撤销操作
            success = True
            for op in script_ops:
                if self._undo_operation(op):
                    self.operations.remove(op)
                else:
                    success = False
                    break
            
            if success:
                self._save_history()
                logger.info(f"已撤销脚本 {script_name} 的所有操作")
            
            return success
            
        except Exception as e:
            logger.error(f"撤销脚本操作失败: {e}")
            return False
    
    def get_operation_history(self, script_name: Optional[str] = None) -> List[dict]:
        """获取操作历史"""
        try:
            if script_name:
                return [op.to_dict() for op in self.operations 
                        if op.script_name == script_name]
            return [op.to_dict() for op in self.operations]
        except Exception as e:
            logger.error(f"获取操作历史失败: {e}")
            return []

def init_file_monitor(paths: Union[str, List[str]] = None):
    """初始化文件监控器"""
    monitor = FileOperationMonitor()
    monitor.start_monitoring(paths)
    return monitor

# 示例使用方法
if __name__ == "__main__":
    # 初始化监控器
    monitor = init_file_monitor()
    
    try:
        # 示例：创建文件
        with open("test.txt", "w") as f:
            f.write("Hello, World!")
        
        # 示例：移动文件
        os.rename("test.txt", "test2.txt")
        
        # 示例：删除文件
        os.remove("test2.txt")
        
        # 等待一段时间，确保操作被记录
        time.sleep(1)
        
        # 显示操作历史
        print("\n操作历史:")
        for op in monitor.get_operation_history():
            print(f"{op['operation_type']}: {op['source_path']}")
        
        # 撤销所有操作
        print("\n撤销操作:")
        monitor.undo_all_operations()
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
    finally:
        # 停止监控
        monitor.stop_monitoring() 
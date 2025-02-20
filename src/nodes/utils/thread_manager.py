import os
import logging
import yaml
import psutil
from queue import Queue
from threading import Event, Lock
import watchdog.events
import watchdog.observers

logger = logging.getLogger(__name__)

class ConfigFileHandler(watchdog.events.FileSystemEventHandler):
    def __init__(self, config_path, callback):
        self.config_path = os.path.abspath(config_path)
        self.callback = callback

    def on_modified(self, event):
        if event.src_path == self.config_path:
            self.callback()

class ThreadManager:
    def __init__(self, config_path="config.yaml"):
        self.config_path = config_path
        self.config = self.load_config()
        self.processing_queue = Queue(maxsize=self.config.get('queue_size', 100))
        self.completion_queue = Queue()
        self.stop_event = Event()
        self.lock = Lock()
        
        # 启动配置文件监控
        self.observer = watchdog.observers.Observer()
        handler = ConfigFileHandler(config_path, self.reload_config)
        self.observer.schedule(handler, os.path.dirname(config_path), recursive=False)
        self.observer.start()

    def load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return {
                'performance_mode': 'normal',
                'thread_config': {
                    'normal': {
                        'max_threads': 4,
                        'memory_multiplier': 2,
                        'cpu_multiplier': 2,
                        'max_total_threads': 8
                    }
                },
                'memory_limit': 75,
                'queue_size': 100,
                'batch_size': 10
            }

    def reload_config(self):
        with self.lock:
            self.config = self.load_config()
            logger.info(f"配置已重新加载: 性能模式={self.config['performance_mode']}")

    def get_optimal_thread_count(self, image_count):
        with self.lock:
            try:
                mode = self.config['performance_mode']
                thread_config = self.config['thread_config'][mode]
                
                cpu_count = os.cpu_count() or 4
                available_memory = psutil.virtual_memory().available / (1024 * 1024 * 1024)
                
                # 根据配置计算线程数
                cpu_based_threads = cpu_count * thread_config['cpu_multiplier']
                memory_based_threads = int(available_memory * thread_config['memory_multiplier'])
                
                # 考虑图片数量
                if image_count <= thread_config['max_threads']:
                    thread_count = image_count
                else:
                    thread_count = min(
                        thread_config['max_threads'],
                        cpu_based_threads,
                        memory_based_threads,
                        thread_config['max_total_threads']
                    )
                
                return max(1, thread_count)
            except Exception as e:
                logger.error(f"计算线程数时出错: {e}")
                return 2

    def get_batch_size(self):
        with self.lock:
            return self.config.get('batch_size', 10)

    def cleanup(self):
        self.stop_event.set()
        self.observer.stop()
        self.observer.join() 
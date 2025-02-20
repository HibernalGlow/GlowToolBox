# irm https://raw.githubusercontent.com/yuaotian/go-cursor-help/master/scripts/install.ps1 | iex
import tkinter as tk
from tkinter import ttk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
import time
from datetime import datetime, timedelta
import json
import os
import portalocker  # 替换fcntl

# 性能配置
# 可以直接修改这个文件来实时调整性能
# 修改后会立即生效，无需重启程序

# 全局配置路径
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'performance_config.json')

DEFAULT_CONFIG = {
    "thread_count": 1,
    "batch_size": 1,
    "start_time": datetime.now().isoformat()  # 添加启动时间戳
}

def get_config():
    """获取整个配置文件内容"""
    try:
        with open(CONFIG_FILE, 'r+', encoding='utf-8') as f:
            portalocker.lock(f, portalocker.LOCK_SH)  # 共享锁
            try:
                config = json.load(f)
                # 添加自动清理
                cleanup_old_configs(config)
                return config
            except json.JSONDecodeError:
                return {}
            finally:
                portalocker.unlock(f)
    except FileNotFoundError:
        return {}

def get_thread_count():
    """获取当前进程的线程数"""
    pid = os.getpid()
    config = get_config()
    return max(1, min(config.get(str(pid), DEFAULT_CONFIG)['thread_count'], 16))

def get_batch_size():
    """获取当前进程的批处理大小"""
    pid = os.getpid()
    config = get_config()
    return max(1, min(config.get(str(pid), DEFAULT_CONFIG)['batch_size'], 100))

# 运行状态控制
IS_PAUSED = False
END_TIME = None

class ConfigGUI:
    def __init__(self):
        self.pid = os.getpid()
        # 初始化当前进程配置
        self._init_config()
        
        self.root = ttk.Window(
            title="性能配置调整器",
            themename="cosmo",
            resizable=(True, True)
        )
        self.root.minsize(300, 200)  # 调整最小尺寸
        self.root.geometry("800x500")  # 调整初始尺寸
        
        # 创建主框架
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=BOTH, expand=YES, padx=20, pady=20)
        
        # 调整grid布局的行数
        self.main_frame.grid_columnconfigure(0, weight=1)
        for i in range(4):  # 减少行数
            self.main_frame.grid_rowconfigure(i, weight=1)
        
        # 标题
        title_label = ttk.Label(
            self.main_frame,
            text="性能参数实时调整",
            font=("Helvetica", 16, "bold")
        )
        title_label.grid(row=0, column=0, pady=10, sticky="ew")
        
        # 线程数调整
        thread_frame = ttk.LabelFrame(
            self.main_frame,
            text="线程数 (1-16)",
            padding="10"
        )
        thread_frame.grid(row=1, column=0, sticky="nsew", pady=5)
        thread_frame.grid_columnconfigure(0, weight=1)
        
        self.thread_var = tk.IntVar(value=get_thread_count())
        self.thread_slider = ttk.Scale(
            thread_frame,
            from_=1,
            to=16,
            variable=self.thread_var,
            command=self.update_thread_count
        )
        self.thread_slider.grid(row=0, column=0, sticky="ew", padx=5)
        
        self.thread_label = ttk.Label(
            thread_frame,
            text=f"当前值: {self.thread_var.get()}"
        )
        self.thread_label.grid(row=1, column=0, pady=(5,0))
        
        # 批处理大小调整
        batch_frame = ttk.LabelFrame(
            self.main_frame,
            text="批处理大小 (1-100)",
            padding="10"
        )
        batch_frame.grid(row=2, column=0, sticky="nsew", pady=5)
        batch_frame.grid_columnconfigure(0, weight=1)
        
        self.batch_var = tk.IntVar(value=get_batch_size())
        self.batch_slider = ttk.Scale(
            batch_frame,
            from_=1,
            to=100,
            variable=self.batch_var,
            command=self.update_batch_size
        )
        self.batch_slider.grid(row=0, column=0, sticky="ew", padx=5)
        
        self.batch_label = ttk.Label(
            batch_frame,
            text=f"当前值: {self.batch_var.get()}"
        )
        self.batch_label.grid(row=1, column=0, pady=(5,0))

        # 添加预设模式按钮框架
        preset_frame = ttk.Frame(self.main_frame)
        preset_frame.grid(row=3, column=0, sticky="nsew", pady=10)
        
        # 三个预设按钮
        ttk.Button(
            preset_frame,
            text="低配模式",
            command=lambda: self.set_preset(1, 1),
            bootstyle="secondary"
        ).pack(side=LEFT, expand=YES, padx=5)
        
        ttk.Button(
            preset_frame,
            text="中配模式",
            command=lambda: self.set_preset(8, 8),
            bootstyle="info"
        ).pack(side=LEFT, expand=YES, padx=5)
        
        ttk.Button(
            preset_frame,
            text="高配模式",
            command=lambda: self.set_preset(16, 16),
            bootstyle="primary"
        ).pack(side=LEFT, expand=YES, padx=5)

        # 状态标签
        self.status_label = ttk.Label(
            self.main_frame,
            text="✓ 配置已同步",
            bootstyle="success"
        )
        self.status_label.grid(row=4, column=0, pady=10, sticky="ew")
        
        # 启动自动保存线程
        self.save_thread = threading.Thread(target=self.auto_save, daemon=True)
        self.save_thread.start()
    
    def _init_config(self):
        """初始化当前进程配置"""
        config = get_config()
        if str(self.pid) not in config:
            self._update_config(DEFAULT_CONFIG)

    def _update_config(self, new_values):
        """更新当前进程配置"""
        with open(CONFIG_FILE, 'a+', encoding='utf-8') as f:
            portalocker.lock(f, portalocker.LOCK_EX)  # 排他锁
            try:
                f.seek(0)
                content = f.read()
                config = json.loads(content) if content else {}
                # 添加清理逻辑
                cleanup_old_configs(config)
                config[str(self.pid)] = {
                    **config.get(str(self.pid), DEFAULT_CONFIG),
                    **new_values
                }
                f.seek(0)
                f.truncate()
                json.dump(config, f, indent=2)
            except json.JSONDecodeError:
                config = {str(self.pid): DEFAULT_CONFIG}
                json.dump(config, f, indent=2)
            finally:
                portalocker.unlock(f)

    def update_thread_count(self, *args):
        self.thread_label.config(text=f"当前值: {self.thread_var.get()}")
        self.show_saving_status()
        
    def update_batch_size(self, *args):
        self.batch_label.config(text=f"当前值: {self.batch_var.get()}")
        self.show_saving_status()
    
    def show_saving_status(self):
        self.status_label.config(text="⟳ 正在保存...", bootstyle="warning")
        
    def save_config(self):
        """保存当前进程配置"""
        self._update_config({
            "thread_count": self.thread_var.get(),
            "batch_size": self.batch_var.get()
        })
        self.status_label.config(text="✓ 配置已同步", bootstyle="success")
    
    def auto_save(self):
        """自动保存配置的后台线程"""
        while True:
            time.sleep(0.5)  # 延迟保存，避免频繁写入
            self.save_config()
    
    def set_preset(self, threads, batch_size):
        """设置预设配置"""
        self.thread_var.set(threads)
        self.batch_var.set(batch_size)
        self.thread_label.config(text=f"当前值: {threads}")
        self.batch_label.config(text=f"当前值: {batch_size}")
        self.show_saving_status()
    
    def run(self):
        self.root.mainloop()

def cleanup_old_configs(config):
    """清理超过24小时的非活跃配置"""
    now = datetime.now()
    expired_pids = []
    
    for pid_str in list(config.keys()):
        try:
            # 仅通过时间戳判断，避免进程检查的兼容性问题
            start_time = datetime.fromisoformat(config[pid_str].get('start_time', now.isoformat()))
            if (now - start_time) > timedelta(hours=6):
                expired_pids.append(pid_str)
        except Exception:
            continue
    
    # 删除过期配置
    for pid in expired_pids:
        del config[pid]

if __name__ == "__main__":
    app = ConfigGUI()
    app.run() 
import os
import time
import logging
import platform
import ctypes
import tkinter as tk
from datetime import datetime
from threading import Thread, Event
from tkinter import ttk, scrolledtext
import win32gui
import win32con
import win32process
import win32api

# 配置日志
logging.basicConfig(
    filename='recycle_bin_cleaner.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

# Windows API 常量
SHERB_NOCONFIRMATION = 0x00000001
SHERB_NOPROGRESSUI = 0x00000002
SHERB_NOSOUND = 0x00000004

def hide_console():
    """使用更安全的方式隐藏命令行窗口"""
    try:
        # 获取当前进程ID
        pid = win32api.GetCurrentProcessId()
        # 枚举所有窗口，找到属于当前进程的控制台窗口
        def callback(hwnd, hwnds):
            if win32gui.IsWindowVisible(hwnd):
                _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                if found_pid == pid:
                    # 检查窗口类名来确认是否为控制台窗口
                    class_name = win32gui.GetClassName(hwnd)
                    if class_name == "ConsoleWindowClass":
                        hwnds.append(hwnd)
            return True
        
        hwnds = []
        win32gui.EnumWindows(callback, hwnds)
        
        # 隐藏找到的控制台窗口
        for hwnd in hwnds:
            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
    except Exception as e:
        logging.error(f"隐藏控制台窗口时出错: {e}")

class GUILogHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert('end', msg + '\n')
            self.text_widget.see('end')
            self.text_widget.configure(state='disabled')
        self.text_widget.after(0, append)

class RecycleBinCleaner:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("回收站清理工具")
        self.root.geometry("500x400")
        
        self.stop_event = Event()
        self.paused = Event()
        self.cleaning_thread = None
        self.CLEAN_INTERVAL = 10  # 清理间隔（秒）
        self.last_bin_empty = False  # 跟踪上一次回收站是否为空
        
        self.setup_ui()
        self.setup_logging()
        
    def setup_logging(self):
        # 配置GUI日志处理器
        self.log_handler = GUILogHandler(self.log_text)
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        logging.getLogger().addHandler(self.log_handler)
        logging.getLogger().setLevel(logging.INFO)
        
    def setup_ui(self):
        # 创建样式
        style = ttk.Style()
        style.configure("TButton", padding=5)
        
        # 状态标签
        self.status_label = ttk.Label(self.root, text="状态: 未启动", font=("微软雅黑", 10))
        self.status_label.pack(pady=10)
        
        # 按钮框架
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=5)
        
        # 启动按钮
        self.start_btn = ttk.Button(btn_frame, text="启动", command=self.start_cleaning)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        # 暂停/恢复按钮
        self.pause_btn = ttk.Button(btn_frame, text="暂停", command=self.toggle_pause)
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        self.pause_btn["state"] = "disabled"
        
        # 重启按钮
        self.restart_btn = ttk.Button(btn_frame, text="重启", command=self.restart_cleaning)
        self.restart_btn.pack(side=tk.LEFT, padx=5)
        self.restart_btn["state"] = "disabled"
        
        # 停止按钮
        self.stop_btn = ttk.Button(btn_frame, text="停止", command=self.stop_cleaning)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn["state"] = "disabled"
        
        # 日志显示区域
        log_frame = ttk.LabelFrame(self.root, text="运行日志", padding=5)
        log_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=50, font=("微软雅黑", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.configure(state='disabled')

    def empty_recycle_bin(self):
        """清空回收站"""
        try:
            shell32 = ctypes.windll.shell32
            flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
            result = shell32.SHEmptyRecycleBinW(None, None, flags)
            if result == 0:
                self.last_bin_empty = False  # 重置状态
                logging.info("回收站已清空")
                return True
            elif result == -2147418113:  # 回收站为空时的错误码
                if not self.last_bin_empty:  # 只在状态改变时输出日志
                    logging.info("回收站已经是空的")
                    self.last_bin_empty = True
                return True
            else:
                self.last_bin_empty = False  # 重置状态
                logging.error(f"清空回收站失败，错误码: {result}")
                return False
        except Exception as e:
            self.last_bin_empty = False  # 重置状态
            logging.error(f"清空回收站时出错: {e}")
            return False

    def cleaning_loop(self):
        logging.info("自动清理服务已启动")
        last_paused_state = False
        
        while not self.stop_event.is_set():
            current_paused_state = self.paused.is_set()
            
            if not current_paused_state:
                self.empty_recycle_bin()
                self.root.after(0, lambda: self.status_label.config(text="状态: 运行中"))
            else:
                if not last_paused_state:  # 只在刚暂停时输出一次日志
                    self.root.after(0, lambda: self.status_label.config(text="状态: 已暂停"))
                    logging.info("服务已暂停")
            
            last_paused_state = current_paused_state
            
            # 每秒检查一次暂停状态
            for _ in range(self.CLEAN_INTERVAL):
                if self.stop_event.is_set():
                    break
                time.sleep(1)
        
        logging.info("服务已停止")
        self.root.after(0, self.reset_ui)

    def restart_cleaning(self):
        """重新启动清理服务"""
        logging.info("正在重新启动服务...")
        self.stop_cleaning()  # 停止当前任务
        self.start_cleaning() # 启动新任务

    def start_cleaning(self):
        if not self.cleaning_thread or not self.cleaning_thread.is_alive():
            self.stop_event.clear()
            self.paused.clear()
            self.cleaning_thread = Thread(target=self.cleaning_loop)
            self.cleaning_thread.daemon = True
            self.cleaning_thread.start()
            
            self.start_btn["state"] = "disabled"
            self.pause_btn["state"] = "normal"
            self.restart_btn["state"] = "normal"
            self.stop_btn["state"] = "normal"
            self.status_label.config(text="状态: 运行中")

    def toggle_pause(self):
        if self.paused.is_set():
            self.paused.clear()
            self.pause_btn["text"] = "暂停"
            self.status_label.config(text="状态: 运行中")
            logging.info("服务已恢复")
        else:
            self.paused.set()
            self.pause_btn["text"] = "恢复"
            self.status_label.config(text="状态: 已暂停")

    def stop_cleaning(self):
        self.stop_event.set()
        if self.cleaning_thread:
            self.cleaning_thread.join()
        self.reset_ui()

    def reset_ui(self):
        self.start_btn["state"] = "normal"
        self.pause_btn["state"] = "disabled"
        self.restart_btn["state"] = "disabled"
        self.stop_btn["state"] = "disabled"
        self.pause_btn["text"] = "暂停"
        self.status_label.config(text="状态: 已停止")

    def run(self):
        if platform.system() != "Windows":
            self.status_label.config(text="错误: 此程序只支持Windows系统")
            logging.error("此程序只支持Windows系统")
            return
            
        self.root.mainloop()

def main():
    hide_console()  # 启动后立即隐藏命令行窗口
    app = RecycleBinCleaner()
    app.run()

if __name__ == "__main__":
    main()
import os
import time
import logging
import platform
import ctypes
from datetime import datetime
from threading import Thread, Event
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap import ScrolledText
import win32gui
import win32con
import win32process
import win32api

# Windows API 常量
SHERB_NOCONFIRMATION = 0x00000001
SHERB_NOPROGRESSUI = 0x00000002
SHERB_NOSOUND = 0x00000004

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
        self.root = ttk.Window(
            title="回收站清理工具",
            themename="cosmo",
            size=(600, 500),
            resizable=(True, True)
        )
        self.root.place_window_center()
        
        self.stop_event = Event()
        self.paused = Event()
        self.cleaning_thread = None
        self.CLEAN_INTERVAL = 10  # 默认清理间隔（秒）
        self.last_bin_empty = False
        
        self.setup_ui()
        self.setup_logging()
        
    def setup_logging(self):
        self.log_handler = GUILogHandler(self.log_text)
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        logging.getLogger().addHandler(self.log_handler)
        logging.getLogger().setLevel(logging.INFO)
        
    def setup_ui(self):
        # 主容器
        main_container = ttk.Frame(self.root, padding=10)
        main_container.pack(fill=BOTH, expand=YES)
        
        # 顶部状态区域
        status_frame = ttk.Frame(main_container)
        status_frame.pack(fill=X, pady=(0, 10))
        
        self.status_label = ttk.Label(
            status_frame,
            text="状态: 未启动",
            font=("微软雅黑", 10),
            bootstyle="info"
        )
        self.status_label.pack(side=LEFT)
        
        # 间隔调整区域
        interval_frame = ttk.Labelframe(
            main_container,
            text="清理间隔设置",
            padding=10,
            bootstyle="info"
        )
        interval_frame.pack(fill=X, pady=(0, 10))
        
        self.interval_value = ttk.Label(
            interval_frame,
            text=f"当前间隔: {self.CLEAN_INTERVAL} 秒",
            bootstyle="info"
        )
        self.interval_value.pack(side=TOP, pady=(0, 5))
        
        self.interval_scale = ttk.Scale(
            interval_frame,
            from_=5,
            to=300,
            value=self.CLEAN_INTERVAL,
            length=250,
            command=self.update_interval,
            bootstyle="info"
        )
        self.interval_scale.pack(fill=X)
        
        # 按钮区域
        btn_frame = ttk.Frame(main_container)
        btn_frame.pack(fill=X, pady=(0, 10))
        
        self.start_btn = ttk.Button(
            btn_frame,
            text="启动",
            command=self.start_cleaning,
            width=10,
            bootstyle="success"
        )
        self.start_btn.pack(side=LEFT, padx=5)
        
        self.pause_btn = ttk.Button(
            btn_frame,
            text="暂停",
            command=self.toggle_pause,
            width=10,
            state="disabled",
            bootstyle="warning"
        )
        self.pause_btn.pack(side=LEFT, padx=5)
        
        self.restart_btn = ttk.Button(
            btn_frame,
            text="重启",
            command=self.restart_cleaning,
            width=10,
            state="disabled",
            bootstyle="info"
        )
        self.restart_btn.pack(side=LEFT, padx=5)
        
        self.stop_btn = ttk.Button(
            btn_frame,
            text="停止",
            command=self.stop_cleaning,
            width=10,
            state="disabled",
            bootstyle="danger"
        )
        self.stop_btn.pack(side=LEFT, padx=5)
        
        # 日志区域
        log_frame = ttk.Labelframe(
            main_container,
            text="运行日志",
            padding=10,
            bootstyle="info"
        )
        log_frame.pack(fill=BOTH, expand=YES)
        
        self.log_text = ScrolledText(
            log_frame,
            height=15,
            wrap=WORD,
            font=("微软雅黑", 9)
        )
        self.log_text.pack(fill=BOTH, expand=YES)
        self.log_text.configure(state='disabled')

    def update_interval(self, value):
        """更新清理间隔"""
        self.CLEAN_INTERVAL = int(float(value))
        self.interval_value.configure(text=f"当前间隔: {self.CLEAN_INTERVAL} 秒")

    def empty_recycle_bin(self):
        """清空回收站"""
        try:
            shell32 = ctypes.windll.shell32
            flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
            result = shell32.SHEmptyRecycleBinW(None, None, flags)
            if result == 0:
                self.last_bin_empty = False
                logging.info("回收站已清空")
                return True
            elif result == -2147418113:
                if not self.last_bin_empty:
                    logging.info("回收站已经是空的")
                    self.last_bin_empty = True
                return True
            else:
                self.last_bin_empty = False
                logging.error(f"清空回收站失败，错误码: {result}")
                return False
        except Exception as e:
            self.last_bin_empty = False
            logging.error(f"清空回收站时出错: {e}")
            return False

    def cleaning_loop(self):
        logging.info("自动清理服务已启动")
        last_paused_state = False
        
        while not self.stop_event.is_set():
            current_paused_state = self.paused.is_set()
            
            if not current_paused_state:
                self.empty_recycle_bin()
                self.root.after(0, lambda: self.status_label.configure(
                    text="状态: 运行中",
                    bootstyle="success"
                ))
            else:
                if not last_paused_state:
                    self.root.after(0, lambda: self.status_label.configure(
                        text="状态: 已暂停",
                        bootstyle="warning"
                    ))
                    logging.info("服务已暂停")
            
            last_paused_state = current_paused_state
            
            for _ in range(self.CLEAN_INTERVAL):
                if self.stop_event.is_set():
                    break
                time.sleep(1)
        
        logging.info("服务已停止")
        self.root.after(0, self.reset_ui)

    def restart_cleaning(self):
        logging.info("正在重新启动服务...")
        self.stop_cleaning()
        self.start_cleaning()

    def start_cleaning(self):
        if not self.cleaning_thread or not self.cleaning_thread.is_alive():
            self.stop_event.clear()
            self.paused.clear()
            self.cleaning_thread = Thread(target=self.cleaning_loop)
            self.cleaning_thread.daemon = True
            self.cleaning_thread.start()
            
            self.start_btn.configure(state="disabled")
            self.pause_btn.configure(state="normal")
            self.restart_btn.configure(state="normal")
            self.stop_btn.configure(state="normal")
            self.status_label.configure(
                text="状态: 运行中",
                bootstyle="success"
            )

    def toggle_pause(self):
        if self.paused.is_set():
            self.paused.clear()
            self.pause_btn.configure(text="暂停")
            self.status_label.configure(
                text="状态: 运行中",
                bootstyle="success"
            )
            logging.info("服务已恢复")
        else:
            self.paused.set()
            self.pause_btn.configure(text="恢复")
            self.status_label.configure(
                text="状态: 已暂停",
                bootstyle="warning"
            )

    def stop_cleaning(self):
        self.stop_event.set()
        if self.cleaning_thread:
            self.cleaning_thread.join()
        self.reset_ui()

    def reset_ui(self):
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled")
        self.restart_btn.configure(state="disabled")
        self.stop_btn.configure(state="disabled")
        self.pause_btn.configure(text="暂停")
        self.status_label.configure(
            text="状态: 已停止",
            bootstyle="danger"
        )

    def run(self):
        if platform.system() != "Windows":
            self.status_label.configure(
                text="错误: 此程序只支持Windows系统",
                bootstyle="danger"
            )
            logging.error("此程序只支持Windows系统")
            return
            
        self.root.mainloop()

def hide_console():
    """使用更安全的方式隐藏命令行窗口"""
    try:
        pid = win32api.GetCurrentProcessId()
        def callback(hwnd, hwnds):
            if win32gui.IsWindowVisible(hwnd):
                _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                if found_pid == pid:
                    class_name = win32gui.GetClassName(hwnd)
                    if class_name == "ConsoleWindowClass":
                        hwnds.append(hwnd)
            return True
        
        hwnds = []
        win32gui.EnumWindows(callback, hwnds)
        
        for hwnd in hwnds:
            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
    except Exception as e:
        logging.error(f"隐藏控制台窗口时出错: {e}")

def main():
    hide_console()
    app = RecycleBinCleaner()
    app.run()

if __name__ == "__main__":
    main() 
import sys
import time
import pyperclip
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime
import os
from colorama import init, Fore, Style

# 初始化colorama
init()

class FileChangeHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            print(f"{Fore.GREEN}[{self._get_time()}] 新建文件夹: {event.src_path}{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}[{self._get_time()}] 新建文件: {event.src_path}{Style.RESET_ALL}")

    def on_deleted(self, event):
        if event.is_directory:
            print(f"{Fore.RED}[{self._get_time()}] 删除文件夹: {event.src_path}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}[{self._get_time()}] 删除文件: {event.src_path}{Style.RESET_ALL}")

    def on_modified(self, event):
        if not event.is_directory:
            print(f"{Fore.YELLOW}[{self._get_time()}] 修改文件: {event.src_path}{Style.RESET_ALL}")

    def on_moved(self, event):
        if event.is_directory:
            print(f"{Fore.BLUE}[{self._get_time()}] 移动/重命名文件夹: \n从: {event.src_path}\n到: {event.dest_path}{Style.RESET_ALL}")
        else:
            print(f"{Fore.BLUE}[{self._get_time()}] 移动/重命名文件: \n从: {event.src_path}\n到: {event.dest_path}{Style.RESET_ALL}")

    def _get_time(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def main():
    # 尝试从剪贴板获取路径，如果为空则使用默认路径
    path = pyperclip.paste().strip()
    if not path or not os.path.exists(path):
        path = r"E:\1EHV"
    
    if not os.path.exists(path):
        print(f"{Fore.RED}错误：路径 {path} 不存在！{Style.RESET_ALL}")
        return

    print(f"{Fore.CYAN}开始监控路径: {path}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}按 Ctrl+C 停止监控...{Style.RESET_ALL}")

    event_handler = FileChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print(f"\n{Fore.YELLOW}停止监控...{Style.RESET_ALL}")
    
    observer.join()

if __name__ == "__main__":
    main() 
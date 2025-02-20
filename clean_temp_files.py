import os
import sys
import time
import psutil
from pathlib import Path

def is_file_locked(filepath):
    """检查文件是否被占用"""
    try:
        # 尝试以写入模式打开文件
        with open(filepath, 'a'):
            return False
    except IOError:
        return True

def clean_temp_files(directory):
    """清理指定目录下的.bak和.temp文件"""
    directory = Path(directory)
    if not directory.exists():
        print(f"目录 {directory} 不存在!")
        return

    # 要清理的文件扩展名
    extensions = ('.bak', '.temp')
    
    files_cleaned = 0
    # 遍历目录
    for file_path in directory.rglob('*'):
        if file_path.suffix.lower() in extensions:
            try:
                if not is_file_locked(file_path):
                    file_path.unlink()
                    files_cleaned += 1
                    print(f"已删除文件: {file_path}")
                else:
                    print(f"文件被占用，无法删除: {file_path}")
            except Exception as e:
                print(f"删除文件 {file_path} 时出错: {e}")
    return files_cleaned

def main():
    if len(sys.argv) != 2:
        print("使用方法: python clean_temp_files.py <目录路径>")
        sys.exit(1)
    
    target_dir = sys.argv[1]
    interval = 300  # 默认5分钟检查一次
    
    print(f"开始监控目录: {target_dir}")
    print(f"检查间隔: {interval}秒")
    print("按Ctrl+C退出程序")
    
    try:
        while True:
            print("\n" + "-" * 50)
            print(f"开始清理检查 - {time.strftime('%Y-%m-%d %H:%M:%S')}")
            files_cleaned = clean_temp_files(target_dir)
            print(f"本次清理完成! 共删除{files_cleaned}个文件")
            print(f"等待{interval}秒后进行下一次检查...")
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n程序已停止运行!")

if __name__ == "__main__":
    main() 
import os
import sys
from datetime import datetime

def get_latest_timestamp(path):
    """获取文件夹中最新的时间戳"""
    latest_time = os.path.getmtime(path)
    
    # 遍历所有子文件和子文件夹
    for root, dirs, files in os.walk(path):
        # 检查所有文件的时间戳
        for file in files:
            file_path = os.path.join(root, file)
            file_time = os.path.getmtime(file_path)
            latest_time = max(latest_time, file_time)
        
        # 检查所有子文件夹的时间戳
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            dir_time = os.path.getmtime(dir_path)
            latest_time = max(latest_time, dir_time)
    
    return latest_time

def update_folder_timestamp(folder_path):
    """更新文件夹的时间戳"""
    try:
        latest_time = get_latest_timestamp(folder_path)
        # 更新文件夹的访问时间和修改时间
        os.utime(folder_path, (latest_time, latest_time))
        print(f"已更新文件夹时间戳: {folder_path}")
        print(f"新的时间戳: {datetime.fromtimestamp(latest_time)}")
    except Exception as e:
        print(f"处理文件夹时出错 {folder_path}: {str(e)}")

def main():
    folder_paths = []
    
    # 检查是否有命令行参数
    if len(sys.argv) > 1:
        folder_paths = sys.argv[1:]
    else:
        print("请输入文件夹路径（每行一个，空行结束）:")
        while True:
            line = input().strip().strip('"')
            if not line:
                break
            folder_paths.append(line)
    
    if not folder_paths:
        print("未提供任何文件夹路径")
        sys.exit(1)
    
    # 处理所有输入的文件夹路径
    for folder_path in folder_paths:
        if os.path.isdir(folder_path):
            update_folder_timestamp(folder_path)
        else:
            print(f"错误: {folder_path} 不是一个有效的文件夹路径")

if __name__ == "__main__":
    main() 
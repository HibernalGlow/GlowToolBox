import os
from send2trash import send2trash
import logging
from tqdm import tqdm

# 配置日志
logging.basicConfig(filename='remove_empty_folders.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def remove_empty_folders(path):
    if not os.path.isdir(path):
        return

    # 获取所有文件夹
    all_folders = []
    for root, dirs, files in os.walk(path, topdown=False):
        for name in dirs:
            folder_path = os.path.join(root, name)
            all_folders.append(folder_path)

    # 遍历所有文件夹并删除空文件夹
    for folder_path in tqdm(all_folders, desc="Removing empty folders", unit="folder"):
        if not os.listdir(folder_path):
            send2trash(folder_path)
            logging.info(f"Moved empty folder to trash: {folder_path}")
            print(f"Moved empty folder to trash: {folder_path}")

# 指定要删除空文件夹的根目录路径
root_folder = input("请输入要处理的文件夹或压缩包完整路径: ").strip().strip('"')

# 调用函数来删除空文件夹（包括各级子文件夹）
remove_empty_folders(root_folder)

print("done!")

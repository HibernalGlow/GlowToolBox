import os
import send2trash
import re
import logging
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

# 配置日志记录
logging.basicConfig(filename='delete_folders.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def clean_name(name):
    # 移除类似 [#a] 的标记
    return re.sub(r'\[#a\]', '', name)

def delete_folder(folder_path):
    try:
        send2trash.send2trash(folder_path)
        logging.info(f"成功删除文件夹: {folder_path}")
        return True
    except Exception as e:
        logging.error(f"删除文件夹失败: {folder_path} - 错误: {e}")
        return False

def collect_files_and_folders(path):
    """收集所有CBZ文件和文件夹"""
    cbz_files = {}
    folders_to_check = []
    
    print("正在扫描文件...")
    # 使用tqdm显示扫描进度
    for root, dirs, files in tqdm(list(os.walk(path))):
        # 收集CBZ文件
        for file in files:
            if file.lower().endswith('.cbz'):
                cbz_path = os.path.join(root, file)
                base_name = os.path.splitext(os.path.basename(file))[0]
                clean_cbz_name = clean_name(base_name)
                cbz_files[clean_cbz_name] = cbz_path
        
        # 收集文件夹
        for dir_name in dirs:
            folder_path = os.path.join(root, dir_name)
            folders_to_check.append((dir_name, folder_path))
    
    return cbz_files, folders_to_check

def delete_matching_folders(path):
    # 收集文件和文件夹信息
    cbz_files, folders_to_check = collect_files_and_folders(path)
    
    # 确定需要删除的文件夹
    folders_to_delete = []
    print("正在检查匹配的文件夹...")
    for dir_name, folder_path in tqdm(folders_to_check):
        clean_folder_name = clean_name(dir_name)
        if clean_folder_name in cbz_files:
            folders_to_delete.append(folder_path)
    
    if not folders_to_delete:
        print("没有找到需要删除的文件夹")
        return
    
    print(f"找到 {len(folders_to_delete)} 个需要删除的文件夹")
    
    # 使用多线程删除文件夹
    print("正在删除文件夹...")
    with ThreadPoolExecutor() as executor:
        list(tqdm(executor.map(delete_folder, folders_to_delete), 
                 total=len(folders_to_delete), 
                 desc="删除进度"))

if __name__ == "__main__":
    target_path = input("请输入要处理的目录路径: ")
    if os.path.exists(target_path):
        delete_matching_folders(target_path)
        print("处理完成！")
    else:
        print("目录不存在！")
import os
import shutil

def find_folder_in_target(folder_name, target_path):
    """递归查找目标路径下的同名文件夹"""
    for root, dirs, _ in os.walk(target_path):
        if folder_name in dirs:
            return os.path.join(root, folder_name)
    return None

def move_matching_folders():
    # 源目录路径
    source_path = r"D:\BaiduNetdiskDownload\test"
    
    # 获取用户输入的目标路径
    target_path = input("请输入目标路径: ").strip()
    
    # 检查目标路径是否存在
    if not os.path.exists(target_path):
        print(f"目标路径 {target_path} 不存在！")
        return
    
    # 获取源目录下的所有一级文件夹
    source_folders = [f for f in os.listdir(source_path) 
                     if os.path.isdir(os.path.join(source_path, f))]
    
    # 查找匹配的文件夹并移动
    moved_count = 0
    for folder in source_folders:
        # 在目标路径中递归查找同名文件夹
        matching_folder_path = find_folder_in_target(folder, target_path)
        
        if matching_folder_path:
            source_folder_path = os.path.join(source_path, folder)
            try:
                shutil.move(source_folder_path, matching_folder_path)
                print(f"已移动文件夹: {folder}")
                print(f"移动到: {matching_folder_path}")
                moved_count += 1
            except Exception as e:
                print(f"移动文件夹 {folder} 时出错: {str(e)}")
    
    print(f"\n完成! 共移动了 {moved_count} 个文件夹")

if __name__ == "__main__":
    move_matching_folders()
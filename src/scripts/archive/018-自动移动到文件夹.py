import os
import shutil

def move_zip_files(root_folder, new_folder_name):
    for folder_name in os.listdir(root_folder):
        folder_path = os.path.join(root_folder, folder_name)
        
        # 确认是文件夹
        if os.path.isdir(folder_path):
            # 创建新文件夹
            new_folder_path = os.path.join(folder_path, new_folder_name)
            os.makedirs(new_folder_path, exist_ok=True)
            
            # 遍历一级文件夹下的文件，检查是否是压缩文件
            # 遍历一级文件夹下的文件，检查是否是压缩文件
            for item_name in os.listdir(folder_path):
                item_path = os.path.join(folder_path, item_name)

                # 如果是文件且扩展名是压缩包
                if os.path.isfile(item_path) and item_name.endswith(('.zip', '.rar', '.7z')):
                    # 检查是否存在子文件夹
                    subfolder_found = any(os.path.isdir(os.path.join(folder_path, subfolder)) for subfolder in os.listdir(folder_path))

                    # 如果没有子文件夹，跳过处理
                    if not subfolder_found:
                        continue
                    
                    # 创建新文件夹
                    new_folder_path = os.path.join(folder_path, new_folder_name)
                    os.makedirs(new_folder_path, exist_ok=True)

                    # 移动压缩包到新文件夹
                    shutil.move(item_path, new_folder_path)
                    print(f"移动了文件: {item_name} 到 {new_folder_path}")

# 使用示例
root_folder = r"E:\1EHV"
new_folder_name = "1. 同人志"  # 自定义文件夹名称
move_zip_files(root_folder, new_folder_name)

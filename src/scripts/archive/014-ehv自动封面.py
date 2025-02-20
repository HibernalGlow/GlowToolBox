import os
import zipfile
import shutil

def get_largest_zip(folder_path):
    """
    找到文件夹中最大的 .zip 文件。

    参数:
    folder_path (str): 要搜索的文件夹路径。

    返回:
    str: 最大的 .zip 文件的路径，如果未找到则返回 None。
    """
    largest_size = 0
    largest_zip = None
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.zip'):
                file_path = os.path.join(root, file)
                size = os.path.getsize(file_path)
                if size > largest_size:
                    largest_size = size
                    largest_zip = file_path
    return largest_zip

def extract_first_image_from_zip(zip_path, destination_folder):
    """
    从指定的 .zip 文件中提取第一张图片到目标文件夹。

    参数:
    zip_path (str): .zip 文件的路径。
    destination_folder (str): 图片提取的目标文件夹路径。
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            image_files = sorted([f for f in zip_ref.namelist() if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.avif', '.jxl'))])
            if image_files:
                first_image = image_files[0]
                zip_ref.extract(first_image, destination_folder)
                # Move the image to the destination folder root
                extracted_path = os.path.join(destination_folder, first_image)
                final_path = os.path.join(destination_folder, os.path.basename(first_image))
                shutil.move(extracted_path, final_path)
                # 清理多余的目录结构
                extracted_dir = os.path.dirname(extracted_path)
                while extracted_dir != destination_folder:
                    try:
                        os.rmdir(extracted_dir)
                    except OSError as e:
                        if e.errno == 145:  # 目录不是空的
                            break
                        else:
                            raise
                    extracted_dir = os.path.dirname(extracted_dir)
    except zipfile.BadZipFile:
        print(f"损坏的压缩包: {zip_path}")

def process_folder(root_folder):
    """
    处理文件夹，如果子文件夹中没有图片，则从最大的 .zip 文件中提取第一张图片。

    参数:
    root_folder (str): 需要处理的根文件夹路径。
    """
    # 检查一级文件夹本身
    if os.path.isdir(root_folder):
        # 检查是否为隐藏文件夹
        if not root_folder.startswith('.') and not root_folder.startswith('{'):
            # 检查当前文件夹是否包含图片
            contains_image = any(file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.avif', '.jxl')) for file in os.listdir(root_folder))
            
            if not contains_image:
                largest_zip = get_largest_zip(root_folder)
                if largest_zip:
                    extract_first_image_from_zip(largest_zip, root_folder)
                else:
                    print(f"在 {root_folder} 中未找到压缩包")
            else:
                print(f"{root_folder} 包含图片，无需处理")
        else:
            print(f"跳过隐藏文件夹或特殊目录: {root_folder}")

    # 检查子文件夹
    for sub_folder in os.listdir(root_folder):
        sub_folder_path = os.path.join(root_folder, sub_folder)
        
        if os.path.isdir(sub_folder_path):
            # 检查是否为隐藏文件夹
            if not sub_folder.startswith('.') and not sub_folder.startswith('{'):
                # 检查当前文件夹是否包含图片
                contains_image = any(file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.avif', '.jxl')) for file in os.listdir(sub_folder_path))
                
                if not contains_image:
                    largest_zip = get_largest_zip(sub_folder_path)
                    if largest_zip:
                        extract_first_image_from_zip(largest_zip, sub_folder_path)
                    else:
                        print(f"在 {sub_folder_path} 中未找到压缩包")
                else:
                    print(f"{sub_folder_path} 包含图片，无需处理")
            else:
                print(f"跳过隐藏文件夹或特殊目录: {sub_folder_path}")
        else:
            print(f"{sub_folder_path} 不是文件夹，跳过")

# 使用示例
root_folder = input("请输入需要处理的根文件夹路径: ")
process_folder(root_folder)
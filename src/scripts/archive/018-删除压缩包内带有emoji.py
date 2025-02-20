import zipfile
import os
import subprocess

def delete_arrow_folder_contents(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # 获取压缩包内的所有文件和文件夹
        zip_contents = zip_ref.namelist()
        
        # 检查压缩包是否只有一个文件夹
        if len(zip_contents) == 1 and zip_contents[0].endswith('/'):
            print("压缩包只有一个文件夹，不进行删除操作。")
            return
        
        # 查找带有🏹图标的文件夹
        arrow_folder = None
        for item in zip_contents:
            if '🏹' in item and item.endswith('/'):
                arrow_folder = item
                break
        
        if not arrow_folder:
            print("压缩包内没有带有🏹图标的文件夹。")
            return
        
        # 删除带有🏹图标文件夹内的所有内容
        files_to_delete = [f for f in zip_contents if f.startswith(arrow_folder) and f != arrow_folder]
        for file_to_delete in files_to_delete:
            zip_contents.remove(file_to_delete)
        
        # 创建一个新的压缩包，只包含需要保留的文件
        temp_zip_path = zip_path + '.tmp'
        with zipfile.ZipFile(temp_zip_path, 'w') as new_zip:
            for item in zip_contents:
                new_zip.writestr(item, zip_ref.read(item))
    
    # 删除原压缩包并重命名新压缩包
    os.remove(zip_path)
    os.rename(temp_zip_path, zip_path)
    print("删除操作完成。")

# 使用示例
zip_path = input("请输入路径: ").strip().strip('"')  # 替换为你的压缩包路径
delete_arrow_folder_contents(zip_path)

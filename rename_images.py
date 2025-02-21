import os
import re
import zipfile
import tempfile
import shutil

def rename_images_in_directory(dir_path):
    # 遍历目录中的所有文件
    for root, dirs, files in os.walk(dir_path):
        for filename in files:
            if filename.lower().endswith(('.jpg', '.png', '.avif', '.jxl')):
                # 匹配文件名中的 [hash-xxxxxx] 模式
                new_filename = re.sub(r'\[hash-[0-9a-fA-F]+\]', '', filename)
                
                # 如果文件名发生了变化
                if new_filename != filename:
                    old_path = os.path.join(root, filename)
                    new_path = os.path.join(root, new_filename)
                    os.rename(old_path, new_path)

def rename_images_in_zip(zip_path):
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 打开压缩包
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # 解压到临时目录
            zip_ref.extractall(temp_dir)
        
        # 处理临时目录中的文件
        rename_images_in_directory(temp_dir)
        
        # 获取原始zip文件名（不含扩展名）和目录
        zip_dir = os.path.dirname(zip_path)
        zip_name = os.path.splitext(os.path.basename(zip_path))[0]
        
        # 创建新的zip文件
        new_zip_path = os.path.join(zip_dir, f"{zip_name}_renamed.zip")
        with zipfile.ZipFile(new_zip_path, 'w', zipfile.ZIP_DEFLATED) as new_zip:
            # 将处理后的文件添加到新的zip中
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    new_zip.write(file_path, arcname)
        
        print(f"压缩包处理完成！新文件保存为: {new_zip_path}")
        
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("使用方法: python rename_images.py <压缩包路径或文件夹路径>")
        sys.exit(1)
    
    target_path = sys.argv[1]
    if not os.path.exists(target_path):
        print(f"错误: 路径 '{target_path}' 不存在")
        sys.exit(1)
    
    if os.path.isdir(target_path):
        # 处理普通文件夹
        temp_dir = tempfile.mkdtemp()
        try:
            # 复制原文件夹到临时目录
            new_dir = shutil.copytree(target_path, os.path.join(temp_dir, "temp"))
            rename_images_in_directory(new_dir)
            
            # 创建输出目录
            output_dir = f"{target_path}_renamed"
            shutil.move(new_dir, output_dir)
            print(f"文件夹处理完成！新文件夹保存为: {output_dir}")
        finally:
            shutil.rmtree(temp_dir)
    elif zipfile.is_zipfile(target_path):
        rename_images_in_zip(target_path)
    else:
        print("错误: 输入路径必须是有效的压缩包或文件夹")
        sys.exit(1) 
import os
import shutil
from pathlib import Path

def get_image_files(folder_path):
    """获取指定文件夹中的所有图片文件"""
    image_files = []
    extensions = ['.jpg', '.jpeg', '.png', '.avif', '.jxl', '.gif', '.webp']
    for ext in extensions:
        image_files.extend(folder_path.glob(f'*{ext}'))
    return image_files

def group_files_by_name(files):
    """将文件按文件名分组"""
    file_groups = {}
    for file in files:
        name = file.stem
        if name not in file_groups:
            file_groups[name] = []
        file_groups[name].append(file)
    return file_groups

def move_files(files_to_move, src_path, dst_path):
    """移动文件到目标路径"""
    for file in files_to_move:
        rel_path = file.relative_to(src_path)
        dst_file = dst_path / rel_path
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(file), str(dst_file))
        print(f'已移动: {file} -> {dst_file}')

def process_images(src_path, dst_path, keep_formats=('.avif', '.jxl', '.gif')):
    """处理图片文件,保留指定格式,移动其他格式到目标路径"""
    src_path = Path(src_path)
    dst_path = Path(dst_path)
    
    # 递归处理所有子文件夹
    for folder in [src_path, *src_path.rglob('*')]:
        if not folder.is_dir():
            continue
            
        # 获取当前文件夹中的图片文件
        image_files = get_image_files(folder)
        
        # 按文件名分组
        file_groups = group_files_by_name(image_files)
        
        # 处理每组同名文件
        for name, files in file_groups.items():
            if len(files) > 1:  # 只处理有重名的文件
                keep_files = [f for f in files if f.suffix.lower() in keep_formats]
                move_files = [f for f in files if f.suffix.lower() not in keep_formats]
                
                if keep_files:
                    move_files(move_files, src_path, dst_path)

if __name__ == '__main__':
    # 获取用户输入
    src_path = input('请输入源文件夹路径: ').strip()
    dst_path = input('请输入目标文件夹路径: ').strip()
    
    # 设置要保留的格式
    keep_formats = ('.avif', '.jxl', '.gif')
    
    # 处理文件
    process_images(src_path, dst_path, keep_formats)
    print('处理完成!')
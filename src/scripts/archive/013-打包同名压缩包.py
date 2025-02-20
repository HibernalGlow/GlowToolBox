import os
import zipfile
import shutil
from pathlib import Path

# 支持的文件扩展名
VIDEO_EXTS = ['.mp4', '.mkv', '.avi', '.wmv']
SUBTITLE_EXTS = ['.srt', '.ass', '.ssa']
IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.gif']

def pack_related_files(video_path):
    """
    将视频文件及其相关的同名字幕和图片文件打包
    """
    video_path = Path(video_path)
    base_name = video_path.stem
    parent_dir = video_path.parent
    
    print(f"\n处理文件：{video_path}")
    
    # 创建临时文件夹
    temp_dir = parent_dir / f"{base_name}_temp"
    temp_dir.mkdir(exist_ok=True)
    print(f"创建临时目录：{temp_dir}")
    
    # 收集相关文件
    related_files = []
    for file in parent_dir.iterdir():
        if file.stem == base_name:
            if (file.suffix.lower() in VIDEO_EXTS or 
                file.suffix.lower() in SUBTITLE_EXTS or 
                file.suffix.lower() in IMAGE_EXTS):
                related_files.append(file)
    
    if not related_files:
        print("未找到相关文件，跳过处理")
        shutil.rmtree(temp_dir)
        return
        
    print(f"找到相关文件：{len(related_files)} 个")
    for file in related_files:
        print(f"- {file.name}")
    
    # 复制文件到临时文件夹
    print("\n开始复制文件到临时目录...")
    for file in related_files:
        shutil.copy2(file, temp_dir)
        print(f"已复制：{file.name}")
    
    # 创建zip文件
    zip_path = parent_dir / f"{base_name}.zip"
    print(f"\n创建压缩包：{zip_path}")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in temp_dir.iterdir():
            zipf.write(file, file.name)
            print(f"已添加到压缩包：{file.name}")
    
    # 删除原文件和临时文件夹
    for file in related_files:
        file.unlink()
    shutil.rmtree(temp_dir)

def main():
    # 获取用户输入的路径，默认为当前目录
    path = input('请输入要处理的目录路径（直接回车使用当前目录）：').strip()
    target_dir = Path(path) if path else Path('.')
    
    if not target_dir.exists():
        print(f"错误：路径 '{target_dir}' 不存在")
        return
    if not target_dir.is_dir():
        print(f"错误：'{target_dir}' 不是一个目录")
        return
    
    # 遍历所有视频文件
    for root, _, files in os.walk(target_dir):
        root_path = Path(root)
        for file in files:
            if Path(file).suffix.lower() in VIDEO_EXTS:
                video_path = root_path / file
                pack_related_files(video_path)

if __name__ == "__main__":
    main()
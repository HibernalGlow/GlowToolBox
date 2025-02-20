import zipfile
import shutil
import yaml
import subprocess
import os
from pathlib import Path
from tqdm import tqdm
from datetime import datetime

# 添加YAML记录路径
YAML_OUTPUT_PATH = r'E:\1BACKUP\ehv\image-size-records.yaml'

def contains_tdel_file(directory):
    """
    检查目录中是否包含 .artistdel 文件
    
    参数:
    directory: 要检查的目录路径
    
    返回:
    如果包含 .artistdel 文件则返回 True，否则返回 False
    """
    return any(directory.glob("*.artistdel"))

def contains_keywords_in_zip(zip_path, keywords):
    """
    检查压缩包内的文件名是否包含指定关键词列表中的任意一个
    
    参数:
    zip_path: 压缩包路径
    keywords: 关键词列表
    
    返回:
    如果包含任意一个关键词则返回 True，否则返回 False
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            for file_info in zip_file.filelist:
                if any(keyword in file_info.filename for keyword in keywords):
                    return True
    except Exception as e:
        print(f"无法检查压缩包 {zip_path}: {str(e)}")
    return False

def check_images_in_zip(zip_path, min_size_kb=0, max_size_kb=500):
    """
    检查压缩包中的图片平均大小是否在指定范围内
    
    参数:
    zip_path: 压缩包路径
    min_size_kb: 最小大小限制(KB)
    max_size_kb: 最大大小限制(KB)
    """
    image_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.avif', '.jxl', '.gif', '.bmp')
    image_count = 0
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            for file_info in zip_file.filelist:
                if file_info.filename.lower().endswith(image_extensions):
                    image_count += 1
        
        if image_count == 0:
            return False, 0, "无图片文件"
        
        file_size_kb = zip_path.stat().st_size / 1024
        avg_size = file_size_kb / image_count
        is_in_range = min_size_kb <= avg_size <= max_size_kb
        
        return (
            is_in_range,
            avg_size,
            f"平均: {avg_size:.2f}KB, 数量: {image_count}"
        )
        
    except zipfile.BadZipFile:
        return False, 0, "无效压缩包"
    except Exception as e:
        return False, 0, f"错误: {str(e)}"
    
    
def load_yaml_uuid_from_archive(zip_path):
    """从压缩包中获取YAML文件的UUID"""
    try:
        command = ['7z', 'l', str(zip_path)]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if line.strip().endswith('.yaml'):
                parts = line.strip().split()
                yaml_filename = parts[-1]
                return os.path.splitext(yaml_filename)[0]
    except Exception as e:
        tqdm.write(f"获取UUID时出错 {zip_path}: {str(e)}")
    return None

def load_or_save_records(records=None):
    """加载或保存YAML记录"""
    if records is None:
        if os.path.exists(YAML_OUTPUT_PATH):
            try:
                with open(YAML_OUTPUT_PATH, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or []
            except Exception as e:
                print(f"读取记录出错: {e}")
                return []
        return []
    else:
        try:
            with open(YAML_OUTPUT_PATH, 'w', encoding='utf-8') as f:
                yaml.dump(records, f, allow_unicode=True, sort_keys=False, indent=2)
        except Exception as e:
            print(f"保存记录出错: {e}")

def process_zip_file(zip_path, source_dir, min_size_kb, max_size_kb, enable_copy, target_dir, keywords, enable_keyword_check, records):
    """
    处理单个压缩包文件
    
    参数:
    zip_path: 压缩包路径
    source_dir: 源目录路径
    min_size_kb: 最小大小限制(KB)
    max_size_kb: 最大大小限制(KB)
    enable_copy: 是否启用复制功能
    target_dir: 目标目录路径
    keywords: 关键词列表
    enable_keyword_check: 是否启用关键词检查功能
    records: YAML记录列表
    """
    try:
        if enable_keyword_check and keywords and not contains_keywords_in_zip(zip_path, keywords):
            return False, 0

        rel_path = zip_path.relative_to(source_dir)
        uuid = load_yaml_uuid_from_archive(zip_path)
        
        # 检查是否已有记录
        if uuid:
            for record in records:
                if record.get('UUID') == uuid:
                    # tqdm.write(f"已存在记录: {rel_path}")
                    return False, 0

        result, avg_size, message = check_images_in_zip(zip_path, min_size_kb, max_size_kb)
        
        if result:  # 在指定范围内
            file_size = zip_path.stat().st_size
            
            # 创建新记录
            if uuid:
                record = {
                    'UUID': uuid,
                    'Path': str(rel_path),
                    'FileName': zip_path.name,
                    '文件大小': f"{file_size/1024/1024:.2f}MB",
                    '平均图片大小': f"{avg_size:.2f}KB",
                    '检查时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                records.append(record)
            
            if enable_copy:
                target_file = target_dir / rel_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(zip_path, target_file)
                tqdm.write(f"{rel_path} - {message} - {file_size/1024/1024:.2f}MB - 已复制")
            else:
                tqdm.write(f"{rel_path} - {message} - {file_size/1024/1024:.2f}MB")
            
            return True, file_size
    except Exception as e:
        tqdm.write(f"错误 {zip_path.name}: {str(e)}")
    
    return False, 0

def scan_directory(source_dir, min_size_kb=0, max_size_kb=500, enable_copy=False, target_dir=None, skip_tdel=False, keywords=None, enable_keyword_check=False):
    """
    递归扫描目录并可选复制符合条件的文件
    
    参数:
    source_dir: 源目录路径
    min_size_kb: 最小大小限制(KB)
    max_size_kb: 最大大小限制(KB)
    enable_copy: 是否启用复制功能
    target_dir: 目标目录路径（仅在enable_copy=True时需要）
    skip_tdel: 是否跳过包含.artistdel文件的文件夹
    keywords: 关键词列表，文件名中必须包含这些关键词之一
    enable_keyword_check: 是否启用关键词检查功能
    """
    source_dir = Path(source_dir)
    if enable_copy:
        if not target_dir:
            print("启用复制功能时必须指定目标目录")
            return
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
    
    # 加载现有记录
    records = load_or_save_records()
    print(f"已加载 {len(records)} 条记录")
    
    matched_count = 0
    total_size = 0
    
    try:
        if not source_dir.exists():
            print(f"源目录不存在: {source_dir}")
            return
        
        zip_files = list(source_dir.glob("*.zip"))  # 直接检查 source_dir 目录中的 ZIP 文件
        for subdir in source_dir.iterdir():
            if subdir.is_dir():
                if skip_tdel and contains_tdel_file(subdir):
                    print(f"跳过文件夹: {subdir} (包含.artistdel文件)")
                    continue
                zip_files.extend(subdir.rglob("*.zip"))  # 递归检查子目录中的 ZIP 文件
        
        if not zip_files:
            print(f"未找到zip文件")
            return
            
        print(f"共找到 {len(zip_files)} 个zip文件")
        
        zip_files.sort()
        pbar = tqdm(zip_files, desc="处理进度", position=0, leave=True)
        for zip_path in pbar:
            matched, file_size = process_zip_file(
                zip_path, source_dir, min_size_kb, max_size_kb,
                enable_copy, target_dir, keywords, enable_keyword_check,
                records
            )
            if matched:
                matched_count += 1
                total_size += file_size
                
    except Exception as e:
        print(f"扫描错误: {str(e)}")
    
    finally:
        # 保存记录
        load_or_save_records(records)
        
        print(f"\n发现 {matched_count} 个平均大小在 {min_size_kb}KB - {max_size_kb}KB 之间的压缩包")
        print(f"总大小: {total_size/1024/1024:.2f}MB")
        if enable_copy:
            print("文件已复制到目标目录")

if __name__ == "__main__":
    source_dir = r"E:\1EHV\[emily]"
    target_dir = r"E:\2EHV"
    min_size = 1000    # 最小平均大小 (KB)
    max_size = 2000# 最大平均大小 (KB)
    enable_copy = True  # 是否启用复制功能
    skip_tdel = True  # 是否跳过包含.tdl文件的文件夹
    keywords = ['.jxl']  # 关键词列表
    enable_keyword_check = True  # 是否启用关键词检查功能
    
    scan_directory(
        source_dir=source_dir,
        min_size_kb=min_size,
        max_size_kb=max_size,
        enable_copy=enable_copy,
        target_dir=target_dir if enable_copy else None,
        skip_tdel=skip_tdel,
        keywords=keywords,
        enable_keyword_check=enable_keyword_check
    )
    print("\n处理完成")
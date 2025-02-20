import zipfile
import shutil
from pathlib import Path
from tqdm import tqdm
from PIL import Image
import io
import pillow_jxl
import pillow_avif
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from functools import partial
import time

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

def check_images_in_zip(zip_path, min_size_kb=0, max_size_kb=500, min_width=0, max_width=float('inf'), min_height=0, max_height=float('inf')):
    """
    检查压缩包中的图片平均大小和尺寸是否在指定范围内
    
    参数:
    zip_path: 压缩包路径
    min_size_kb: 最小大小限制(KB)
    max_size_kb: 最大大小限制(KB)
    min_width: 最小宽度限制(像素)
    max_width: 最大宽度限制(像素)
    min_height: 最小高度限制(像素)
    max_height: 最大高度限制(像素)
    """
    image_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.avif', '.jxl', '.gif', '.bmp')
    image_sizes = []
    valid_images = 0
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            for file_info in zip_file.filelist:
                if file_info.filename.lower().endswith(image_extensions):
                    size_kb = file_info.file_size / 1024
                    if size_kb < min_size_kb or size_kb > max_size_kb:
                        continue
                        
                    try:
                        with zip_file.open(file_info) as image_file:
                            # 完整读取图片数据
                            image_data = image_file.read()
                            img = Image.open(io.BytesIO(image_data))
                            width, height = img.size
                            
                            if (min_width <= width <= max_width and 
                                min_height <= height <= max_height):
                                image_sizes.append(size_kb)
                                valid_images += 1
                    except Exception as e:
                        tqdm.write(f"跳过处理文件 {file_info.filename}: {str(e)}")
                        continue

            if not image_sizes:
                return False, 0, "无符合条件的图片"
            
            avg_size = sum(image_sizes) / len(image_sizes)
            is_in_range = min_size_kb <= avg_size <= max_size_kb
            return (
                is_in_range,
                avg_size,
                f"平均: {avg_size:.2f}KB, 符合条件数量: {valid_images}"
            )
            
    except zipfile.BadZipFile:
        return False, 0, "无效压缩包"
    except Exception as e:
        return False, 0, f"错误: {str(e)}"

def process_zip_file(zip_path, source_dir, min_size_kb, max_size_kb, enable_copy, target_dir, keywords, enable_keyword_check, min_width, max_width, min_height, max_height):
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
    min_width: 最小宽度限制(像素)
    max_width: 最大宽度限制(像素)
    min_height: 最小高度限制(像素)
    max_height: 最大高度限制(像素)
    """
    try:
        tqdm.write(f"正在处理: {zip_path.name}")
        
        # 先检查关键词
        if enable_keyword_check and keywords and not contains_keywords_in_zip(zip_path, keywords):
            return False, 0

        # 检查图片大小和宽高
        result, avg_size, message = check_images_in_zip(
            zip_path, min_size_kb, max_size_kb,
            min_width, max_width, min_height, max_height
        )
        
        # 只有当结果为True（即符合所有条件，包括宽高）时才进行复制
        if result:
            rel_path = zip_path.relative_to(source_dir)
            file_size = zip_path.stat().st_size
            
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

def scan_directory(source_dir, min_size_kb=0, max_size_kb=500, enable_copy=False, target_dir=None, skip_tdel=False, keywords=None, enable_keyword_check=False, min_width=0, max_width=float('inf'), min_height=0, max_height=float('inf')):
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
    min_width: 最小宽度限制(像素)
    max_width: 最大宽度限制(像素)
    min_height: 最小高度限制(像素)
    max_height: 最大高度限制(像素)
    """
    source_dir = Path(source_dir)
    if enable_copy:
        if not target_dir:
            print("启用复制功能时必须指定目标目录")
            return
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
    
    matched_count = 0
    total_size = 0
    results_lock = threading.Lock()
    
    def process_file_wrapper(zip_path):
        try:
            matched, file_size = process_zip_file(
                zip_path, source_dir, min_size_kb, max_size_kb,
                enable_copy, target_dir, keywords, enable_keyword_check,
                min_width, max_width, min_height, max_height
            )
            with results_lock:
                nonlocal matched_count, total_size
                if matched:
                    matched_count += 1
                    total_size += file_size
            return matched, file_size
        except Exception as e:
            tqdm.write(f"处理文件出错 {zip_path.name}: {str(e)}")
            return False, 0

    try:
        if not source_dir.exists():
            print(f"源目录不存在: {source_dir}")
            return
        
        zip_files = []
        for subdir in source_dir.iterdir():
            if subdir.is_dir():
                if skip_tdel and contains_tdel_file(subdir):
                    print(f"跳过文件夹: {subdir} (包含.artistdel文件)")
                    continue
                zip_files.extend(subdir.rglob("*.zip"))
        
        if not zip_files:
            print(f"未找到zip文件")
            return
            
        print(f"共找到 {len(zip_files)} 个zip文件")
        
        # 使用线程池处理文件
        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = []
            pbar = tqdm(total=len(zip_files), desc="处理进度", position=0, leave=True)
            
            for zip_path in zip_files:
                future = executor.submit(process_file_wrapper, zip_path)
                futures.append(future)
            
            for future in as_completed(futures):
                pbar.update(1)
            
            pbar.close()
                
    except Exception as e:
        print(f"扫描错误: {str(e)}")
    
    finally:
        print(f"\n发现 {matched_count} 个平均大小在 {min_size_kb}KB - {max_size_kb}KB 之间的压缩包")
        print(f"总大小: {total_size/1024/1024:.2f}MB")
        if enable_copy:
            print("文件已复制到目标目录")

if __name__ == "__main__":
    source_dir = r"E:\1EHV"
    target_dir = r"E:\7EHV"
    min_size = 1001    # 最小平均大小 (KB)
    max_size = 2000  # 最大平均大小 (KB)
    enable_copy = True  # 是否启用复制功能
    skip_tdel = True  # 是否跳过包含.tdl文件的文件夹
    keywords = ['.jxl']  # 关键词列表
    enable_keyword_check = True  # 是否启用关键词检查功能
    min_width = 1800    # 最小宽度 (像素)
    max_width = 100000   # 最大宽度 (像素)
    min_height = 0   # 最小高度 (像素)
    max_height = 10000000  # 最大高度 (像素)
    
    scan_directory(
        source_dir=source_dir,
        min_size_kb=min_size,
        max_size_kb=max_size,
        enable_copy=enable_copy,
        target_dir=target_dir if enable_copy else None,
        skip_tdel=skip_tdel,
        keywords=keywords,
        enable_keyword_check=enable_keyword_check,
        min_width=min_width,
        max_width=max_width,
        min_height=min_height,
        max_height=max_height
    )
    print("\n处理完成")
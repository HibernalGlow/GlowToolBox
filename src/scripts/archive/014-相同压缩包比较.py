import os
import shutil
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple, Optional
import difflib
import hashlib
import pyperclip
import argparse
from send2trash import send2trash
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import time
from dataclasses import dataclass
from collections import defaultdict

vipshome = Path(r'D:\1VSCODE\1ehv\other\vips\bin')
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(str(vipshome))
os.environ['PATH'] = str(vipshome) + ';' + os.environ['PATH']
import pyvips

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('compare_zips.log', encoding='utf-8')
    ]
)

SEVEN_ZIP_PATH = "C:\\Program Files\\7-Zip\\7z.exe"
MIN_NAME_SIMILARITY = 0.8  # 文件名相似度阈值
MAX_SIZE_DIFF_MB = 1  # 允许的最大文件大小差异（MB）
MAX_WORKERS = 4  # 最大线程数

@dataclass
class Statistics:
    total_files: int = 0
    processed_pairs: int = 0
    similar_pairs: int = 0
    deleted_files: int = 0
    saved_space: int = 0

stats = Statistics()

def format_size(size_in_bytes: int) -> str:
    """格式化文件大小显示"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.2f} TB"

def get_name_similarity(name1: str, name2: str) -> float:
    """计算两个文件名的相似度"""
    name1_clean = name1.replace("_1", "").replace("_散图", "")
    name2_clean = name2.replace("_1", "").replace("_散图", "")
    return difflib.SequenceMatcher(None, name1_clean, name2_clean).ratio()

def get_zip_size(zip_path: Path) -> int:
    """获取压缩包大小"""
    return zip_path.stat().st_size

def is_size_similar(size1: int, size2: int) -> bool:
    """检查两个文件大小是否在允许的差异范围内"""
    diff_bytes = abs(size1 - size2)
    diff_mb = diff_bytes / (1024 * 1024)  # 转换为MB
    return diff_mb <= MAX_SIZE_DIFF_MB

def extract_smallest_image(zip_path: Path, temp_dir: Path) -> Optional[Path]:
    """提取压缩包中最小的图片文件"""
    try:
        # 列出压缩包内容，使用GBK编码
        cmd = f'"{SEVEN_ZIP_PATH}" l "{zip_path}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, encoding='gbk', errors='ignore')
        
        if result.returncode != 0:
            logging.error(f"无法读取压缩包内容 {zip_path}: {result.stderr}")
            return None
            
        # 解析输出找到最小的图片文件
        smallest_image = None
        smallest_size = float('inf')
        
        for line in result.stdout.split('\n'):
            parts = line.strip().split()
            if len(parts) >= 5:
                try:
                    size = int(parts[3])
                    name = ' '.join(parts[5:])  # 文件名可能包含空格
                    if any(name.lower().endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.webp', '.avif')):
                        logging.debug(f"找到图片: {name}, 大小: {format_size(size)}")
                        if size < smallest_size and size > 0:  # 确保文件大小大于0
                            smallest_size = size
                            smallest_image = name
                except (ValueError, IndexError):
                    continue
        
        if not smallest_image:
            logging.warning(f"压缩包中没有找到图片文件: {zip_path}")
            return None
            
        logging.info(f"提取最小图片: {smallest_image} ({format_size(smallest_size)})")
            
        # 提取最小的图片
        extract_dir = temp_dir / zip_path.stem
        extract_dir.mkdir(exist_ok=True)
        
        # 使用GBK编码执行提取命令
        cmd = f'"{SEVEN_ZIP_PATH}" e "{zip_path}" -o"{extract_dir}" "{smallest_image}" -y'
        result = subprocess.run(cmd, shell=True, capture_output=True, encoding='gbk', errors='ignore')
        
        if result.returncode != 0:
            logging.error(f"提取图片失败 {zip_path}: {result.stderr}")
            return None
            
        # 返回提取的图片路径
        extracted_image = extract_dir / Path(smallest_image).name
        if not extracted_image.exists():
            logging.error(f"提取的图片文件不存在: {extracted_image}")
            return None
            
        return extracted_image
        
    except Exception as e:
        logging.error(f"处理压缩包时出错 {zip_path}: {str(e)}")
        return None

def calculate_image_hash(image_path: Path) -> Optional[str]:
    """计算图片的MD5哈希值"""
    try:
        # 直接计算文件的MD5哈希值
        with open(image_path, 'rb') as f:
            file_hash = hashlib.md5()
            # 分块读取，避免一次性读入大文件
            for chunk in iter(lambda: f.read(4096), b''):
                file_hash.update(chunk)
        hash_value = file_hash.hexdigest()
        logging.debug(f"计算图片哈希值: {image_path.name} -> {hash_value}")
        return hash_value
    except Exception as e:
        logging.error(f"计算图片哈希值失败 {image_path}: {str(e)}")
        return None

def find_all_zips(directory: Path) -> List[Path]:
    """递归查找目录下的所有zip文件"""
    zip_files = []
    try:
        for item in directory.rglob("*.zip"):
            if item.is_file():
                zip_files.append(item)
    except Exception as e:
        logging.error(f"查找zip文件时出错 {directory}: {str(e)}")
    return zip_files

def compare_zip_pair(zip_pair: Tuple[Path, Path], temp_dir: Path) -> Optional[Tuple[Path, Path]]:
    """比较单个压缩包对"""
    zip1, zip2 = zip_pair
    
    # 检查文件名相似度
    name_similarity = get_name_similarity(zip1.stem, zip2.stem)
    if name_similarity < MIN_NAME_SIMILARITY:
        return None
        
    # 检查文件大小
    size1 = get_zip_size(zip1)
    size2 = get_zip_size(zip2)
    if not is_size_similar(size1, size2):
        return None
        
    # 提取并比较最小图片的哈希值
    img1_path = extract_smallest_image(zip1, temp_dir)
    img2_path = extract_smallest_image(zip2, temp_dir)
    
    if img1_path and img2_path:
        hash1 = calculate_image_hash(img1_path)
        hash2 = calculate_image_hash(img2_path)
        
        # 清理临时文件
        for path in [img1_path, img2_path]:
            if path and path.exists():
                try:
                    path.unlink()
                except Exception:
                    pass
        
        if hash1 and hash2 and hash1 == hash2:
            return (zip1, zip2)
    
    return None

def compare_zip_pairs(zip_files: List[Path]) -> List[Tuple[Path, Path]]:
    """比较所有压缩包对，返回相似的压缩包对列表"""
    similar_pairs = []
    
    # 生成所有可能的压缩包对
    pairs = []
    for i, zip1 in enumerate(zip_files):
        for zip2 in zip_files[i+1:]:
            if zip1.parent == zip2.parent:  # 只比较同一目录下的文件
                pairs.append((zip1, zip2))
    
    stats.processed_pairs = len(pairs)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # 使用tqdm显示进度
            futures = [executor.submit(compare_zip_pair, pair, temp_path) for pair in pairs]
            for future in tqdm(futures, desc="比较压缩包", total=len(pairs)):
                result = future.result()
                if result:
                    similar_pairs.append(result)
                    stats.similar_pairs += 1
    
    return similar_pairs

def process_directory(directory: Path):
    """处理指定目录下的所有压缩包"""
    # 递归获取所有zip文件
    zip_files = find_all_zips(directory)
    if not zip_files:
        logging.info(f"目录中没有找到zip文件: {directory}")
        return
    
    stats.total_files += len(zip_files)
    logging.info(f"找到 {len(zip_files)} 个zip文件")
    
    # 比较压缩包
    similar_pairs = compare_zip_pairs(zip_files)
    
    if not similar_pairs:
        logging.info("没有找到相同的压缩包")
        return
    
    # 处理相似的压缩包对
    logging.info(f"\n处理 {len(similar_pairs)} 对重复压缩包:")
    for zip1, zip2 in similar_pairs:
        # 保留名称更短的压缩包
        to_keep = zip1 if len(zip1.stem) <= len(zip2.stem) else zip2
        to_delete = zip2 if to_keep == zip1 else zip1
        
        try:
            delete_size = get_zip_size(to_delete)
            logging.info(f"删除: {to_delete.name} ({format_size(delete_size)})")
            logging.info(f"保留: {to_keep.name}")
            send2trash(str(to_delete))
            stats.deleted_files += 1
            stats.saved_space += delete_size
        except Exception as e:
            logging.error(f"删除文件失败 {to_delete}: {str(e)}")

def print_summary():
    """打印处理总结"""
    logging.info("\n处理总结:")
    logging.info(f"总文件数: {stats.total_files}")
    logging.info(f"比较文件对数: {stats.processed_pairs}")
    logging.info(f"发现重复对数: {stats.similar_pairs}")
    logging.info(f"删除文件数: {stats.deleted_files}")
    logging.info(f"节省空间: {format_size(stats.saved_space)}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='压缩包比较工具')
    parser.add_argument('--clipboard', action='store_true', help='从剪贴板读取路径')
    args = parser.parse_args()
    
    start_time = time.time()
    
    # 获取目录路径
    if args.clipboard:
        input_text = pyperclip.paste()
        print("从剪贴板读取的路径:")
        print(input_text)
    else:
        print("请输入目录路径（每行一个，最后输入空行结束）:")
        input_lines = []
        while True:
            line = input().strip()
            if not line:
                break
            input_lines.append(line)
        input_text = '\n'.join(input_lines)
    
    # 处理输入的路径
    directories = []
    for path in input_text.strip().split('\n'):
        clean_path = path.strip().strip('"').strip("'").strip()
        if os.path.exists(clean_path):
            directories.append(Path(clean_path))
        else:
            logging.warning(f"路径不存在: {clean_path}")
    
    if not directories:
        logging.error("未输入有效路径，程序退出")
        return
    
    # 处理每个目录
    for directory in directories:
        logging.info(f"\n处理目录: {directory}")
        process_directory(directory)
    
    end_time = time.time()
    logging.info(f"\n总耗时: {end_time - start_time:.2f}秒")
    print_summary()

if __name__ == '__main__':
    main() 
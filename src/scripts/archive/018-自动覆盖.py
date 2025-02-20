import os
import re
import shutil
import logging
from tqdm import tqdm
import zipfile
import imagehash
from PIL import Image
from io import BytesIO

# 初始化日志，指定编码为UTF-8
logging.basicConfig(filename='file_check.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s', encoding='utf-8')

# 创建一个 StreamHandler 用于控制台输出
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)

# 获取根日志记录器并添加控制台处理器
logging.getLogger('').addHandler(console_handler)

def parse_filename(filename):
    """将文件名按括号和方框分隔成模块，去除多余空格"""
    modules = re.findall(r'\[(.*?)\]|\((.*?)\)', filename)
    return [item.strip() for sublist in modules for item in sublist if item]

def is_image_file(filename):
    """检查文件是否为图片文件"""
    image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')
    return filename.lower().endswith(image_extensions)

def find_matching_files(base_path, parsed_modules):
    """在目标文件夹中查找匹配的文件"""
    matching_files = []
    for root, _, files in os.walk(base_path):
        for file in files:
            if not file.endswith('.bak') and not os.path.isdir(os.path.join(root, file)) and not is_image_file(file):
                other_modules = parse_filename(file)
                if sorted(parsed_modules) == sorted(other_modules):
                    match_file = os.path.join(root, file)
                    matching_files.append(match_file)
    # if not matching_files:
    #     logging.info("No matching files found")
    return matching_files

def calculate_image_hashes(zip_path):
    """计算压缩包内所有图片的哈希值"""
    image_hashes = {}
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if not file_info.is_dir() and file_info.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
                    with zip_ref.open(file_info) as file:
                        file_content = file.read()
                        try:
                            img_hash = imagehash.phash(Image.open(BytesIO(file_content)))
                            image_hashes[file_info.filename] = img_hash
                        except Exception as e:
                            logging.error(f"Error calculating hash for {file_info.filename}: {e}")
    except zipfile.BadZipFile:
        logging.error(f"File is not a zip file: {zip_path}")
    return image_hashes

def compare_hashes(hashes1, hashes2, hamming_distance_threshold):
    """比较两个哈希字典，返回相同哈希值的数量"""
    same_count = 0
    for filename, hash_value in hashes1.items():
        for other_filename, other_hash_value in hashes2.items():
            if hash_value - other_hash_value <= hamming_distance_threshold:
                same_count += 1
                break
    return same_count

def main(src_path, target_path, hash_match_threshold, hamming_distance_threshold, skip_multiple_matches):
    """主函数，处理压缩包"""
    logging.info(f"Starting processing from {src_path} to {target_path} with hash match threshold {hash_match_threshold} and hamming distance threshold {hamming_distance_threshold}")
    total_files = sum([len(files) for r, d, files in os.walk(src_path)])
    progress_bar = tqdm(total=total_files, desc="Processing files", position=0, leave=True)

    for root, _, files in os.walk(src_path):
        for file in files:
            progress_bar.update(1)
            if file.endswith(('.zip', '.rar', '.7z')):
                filepath = os.path.join(root, file)
                #logging.info(f"Processing file: {filepath}")
                modules = parse_filename(file)
                
                matching_files = find_matching_files(target_path, modules)
                
                if matching_files:
                    if len(matching_files) == 1:
                        match_file = matching_files[0]
                        logging.info(f"Single match found: {file} will be replaced with {match_file}")
                        try:
                            shutil.copy2(filepath, match_file)
                            os.remove(filepath)
                            logging.info(f"Replaced and removed: {filepath}")
                        except Exception as e:
                            logging.error(f"Failed to replace {filepath} with {match_file}: {str(e)}")
                    elif skip_multiple_matches:
                        logging.info(f"Multiple matches found for {file}, skipping.")
                    else:
                        # 计算当前压缩包内图片的哈希值
                        current_hashes = calculate_image_hashes(filepath)
                        
                        if not current_hashes:
                            logging.info(f"Skipping file due to bad zip: {filepath}")
                            continue
                        
                        for match_file in matching_files:
                            # 计算匹配文件内图片的哈希值
                            match_hashes = calculate_image_hashes(match_file)
                            
                            if not match_hashes:
                                logging.info(f"Overwriting non-zip or bad zip file: {match_file}")
                                try:
                                    shutil.copy2(filepath, match_file)
                                    os.remove(filepath)
                                    logging.info(f"Replaced and removed: {filepath}")
                                except Exception as e:
                                    logging.error(f"Failed to replace {filepath} with {match_file}: {str(e)}")
                                break
                            
                            # 比较哈希值
                            same_count = compare_hashes(current_hashes, match_hashes, hamming_distance_threshold)
                            if same_count >= hash_match_threshold:
                                logging.info(f"Match found with {same_count} same hashes: {file} and {match_file}")
                                # 覆盖后删除原始文件夹的压缩包
                                try:
                                    shutil.copy2(filepath, match_file)
                                    os.remove(filepath)
                                    logging.info(f"Replaced and removed: {filepath}")
                                except Exception as e:
                                    logging.error(f"Failed to replace {filepath} with {match_file}: {str(e)}")
                                break
                        else:
                            logging.info(f"No match found with {hash_match_threshold}+ same hashes for: {file}")
                # else:
                #     logging.info(f"No match found for: {file}")

if __name__ == "__main__":
    src_path = r"D:\123pan\1EHV"  # 替换为您的压缩包文件夹路径
    target_path = r"E:\1EHV"  # 替换为您需要匹配的目标文件夹路径
    hash_match_threshold = 3  # 用户自定义的哈希值匹配阈值
    hamming_distance_threshold = 12  # 用户自定义的汉明距离阈值
    skip_multiple_matches = True
    
    main(src_path, target_path, hash_match_threshold, hamming_distance_threshold, skip_multiple_matches)

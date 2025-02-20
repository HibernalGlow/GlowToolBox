import os
import zipfile
from io import BytesIO
from PIL import Image
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import sys
import shutil
import threading
import warnings
import unicodedata
import hashlib

# 增加图像像素限制
Image.MAX_IMAGE_PIXELS = None

# 动态配置日志处理
log_file = "process_log.log"
error_log_file = "error_log.log"
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 配置文件日志处理器，使用 UTF-8 编码
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# 配置控制台日志处理器，只输出错误信息
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.ERROR)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
console_handler.stream = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
logger.addHandler(console_handler)

# 新增错误日志处理器
error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(error_handler)

warnings.filterwarnings('ignore', category=UserWarning, module='zipfile')

# 定义WebP格式的无损和有损压缩选项
webp_options_lossless = {
    'lossless': True,
    'method': 5,
}

webp_options_lossy = {
    'quality': 75,
    'lossless': False,
    'method': 5,
}

# 检查压缩包中的文件格式，如果全部都是 WebP 格式则跳过转换。
def check_archive_for_conversion(archive_path):
    try:
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            file_infos = zip_ref.infolist()
            non_webp_images = [f for f in file_infos if f.filename.lower().endswith(('png', 'jpg', 'jpeg', 'bmp'))]
            if len(non_webp_images) == 0:
                logger.info(f"No convertible images found in {archive_path}. Skipping conversion.")
                return False
            return True
    except Exception as e:
        logger.error(f"☢️ Error checking archive {archive_path}: {e}")
        return False

def convert_image_to_webp(image_data, webp_options, file_name, archive_path):
    try:
        img = Image.open(BytesIO(image_data))
        if webp_options.get('lossless', False):
            img = img.convert("RGB")
        else:
            img = img.convert("RGB")
        output = BytesIO()
        img.save(output, format="WEBP", **webp_options)
        img.close()
        return output.getvalue()
    except Exception as e:
        logger.error(f"☢️ Error converting image: {e}, File: {file_name}, Archive: {archive_path}. Using original file.")
        error_handler.emit(logging.LogRecord(__name__, logging.ERROR, None, None, f"☢️ Error converting image: {e}, File: {file_name}, Archive: {archive_path}. Using original file.", None, None))
        return None

def process_file(file_info, zip_ref, existing_names, new_zip, webp_options, archive_path, failed_hashes):
    try:
        with zip_ref.open(file_info) as file:
            if file_info.filename.lower().endswith(('png', 'jpg', 'jpeg', 'bmp')):
                image_data = file.read()
                converted_data = convert_image_to_webp(image_data, webp_options, file_info.filename, archive_path)
                if converted_data is None:
                    logger.warning(f"Skipping file {file_info.filename} due to conversion error. Saving original format.")
                    new_file_name = get_unique_name(existing_names, file_info.filename)
                    with zip_lock:
                        new_zip.writestr(new_file_name, image_data)
                        existing_names.add(new_file_name)
                else:
                    new_file_name = get_unique_name(existing_names, os.path.splitext(file_info.filename)[0] + ".webp")
                    with zip_lock:
                        new_zip.writestr(new_file_name, converted_data)
                        existing_names.add(new_file_name)
            elif file_info.filename.lower().endswith('.webp'):
                new_file_name = get_unique_name(existing_names, file_info.filename)
                with zip_lock:
                    new_zip.writestr(new_file_name, file.read())
                    existing_names.add(new_file_name)
            else:
                new_file_name = get_unique_name(existing_names, file_info.filename)
                with zip_lock:
                    new_zip.writestr(new_file_name, file.read())
                    existing_names.add(new_file_name)
        return True
    except Exception as e:
        logger.error(f"☢️ Error processing file {file_info.filename} in archive {archive_path}: {e}")
        error_handler.emit(logging.LogRecord(__name__, logging.ERROR, None, None, f"☢️ Error processing file {file_info.filename} in archive {archive_path}: {e}", None, None))
        return False

def process_archive_in_memory(archive_path, num_threads, backup_enabled, delete_backup_on_success, ignore_delete_backup_on_success, global_progress_bar):
    archive_name = os.path.basename(archive_path)
    original_size = os.path.getsize(archive_path)

    if not check_archive_for_conversion(archive_path):
        global_progress_bar.update(1)
        return None

    failed_hashes = set()
    if skip_failed_hashes and os.path.exists(failed_hashes_file):
        with open(failed_hashes_file, 'r') as f:
            failed_hashes = set(line.strip() for line in f)

    try:
        backup_path = None
        if backup_enabled:
            backup_path = backup_archive(archive_path)
        
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            file_infos = zip_ref.infolist()
            original_count = len([f for f in file_infos if f.filename.lower().endswith(('png', 'jpg', 'jpeg', 'bmp', 'webp'))])

            existing_names = set()
            output_zip_stream = BytesIO()
            with zipfile.ZipFile(output_zip_stream, 'w', zipfile.ZIP_DEFLATED) as new_zip:
                with ThreadPoolExecutor(max_workers=num_threads) as executor:
#                    futures = {executor.submit(process_file, file_info, zip_ref, existing_names, new_zip, webp_options_lossy if file_info.filename.lower().endswith('png') else webp_options_lossy, archive_path, failed_hashes): file_info.filename for file_info in file_infos}
                    futures = {executor.submit(process_file, file_info, zip_ref, existing_names, new_zip, webp_options_lossy, archive_path, failed_hashes): file_info.filename for file_info in file_infos}

                    

                    for future in as_completed(futures):
                        if not future.result():
                            logger.warning(f"☢️ Conversion failed for some files in {archive_path}. Skipping this archive.")
                            global_progress_bar.update(1)
                            return None

                new_count = len(existing_names)
                if not verify_conversion(original_count, new_count, archive_path, backup_path, ignore_delete_backup_on_success):
                    global_progress_bar.update(1)
                    return None

            with open(archive_path, 'wb') as f_out:
                f_out.write(output_zip_stream.getvalue())
            output_zip_stream.close()

            new_size = os.path.getsize(archive_path)
            size_reduction_mb = original_size - new_size
            if delete_backup_on_success and backup_path:
                if verify_conversion(original_count, new_count, archive_path, backup_path, ignore_delete_backup_on_success):
                    delete_backup_if_successful(archive_path, backup_path)
                else:
                    logger.warning("由于文件数量不匹配，备份文件未被删除。")
            global_progress_bar.update(1)
            return {
                "before": original_size,
                "after": new_size,
                "compression": size_reduction_mb,
                "method": "ZIP_DEFLATED"
            }

    except Exception as e:
        logger.error(f"☢️ Error processing archive {archive_path}: {e}")
        error_handler.emit(logging.LogRecord(__name__, logging.ERROR, None, None, f"☢️ Error processing archive {archive_path}: {e}", None, None))
        if backup_enabled and backup_path:
            restore_backup(archive_path, backup_path)
        global_progress_bar.update(1)
        return None
# 生成摘要报告
def generate_summary_report(log_tree):
    if not log_tree:
        logger.info("No archives processed.")
        return

    logger.info("Summary Report:")
    for archive_path, archive_info in log_tree.items():
        before = archive_info["before"]
        after = archive_info["after"]
        compression = archive_info["compression"]
        method = archive_info["method"]
        logger.info(f"Archive: {archive_path}, Original Size: {before / 1024:.2f} KB, New Size: {after / 1024:.2f} KB, Compression: {compression / 1024:.2f} KB, Method: {method}")

# 检查转换后的文件数量是否符合预期
def verify_conversion(original_count, new_count, archive_path, backup_path, ignore_delete_backup_on_success):
    if new_count < original_count:
        logger.error(f"File count mismatch after conversion: {original_count} -> {new_count}. Restoring from backup.")
        error_handler.emit(logging.LogRecord(__name__, logging.ERROR, None, None, f"File count mismatch after conversion: {original_count} -> {new_count}. Restoring from backup.", None, None))
        if backup_path:
            restored_files = restore_backup(archive_path, backup_path)
            if restored_files:
                logger.info(f"Restored {archive_path} from backup: {backup_path}")
            else:
                logger.warning("备份文件未能成功恢复。")
        return False
    elif new_count > original_count and not ignore_delete_backup_on_success:
        logger.warning(f"File count increased after conversion: {original_count} -> {new_count}. Keeping backup.")
        return True
    return True

# 删除备份文件
def delete_backup_if_successful(archive_path, backup_path):
    if os.path.exists(backup_path):
        logger.info(f"Deleting backup: {backup_path}")
        os.remove(backup_path)

# 创建备份
def backup_archive(archive_path):
    backup_path = f"{archive_path}.bak"
    shutil.copy2(archive_path, backup_path)
    logger.info(f"Backup created at: {backup_path}")
    return backup_path

# 从备份恢复
def restore_backup(archive_path, backup_path):
    if os.path.exists(backup_path):
        shutil.copy(backup_path, archive_path)
        logger.info(f"Restored {archive_path} from backup: {backup_path}")
        return True
    return False

# 生成唯一文件名，避免重名冲突
def get_unique_name(existing_names, name):
    base_name, ext = os.path.splitext(name)
    base_name = unicodedata.normalize('NFKC', base_name)  # 规范化字符
    new_name = name
    counter = 1
    while new_name in existing_names:
        new_name = f"{base_name}_{counter}{ext}"
        counter += 1
    return new_name.encode('utf-8').decode('utf-8')  # 统一使用 UTF-8 编码

# 处理整个目录
def process_directory(directory, num_threads, backup_enabled, delete_backup_on_success, ignore_delete_backup_on_success):
    archives = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.zip')):
                archive_path = os.path.join(root, file)
                if not archive_path.startswith('☢️'):  # 跳过带有☢️标记的文件
                    archives.append(archive_path)

    log_tree = {}
    total_archives = len(archives)

    # 全局进度条
    with tqdm(total=total_archives, desc="Total Progress", unit="archive", position=0, leave=True) as global_progress_bar:
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = {executor.submit(process_archive_in_memory, archive_path, num_threads, backup_enabled, delete_backup_on_success, ignore_delete_backup_on_success, global_progress_bar): archive_path for archive_path in archives}
            
            for future in as_completed(futures):
                archive_path = futures[future]
                try:
                    result = future.result()
                    if result is not None:
                        before = result['before']
                        after = result['after']
                        compression = result['compression']
                        method = result['method']
                        log_tree[archive_path] = {
                            "before": before,
                            "after": after,
                            "compression": compression,
                            "method": method
                        }
                except Exception as e:
                    logger.error(f"Error processing archive {archive_path}: {e}")
                    error_handler.emit(logging.LogRecord(__name__, logging.ERROR, None, None, f"Error processing archive {archive_path}: {e}", None, None))

    return log_tree

# 主函数入口
backup_enabled = True
delete_backup_on_success = True
ignore_delete_backup_on_success = False
skip_failed_hashes = True
failed_hashes_file = "failed_hashes.txt"
num_threads = 16
use_builtin_path= True

# 锁用于同步多线程写入
zip_lock = threading.Lock()

if __name__ == "__main__":
    if use_builtin_path:
        directory = r'E:\1EHV\[00待分类]'
    else:
        directory = input("请输入要处理的目录路径: ").strip().strip('"')

    log_tree = process_directory(directory, num_threads, backup_enabled, delete_backup_on_success, ignore_delete_backup_on_success)
    if log_tree:
        generate_summary_report(log_tree)

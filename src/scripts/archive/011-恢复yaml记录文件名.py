import os
import yaml
import logging
import threading
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tqdm import tqdm
import subprocess
import re
from datetime import datetime

# 设置日志
def setup_logging():
    """配置日志"""
    log_file = 'rename_archives.log'
    
    # 创建格式器
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # 创建并配置文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # 创建并配置控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 获取根日志记录器并设置级别
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def read_yaml(yaml_path):
    """读取YAML文件内容"""
    if os.path.exists(yaml_path):
        with open(yaml_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    return []

def get_archive_name(yaml_data, cutoff_time=None, use_earliest=False):
    """获取YAML中的压缩包名称，可选择最早或最新的记录，并可指定截止时间
    Args:
        yaml_data: YAML数据
        cutoff_time: 截止时间，datetime对象，只获取这个时间之前的记录
        use_earliest: 是否使用最早的记录，True为最早，False为最新
    """
    if not yaml_data or not isinstance(yaml_data, list):
        return None
    
    # 定义黑名单关键词集合
    blacklist_keywords = {'Z0FBQ'}
    
    # 根据选择决定遍历顺序
    records = yaml_data if use_earliest else reversed(yaml_data)
    
    # 遍历所有记录，找到符合条件的记录
    for record in records:
        if isinstance(record, dict) and 'ArchiveName' in record:
            # 检查文件名是否包含黑名单关键词
            archive_name = record['ArchiveName']
            if any(keyword in archive_name for keyword in blacklist_keywords):
                continue
                
            # 如果记录中有时间戳并且设置了截止时间
            if cutoff_time and 'Timestamp' in record:
                try:
                    record_time = datetime.fromisoformat(record['Timestamp'])
                    if record_time > cutoff_time:
                        continue
                except (ValueError, TypeError):
                    continue
            return archive_name
    return None

def get_archive_uuid(archive_path):
    """从压缩包中获取 YAML 文件名作为 UUID"""
    try:
        cmd = ['7z', 'l', archive_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 在输出中查找 .yaml 文件
        for line in result.stdout.splitlines():
            if '.yaml' in line:
                # 提取 YAML 文件名（去掉扩展名）
                yaml_name = line.split()[-1]  # 获取最后一列（文件名）
                return os.path.splitext(yaml_name)[0]  # 去掉 .yaml 扩展名
    except Exception as e:
        logger.error(f"获取UUID失败 {archive_path}: {str(e)}")
    return None

def process_single_archive(archive_path, uuid_directory, stats_lock, stats, cutoff_time=None, use_earliest=False):
    """处理单个压缩包的重命名"""
    logger = logging.getLogger(__name__)
    try:
        current_dir = os.path.dirname(archive_path)
        current_name = os.path.basename(archive_path)
        
        # 获取压缩包对应的 UUID
        uuid = get_archive_uuid(archive_path)
        if not uuid:
            logger.warning(f"无法从压缩包获取UUID: {current_name}")
            with stats_lock:
                stats['errors'] += 1
            return
            
        # 直接读取对应的 YAML 文件
        yaml_path = os.path.join(uuid_directory, f"{uuid}.yaml")
        if not os.path.exists(yaml_path):
            logger.warning(f"找不到对应的YAML文件: {yaml_path}")
            with stats_lock:
                stats['errors'] += 1
            return
            
        yaml_data = read_yaml(yaml_path)
        target_name = get_archive_name(yaml_data, cutoff_time, use_earliest)
        
        if target_name and target_name != current_name:
            new_path = os.path.join(current_dir, target_name)
            
            base_name, ext = os.path.splitext(target_name)
            counter = 1
            while os.path.exists(new_path):
                new_path = os.path.join(current_dir, f"{base_name}_{counter}{ext}")
                counter += 1
            
            os.rename(archive_path, new_path)
            logger.info(f"重命名: {current_name} -> {os.path.basename(new_path)}")
            with stats_lock:
                stats['renamed'] += 1
        else:
            with stats_lock:
                stats['skipped'] += 1
                
    except Exception as e:
        logger.error(f"处理文件时出错 {archive_path}: {str(e)}", exc_info=True)
        with stats_lock:
            stats['errors'] += 1

def rename_archives(target_directory, uuid_directory, cutoff_time=None, use_earliest=False, max_workers=8):
    """使用多线程重命名压缩包"""
    logger = logging.getLogger(__name__)
    stats = {'renamed': 0, 'skipped': 0, 'errors': 0}
    stats_lock = threading.Lock()
    
    # 获取所有压缩包
    archive_files = []
    for root, _, files in os.walk(target_directory):
        for file in files:
            if file.endswith(('.zip', '.rar', '.7z')) and not file.endswith('.tdel'):
                archive_files.append(os.path.join(root, file))
    
    total_files = len(archive_files)
    logger.info(f"找到 {total_files} 个压缩包待处理")
    
    # 使用线程池处理文件
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        with tqdm(total=total_files) as pbar:
            futures = []
            for archive_path in archive_files:
                future = executor.submit(
                    process_single_archive,
                    archive_path,
                    uuid_directory,
                    stats_lock,
                    stats,
                    cutoff_time,
                    use_earliest
                )
                future.add_done_callback(lambda p: pbar.update())
                futures.append(future)
            
            # 等待所有任务完成
            for future in futures:
                future.result()
    
    logger.info("处理完成:")
    logger.info(f"重命名: {stats['renamed']} 个文件")
    logger.info(f"跳过: {stats['skipped']} 个文件")
    logger.info(f"错误: {stats['errors']} 个文件")

if __name__ == '__main__':
    logger = setup_logging()
    target_directory = input("请输入压缩包所在目录路径: ").strip().strip('"')
    uuid_directory = r'E:\1BACKUP\ehv\uuid'
    
    # 获取恢复模式选择
    mode_choice = input("请选择恢复模式（1: 最新文件名, 2: 最早文件名）[默认1]: ").strip()
    use_earliest = mode_choice == "2"
    logger.info(f"使用{'最早' if use_earliest else '最新'}文件名模式")
    
    # 获取截止时间
    cutoff_time_str = input("请输入截止时间（格式：YYYY-MM-DD HH:MM:SS，直接回车则不限制时间）: ").strip()
    cutoff_time = None
    if cutoff_time_str:
        try:
            cutoff_time = datetime.strptime(cutoff_time_str, '%Y-%m-%d %H:%M:%S')
            logger.info(f"设置截止时间: {cutoff_time}")
        except ValueError:
            logger.error("时间格式错误，将不使用时间限制")
    
    logger.info(f"开始处理目录: {target_directory}")
    logger.info(f"YAML文件目录: {uuid_directory}")
    
    rename_archives(target_directory, uuid_directory, cutoff_time, use_earliest)
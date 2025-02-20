import os
import logging
import subprocess
from pathlib import Path
from typing import Optional
import dotenv

dotenv.load_dotenv()
# 常量配置
SCRIPTS_DIR = os.getenv("SCRIPTS_DIR")
HASH_FILES_LIST = os.path.expanduser(r"E:\1EHV\hash_files_list.txt")

HASH_SCRIPT = os.path.join(SCRIPTS_DIR, "comic", "hash_prepare.py")
DEDUP_SCRIPT = os.path.join(SCRIPTS_DIR, "comic", "img_filter.py")

def get_latest_hash_file_path() -> Optional[str]:
    """获取最新的哈希文件路径
    
    Returns:
        Optional[str]: 最新的哈希文件路径，如果没有则返回None
    """
    try:
        if not os.path.exists(HASH_FILES_LIST):
            return None
            
        with open(HASH_FILES_LIST, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        if not lines:
            return None
            
        # 获取最后一行并去除空白字符
        latest_path = lines[-1].strip()
        
        # 检查文件是否存在
        if os.path.exists(latest_path):
            return latest_path
        else:
            logging.info(f"❌ 最新的哈希文件不存在: {latest_path}")
            return None
            
    except Exception as e:
        logging.info(f"❌ 获取最新哈希文件路径失败: {e}")
        return None

def process_artist_folder(folder_path: Path, workers: int = 4, force_update: bool = False) -> Optional[str]:
    """处理画师文件夹，生成哈希文件
    
    Args:
        folder_path: 画师文件夹路径
        workers: 线程数
        force_update: 是否强制更新
        
    Returns:
        Optional[str]: 哈希文件路径
    """
    try:
        # 构建命令
        cmd = f'python "{HASH_SCRIPT}" --workers {workers} --path "{str(folder_path)}"'
        if force_update:
            cmd += " --force"
            
        logging.info(f"[#process_log]执行哈希预热命令: {cmd}")
        
        # 执行命令
        process = subprocess.run(
            cmd,
            check=False,  # 不要在失败时抛出异常
            shell=True,
            timeout=3600  # 1小时超时
        )
        
        # 根据退出码/返回码处理结果
        if process.returncode == 0:  # 成功完成
            # 获取最新的哈希文件路径
            hash_file = get_latest_hash_file_path()
            if hash_file:
                logging.info(f"[#update_log]✅ 找到哈希文件: {hash_file}")
                return hash_file
            else:
                logging.info("[#process_log]❌ 未能获取最新的哈希文件路径")
                
        elif process.returncode == 1:
            logging.info("[#process_log]❌ 没有找到需要处理的文件")
        elif process.returncode == 2:
            logging.info("[#process_log]❌ 输入路径不存在")
        elif process.returncode == 3:
            logging.info("[#process_log]❌ 处理过程出错")
        else:
            logging.info(f"[#process_log]❌ 未知错误，退出码: {process.returncode}")
            
        return None
            
    except subprocess.TimeoutExpired:
        logging.info("[#process_log]❌ 哈希预处理超时（1小时）")
    except Exception as e:
        logging.info(f"[#process_log]❌ 处理画师文件夹时出错: {str(e)}")
    return None

def process_duplicates(hash_file: str, target_paths: list[str], params: dict = None, worker_count: int = 2):
    """处理重复文件
    
    Args:
        hash_file: 哈希文件路径
        target_paths: 要处理的目标路径列表
        params: 参数字典，包含处理参数
        worker_count: 工作线程数
    """
    try:
        # 构建命令
        cmd = f'python "{DEDUP_SCRIPT}" --hash-file "{hash_file}"'
        cmd += " --bak-mode keep"
        cmd += f" --max-workers {worker_count}"
        
        # 添加参数
        if params:
            if params.get('remove_duplicates', True):
                cmd += " --remove-duplicates"
                
            if params.get('ref_hamming_distance') is not None:
                cmd += f" --ref_hamming_distance {params['ref_hamming_distance']}"
                
            if params.get('self_redup', False):
                cmd += " --self-redup"
                cmd += f" --hamming_distance {params['hamming_distance']}"
        
        for path in target_paths:
            cmd += f' "{path}"'
            
        logging.info(f"[#process_log]执行去重复命令: {cmd}")
        
        # 执行命令
        process = subprocess.run(
            cmd,
            check=False,  # 不要在失败时抛出异常
            shell=True,
            timeout=3600  # 1小时超时
        )
        
        # 根据返回码处理结果
        if process.returncode == 0:
            logging.info("[#update_log]✅ 去重复完成")
        else:
            logging.info(f"[#process_log]❌ 去重复失败，返回码: {process.returncode}")
            
    except subprocess.TimeoutExpired:
        logging.info("[#process_log]❌ 去重复处理超时（1小时）")
    except Exception as e:
        logging.info(f"[#process_log]❌ 处理重复文件时出错: {e}") 
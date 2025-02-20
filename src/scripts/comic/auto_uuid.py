import os
import uuid
import json
import yaml
import time
import subprocess
import difflib
import shutil
import logging
import sys
import threading
import argparse
import multiprocessing
from pathlib import Path
from datetime import datetime
from nanoid import generate
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import pyperclip
from colorama import init, Fore, Style
import win32file
import win32con
import numpy as np
from nodes.record.logger_config import setup_logger
from nodes.tui.textual_preset import create_config_app
from nodes.tui.textual_logger import TextualLoggerManager
import orjson  # 使用orjson进行更快的JSON处理
import zipfile
from typing import Dict, Any, Optional

# 定义日志布局配置
TEXTUAL_LAYOUT = {
    "current_stats": {
        "ratio": 2,
        "title": "📊 总体进度",
        "style": "yellow"
    },
    "current_progress": {
        "ratio": 2,
        "title": "🔄 当前进度",
        "style": "cyan"
    },
    "process": {
        "ratio": 3,
        "title": "📝 处理日志",
        "style": "magenta"
    },
    "update": {
        "ratio": 2,
        "title": "ℹ️ 更新日志",
        "style": "blue"
    }
}

# 初始化日志配置
config = {
    'script_name': 'comic_auto_uuid',
    'console_enabled': False
}
logger, config_info = setup_logger(config)

def init_TextualLogger():
    TextualLoggerManager.set_layout(TEXTUAL_LAYOUT, config_info['log_file'])

# 初始化 colorama
init()

class JsonHandler:
    """JSON文件处理类"""
    
    @staticmethod
    def load(file_path: str) -> Dict[str, Any]:
        """快速加载JSON文件"""
        try:
            with open(file_path, 'rb') as f:
                return orjson.loads(f.read())
        except Exception as e:
            logger.error(f"加载JSON文件失败 {file_path}: {e}")
            return {}
    
    @staticmethod
    def save(file_path: str, data: Dict[str, Any]) -> bool:
        """快速保存JSON文件"""
        temp_path = f"{file_path}.tmp"
        try:
            # 使用orjson进行快速序列化
            json_bytes = orjson.dumps(
                data,
                option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY
            )
            
            with open(temp_path, 'wb') as f:
                f.write(json_bytes)
            
            if os.path.exists(file_path):
                os.replace(temp_path, file_path)
            else:
                os.rename(temp_path, file_path)
            return True
            
        except Exception as e:
            logger.error(f"保存JSON文件失败 {file_path}: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False

    @staticmethod
    def convert_yaml_to_json(yaml_data: list) -> Dict[str, Any]:
        """将YAML数据转换为新的JSON格式"""
        json_data = {
            "timestamps": {}
        }
        
        for record in yaml_data:
            timestamp = record.get('Timestamp', '')
            if not timestamp:
                continue
                
            json_data["timestamps"][timestamp] = {
                "archive_name": record.get('ArchiveName', ''),
                "artist_name": record.get('ArtistName', ''),
                "relative_path": record.get('RelativePath', '')
            }
        
        return json_data

class ArchiveHandler:
    """压缩包处理类"""
    
    @staticmethod
    def load_yaml_uuid_from_archive(archive_path: str) -> Optional[str]:
        """从压缩包中加载YAML文件的UUID"""
        try:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                for name in zf.namelist():
                    if name.endswith('.yaml'):
                        return os.path.splitext(name)[0]
        except zipfile.BadZipFile:
            # 如果不是zip文件，尝试使用7z
            return ArchiveHandler._load_uuid_from_7z(archive_path, '.yaml')
        except Exception as e:
            logger.error(f"读取压缩包失败 {archive_path}: {e}")
        return None
    
    @staticmethod
    def load_json_uuid_from_archive(archive_path: str) -> Optional[str]:
        """从压缩包中加载JSON文件的UUID"""
        try:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                for name in zf.namelist():
                    if name.endswith('.json'):
                        return os.path.splitext(name)[0]
        except zipfile.BadZipFile:
            # 如果不是zip文件，尝试使用7z
            return ArchiveHandler._load_uuid_from_7z(archive_path, '.json')
        except Exception as e:
            logger.error(f"读取压缩包失败 {archive_path}: {e}")
        return None
    
    @staticmethod
    def _load_uuid_from_7z(archive_path: str, ext: str) -> Optional[str]:
        """使用7z命令行工具加载UUID"""
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            result = subprocess.run(
                ['7z', 'l', archive_path],
                capture_output=True,
                text=True,
                encoding='gbk',
                errors='ignore',
                startupinfo=startupinfo,
                check=False
            )
            
            if result.returncode != 0:
                return None
            
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                if line.endswith(ext):
                    return os.path.splitext(line.split()[-1])[0]
                    
        except Exception as e:
            logger.error(f"使用7z读取压缩包失败 {archive_path}: {e}")
        return None
    
    @staticmethod
    def convert_yaml_archive_to_json(archive_path: str) -> Optional[Dict[str, Any]]:
        """转换压缩包中的YAML文件为JSON格式"""
        try:
            yaml_uuid = ArchiveHandler.load_yaml_uuid_from_archive(archive_path)
            if not yaml_uuid:
                return None
            
            # 创建临时目录
            temp_dir = os.path.join(os.path.dirname(archive_path), '.temp_extract')
            os.makedirs(temp_dir, exist_ok=True)
            
            try:
                # 提取YAML文件
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    try:
                        zf.extract(f"{yaml_uuid}.yaml", temp_dir)
                    except KeyError:
                        # 如果不是zip文件，使用7z
                        subprocess.run(
                            ['7z', 'e', archive_path, f"{yaml_uuid}.yaml", f"-o{temp_dir}"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=True
                        )
                
                yaml_path = os.path.join(temp_dir, f"{yaml_uuid}.yaml")
                if not os.path.exists(yaml_path):
                    return None
                
                # 读取并转换YAML
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    yaml_data = yaml.safe_load(f)
                
                # 转换为JSON
                json_data = JsonHandler.convert_yaml_to_json(yaml_data)
                json_data["uuid"] = yaml_uuid
                
                # 创建JSON文件
                json_path = os.path.join(temp_dir, f"{yaml_uuid}.json")
                if JsonHandler.save(json_path, json_data):
                    # 更新压缩包
                    try:
                        with zipfile.ZipFile(archive_path, 'a') as zf:
                            # 删除旧的YAML文件
                            zf.remove(f"{yaml_uuid}.yaml")
                            # 添加新的JSON文件
                            zf.write(json_path, f"{yaml_uuid}.json")
                    except Exception:
                        # 如果不是zip文件，使用7z
                        subprocess.run(
                            ['7z', 'd', archive_path, f"{yaml_uuid}.yaml"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=True
                        )
                        subprocess.run(
                            ['7z', 'a', archive_path, json_path],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=True
                        )
                    
                    return json_data
                
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
                
        except Exception as e:
            logger.error(f"转换压缩包中的YAML失败 {archive_path}: {e}")
        return None

# 定义文件路径和线程锁
# uuid_file_path = r'E:\1BACKUP\ehv\uuid.md'  # 存储唯一 UUID 的 Markdown 文件
uuid_lock = threading.Lock()  # 用于保护UUID文件操作的线程锁

class FastUUIDLoader:
    def __init__(self, yaml_path):
        self.yaml_path = yaml_path
        self.cache_path = os.path.splitext(yaml_path)[0] + '.cache'
        self._data = None
        self._index = {}  # 初始化索引字典
        self._lock = threading.Lock()
        
        # 初始化进度属性
        self.progress = {
            'total_steps': 4,
            'current_step': 0,
            'message': '初始化中',
            'percentage': 0.0,
            'timestamp': time.time()
        }
        
        # 自动检测并生成优化格式
        if not self._check_cache_valid():
            self._build_cache()
    
    def _check_cache_valid(self):
        """校验缓存有效性"""
        if not os.path.exists(self.cache_path):
            return False
        # 校验时间戳和大小
        yaml_mtime = os.path.getmtime(self.yaml_path)
        cache_mtime = os.path.getmtime(self.cache_path)
        return yaml_mtime <= cache_mtime
    
    def _build_cache(self):
        """修复索引初始化问题"""
        with self._lock:
            try:
                # 初始化索引
                self._index = {}
                
                # 增加阶段标识
                self._update_progress("开始解析YAML文件", 5)
                
                # 使用更高效的解析方式
                with open(self.yaml_path, 'rb') as f:
                    data = yaml.load(f, Loader=yaml.CSafeLoader)
                
                # 添加数据校验
                if not data or not isinstance(data, list):
                    raise ValueError("无效的YAML数据格式")
                
                self._update_progress("数据校验通过", 20)
                
                # 分批次构建索引
                batch_size = 5000
                total = len(data)
                self._update_progress("开始构建索引", 30)
                
                for i in range(0, total, batch_size):
                    batch = data[i:i+batch_size]
                    for j, record in enumerate(batch):
                        uuid = record.get('UUID')
                        if uuid:
                            self._index[uuid] = i + j
                    # 实时更新进度
                    progress = 30 + 60 * (i + batch_size) / total
                    self._update_progress(f"索引构建中 ({i+batch_size}/{total})", min(90, progress))
                
                self._update_progress("写入缓存文件", 95)
                with open(self.cache_path, 'wb') as f:
                    np.savez_compressed(f, data=data, index=self._index)
                
                self._update_progress("完成", 100)
                
            except Exception as e:
                self._index = None  # 构建失败时重置索引
                raise

    def _update_progress(self, message, percentage):
        """更新进度信息"""
        self.progress.update({
            'message': message,
            'percentage': min(100, max(0, percentage)),
            'timestamp': time.time()
        })
        logger.info(f"[缓存构建] {message} - 进度: {self.progress['percentage']:.1f}%")

    def get_loading_progress(self):
        """获取当前加载进度"""
        return self.progress
    
    def _load_cache(self):
        """加载优化格式"""
        with open(self.cache_path, 'rb') as f:
            cache = np.load(f, allow_pickle=True)
            self._data = cache['data'].tolist()
            self._index = cache['index'].item() if 'index' in cache else {}
    
    def get_uuids(self):
        """获取UUID集合"""
        if self._index is None:
            self._load_cache()
        return set(self._index.keys())
    
    def get_record(self, uuid):
        """快速查询记录"""
        if self._index is None:
            self._load_cache()
        return self._data[self._index[uuid]]

def repair_uuid_records(uuid_record_path):
    """修复损坏的UUID记录文件。"""
    backup_path = f"{uuid_record_path}.bak"
    
    # 如果存在备份文件，尝试从备份恢复
    if os.path.exists(backup_path):
        try:
            with open(backup_path, 'r', encoding='utf-8') as file:
                records = yaml.safe_load(file) or []
                if isinstance(records, list):
                    logger.info("[#process]从备份文件恢复记录成功")
                    return records
        except Exception:
            logger.error("[#process]从备份文件恢复记录失败")
            pass
    
    # 尝试修复原文件
    try:
        with open(uuid_record_path, 'r', encoding='utf-8', errors='ignore') as file:
            content = file.read()
            # 尝试解析每个记录
            records = []
            current_record = {}
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    if current_record:
                        records.append(current_record)
                        current_record = {}
                    continue
                
                if line.startswith('- ') or line.startswith('UUID:'):
                    if current_record:
                        records.append(current_record)
                    current_record = {}
                
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip('- ').strip()
                    value = value.strip()
                    if key and value:
                        current_record[key] = value
            
            if current_record:
                records.append(current_record)
            
            # 验证记录
            valid_records = []
            for record in records:
                if 'UUID' in record:
                    valid_records.append(record)
            
            logger.info(f"[#process]成功修复记录文件，恢复了 {len(valid_records)} 条记录")
            return valid_records
    except Exception as e:
        logger.error(f"[#process]修复UUID记录文件失败: {e}")
        return []

def load_existing_uuids():
    """从JSON记录中加载现有UUID"""
    logger.info("[#current_stats]🔍 开始加载现有UUID...")
    start_time = time.time()
    
    json_record_path = r'E:\1BACKUP\ehv\uuid\uuid_records.json'
    if not os.path.exists(json_record_path):
        return set()
        
    try:
        with open(json_record_path, 'r', encoding='utf-8') as f:
            records = json.load(f)
        uuids = set(records.keys())
        
        elapsed = time.time() - start_time
        logger.info(f"[#current_stats]✅ 加载完成！共加载 {len(uuids)} 个UUID，耗时 {elapsed:.2f} 秒")
        return uuids
        
    except Exception as e:
        logger.error(f"[#process]加载UUID记录失败: {e}")
        return set()

def add_uuid_to_file(uuid, timestamp, archive_name, artist_name, relative_path=None):
    """将生成的 UUID 添加到记录文件中。"""
    uuid_record_path = r'E:\1BACKUP\ehv\uuid\uuid_records.yaml'
    os.makedirs(os.path.dirname(uuid_record_path), exist_ok=True)
    
    # 读取现有记录
    records = []
    if os.path.exists(uuid_record_path):
        try:
            with open(uuid_record_path, 'r', encoding='utf-8') as file:
                records = yaml.safe_load(file) or []
        except Exception as e:
            print(f"读取记录文件失败，尝试修复: {e}")
            records = repair_uuid_records(uuid_record_path) or []
    
    # 添加新记录
    record = {
        'UUID': uuid,
        'CreatedAt': timestamp,
        'ArchiveName': archive_name,
        'ArtistName': artist_name,
        'LastModified': timestamp,
        'LastPath': relative_path or os.path.join(artist_name, archive_name) if artist_name else archive_name
    }
    
    # 检查是否已存在该UUID的记录
    for existing_record in records:
        if existing_record.get('UUID') == uuid:  # 使用get()避免KeyError
            existing_record.update({
                'LastModified': timestamp,
                'ArchiveName': archive_name,
                'ArtistName': artist_name,
                'LastPath': relative_path or os.path.join(artist_name, archive_name) if artist_name else archive_name
            })
            break
    else:
        records.append(record)
    
    # 写入记录（使用线程锁确保并发安全）
    with uuid_lock:
        try:
            # 先写入临时文件
            temp_path = f"{uuid_record_path}.tmp"
            with open(temp_path, 'w', encoding='utf-8') as file:
                yaml.dump(records, file, allow_unicode=True, sort_keys=False)
            
            # 验证临时文件
            with open(temp_path, 'r', encoding='utf-8') as file:
                yaml.safe_load(file)
            
            # 创建备份
            if os.path.exists(uuid_record_path):
                backup_path = f"{uuid_record_path}.bak"
                shutil.copy2(uuid_record_path, backup_path)
            
            # 替换原文件
            os.replace(temp_path, uuid_record_path)
            
        except Exception as e:
            print(f"写入UUID记录文件时出错: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)

def generate_uuid(existing_uuids):
    """生成一个唯一的 16 位 UUID。"""
    while True:
        new_uuid = generate(size=16)  # 生成 16 位的 UUID
        if new_uuid not in existing_uuids:
            return new_uuid

def get_artist_name(target_directory, archive_path, mode='multi'):
    """从压缩文件路径中提取艺术家名称。
    
    Args:
        target_directory: 目标目录路径
        archive_path: 压缩文件路径
        mode: 处理模式，'multi'表示多人模式，'single'表示单人模式
        
    Returns:
        str: 艺术家名称
    """
    if mode == 'single':
        # 单人模式：使用输入路径的最后一个文件夹作为画师名称
        target_path = Path(target_directory)
        return target_path.name
    else:
        # 多人模式：使用输入路径下的一级子文件夹作为画师名称
        archive_path = Path(archive_path)
        relative_path = archive_path.relative_to(target_directory).parts
        return relative_path[0] if len(relative_path) > 0 else ""

def get_relative_path(target_directory, archive_path):
    """获取相对路径。"""
    return Path(archive_path).relative_to(target_directory).parent.as_posix()

def repair_yaml_file(yaml_path):
    """修复损坏的YAML文件。"""
    try:
        with open(yaml_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        if not lines:
            return []

        valid_data = []
        current_record = []
        
        for line in lines:
            current_record.append(line)
            if line.strip() == '' or line == lines[-1]:
                try:
                    record_str = ''.join(current_record)
                    parsed_data = yaml.safe_load(record_str)
                    if isinstance(parsed_data, list):
                        valid_data.extend(parsed_data)
                    elif parsed_data is not None:
                        valid_data.append(parsed_data)
                except yaml.YAMLError:
                    pass
                current_record = []

        if not valid_data:
            return []

        write_yaml(yaml_path, valid_data)
        return valid_data

    except Exception as e:
        print(f"修复YAML文件时出错 {yaml_path}: {e}")
        return []

def read_yaml(yaml_path):
    """读取YAML文件内容，如果文件损坏则尝试修复。"""
    if not os.path.exists(yaml_path):
        return []
        
    try:
        with open(yaml_path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
            if not isinstance(data, list):
                data = [data] if data is not None else []
            return data
    except yaml.YAMLError as e:
        print(f"YAML文件 {yaml_path} 已损坏，尝试修复...")
        return repair_yaml_file(yaml_path)
    except Exception as e:
        print(f"读取YAML文件时出错 {yaml_path}: {e}")
        return []

def write_yaml(yaml_path, data):
    """将数据写入YAML文件，确保写入完整性。"""
    temp_path = yaml_path + '.tmp'
    try:
        with open(temp_path, 'w', encoding='utf-8') as file:
            yaml.dump(data, file, allow_unicode=True)
        
        try:
            with open(temp_path, 'r', encoding='utf-8') as file:
                yaml.safe_load(file)
        except yaml.YAMLError:
            print(f"写入的YAML文件验证失败: {yaml_path}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False
            
        if os.path.exists(yaml_path):
            os.replace(temp_path, yaml_path)
        else:
            os.rename(temp_path, yaml_path)
        return True
            
    except Exception as e:
        print(f"写入YAML文件时出错 {yaml_path}: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False

def get_uuid_path(uuid_directory, timestamp):
    """根据时间戳生成按年月日分层的UUID文件路径。"""
    date = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    year = str(date.year)
    month = f"{date.month:02d}"
    day = f"{date.day:02d}"
    
    # 创建年月日层级目录
    year_dir = os.path.join(uuid_directory, year)
    month_dir = os.path.join(year_dir, month)
    day_dir = os.path.join(month_dir, day)
    
    # 确保目录存在
    os.makedirs(day_dir, exist_ok=True)
    
    return day_dir

def create_yaml(yaml_path, artist_name, archive_name, relative_path, timestamp, uuid):
    """创建新的YAML结构，并写入文件。"""
    # yaml_path已经是完整路径，不需要再次获取日期路径
    data = [{
        'UUID': uuid,
        'Timestamp': timestamp,
        'ArtistName': artist_name,
        'ArchiveName': archive_name,
        'RelativePath': relative_path
    }]
    write_yaml(yaml_path, data)

def normalize_filename(filename):
    """标准化文件名，移除多余空格和特殊字符的影响"""
    normalized = ' '.join(filename.split())
    normalized = normalized.replace('_1', '').replace('_2', '').strip()
    return normalized

def update_yaml(yaml_path, artist_name, archive_name, relative_path, timestamp):
    """更新已有的YAML文件，记录时间戳和信息的变化。"""
    data = read_yaml(yaml_path)

    if not data:
        new_uuid = generate_uuid(load_existing_uuids())
        create_yaml(yaml_path, artist_name, archive_name, relative_path, timestamp, new_uuid)
        logger.info(f"✨ 创建新的YAML记录 [UUID: {new_uuid}]")
        return False

    if not isinstance(data, list) or not all(isinstance(record, dict) for record in data):
        raise ValueError("Invalid YAML format. Expected a list of dictionaries.")

    current_artist = None
    current_archive = None
    current_path = None
    
    for record in reversed(data):
        if current_artist is None and 'ArtistName' in record:
            current_artist = record['ArtistName']
        if current_archive is None and 'ArchiveName' in record:
            current_archive = record['ArchiveName']
        if current_path is None and 'RelativePath' in record:
            current_path = record['RelativePath']
        if current_artist is not None and current_archive is not None and current_path is not None:
            break

    normalized_current = normalize_filename(current_archive) if current_archive else None
    normalized_new = normalize_filename(archive_name)
    
    changes = []
    changes_data = {}
    
    if artist_name != current_artist:
        curr = current_artist or '无'
        changes.append(f"艺术家:{curr} -> {artist_name}")
        changes_data['ArtistName'] = artist_name

    if normalized_current != normalized_new:
        changes.append(f"文件名: {current_archive} -> {archive_name}")
        changes_data['ArchiveName'] = archive_name

    if relative_path != current_path:
        changes.append(f"路径: {current_path} -> {relative_path}")
        changes_data['RelativePath'] = relative_path
    
    if changes:
        logger.info(f"📝 {os.path.basename(archive_name)}\n    " + "\n    ".join(changes))

    if not changes_data:
        logger.info("✓ 未检测到变化")
        return False

    logger.info(f"🔄 检测到变化，添加新记录...")
    new_record = {
        'Timestamp': timestamp,
        **changes_data
    }

    data.append(new_record)
    write_yaml(yaml_path, data)
    logger.info("✅ 成功更新YAML文件")
    return True

def add_yaml_to_zip(yaml_path, archive_path):
    """将YAML文件添加到压缩包中，并保留压缩包和文件夹的时间戳。"""
    original_stat_archive = os.stat(archive_path)
    archive_folder_path = os.path.dirname(archive_path)
    original_stat_folder = os.stat(archive_folder_path)

    subprocess.run(['7z.exe', 'u', archive_path, yaml_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    os.utime(archive_path, (original_stat_archive.st_atime, original_stat_archive.st_mtime))
    os.utime(archive_folder_path, (original_stat_folder.st_atime, original_stat_folder.st_mtime))

def process_single_archive(archive_path, target_directory, uuid_directory, timestamp):
    """处理单个压缩文件的逻辑。"""
    try:
        # 检查是否存在YAML文件并转换为JSON
        yaml_uuid = ArchiveHandler.load_yaml_uuid_from_archive(archive_path)
        if yaml_uuid:
            logger.info(f"[#process]检测到YAML文件: {os.path.basename(archive_path)}")
            json_data = ArchiveHandler.convert_yaml_archive_to_json(archive_path)
            if not json_data:
                logger.error(f"[#process]转换YAML到JSON失败: {archive_path}")
                return True
            logger.info(f"[#process]YAML转换完成: {os.path.basename(archive_path)}")
            return True  # 如果是YAML转换流程,完成后直接返回
        
        # 检查是否已存在JSON文件
        json_uuid = ArchiveHandler.load_json_uuid_from_archive(archive_path)
        if json_uuid:
            logger.info(f"[#process]已存在JSON文件: {os.path.basename(archive_path)}")
            return True
        
        # 获取或创建新的UUID
        uuid_value = generate_uuid(load_existing_uuids())
        json_filename = f"{uuid_value}.json"
        
        # 获取文件信息
        artist_name = get_artist_name(target_directory, archive_path, args.mode if hasattr(args, 'mode') else 'multi')
        archive_name = os.path.basename(archive_path)
        relative_path = get_relative_path(target_directory, archive_path)
        
        logger.info(f"[#current_stats]处理文件: {archive_name}")
        logger.info(f"[#current_stats]艺术家: {artist_name}")
        logger.info(f"[#current_stats]相对路径: {relative_path}")
        
        # 获取按年月日分层的目录路径
        day_dir = get_uuid_path(uuid_directory, timestamp)
        json_path = os.path.join(day_dir, json_filename)
        
        # 准备新的记录数据
        new_record = {
            "archive_name": archive_name,
            "artist_name": artist_name,
            "relative_path": relative_path
        }
        
        # 创建新的JSON文件
        json_data = {
            "uuid": uuid_value,
            "timestamps": {
                timestamp: new_record
            }
        }
        
        # 保存JSON文件
        if JsonHandler.save(json_path, json_data):
            logger.info(f"[#process]创建新JSON: {json_filename}")
            logger.info(f"[#update]✅ 已更新JSON文件: {json_filename}")
            
            # 添加JSON到压缩包
            try:
                with zipfile.ZipFile(archive_path, 'a') as zf:
                    zf.write(json_path, json_filename)
                logger.info(f"[#update]✅ 已添加JSON到压缩包: {archive_name}")
            except Exception:
                # 如果不是zip文件，使用7z
                subprocess.run(
                    ['7z', 'a', archive_path, json_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True
                )
                logger.info(f"[#update]✅ 已添加JSON到压缩包: {archive_name}")
        else:
            logger.error(f"[#process]JSON文件保存失败: {archive_name}")
            
        return True

    except subprocess.CalledProcessError:
        logger.error(f"[#process]发现损坏的压缩包: {archive_path}")
        return True
    except Exception as e:
        logger.error(f"[#process]处理压缩包时出错 {archive_path}: {str(e)}")
        return True

def warm_up_cache(target_directory, max_workers=32, handler=None):
    """并行预热系统缓存"""
    logger.info("[#current_stats]🔄 开始预热系统缓存")
    
    # 首先计算总文件数
    total_files = 0
    for root, _, files in os.walk(target_directory):
        total_files += sum(1 for file in files if file.endswith(('.zip', '.rar', '.7z')))
    
    logger.info("[#current_progress]扫描文件中...")
    archive_files = []
    current_count = 0
    for root, _, files in os.walk(target_directory):
        for file in files:
            if file.endswith(('.zip', '.rar', '.7z')):
                archive_files.append(os.path.join(root, file))
                current_count += 1
                logger.info(f"[@current_progress]已扫描 {current_count}/{total_files} 个文件 ({(current_count/total_files*100):.1f}%)")
    
    logger.info(f"[#current_stats]📊 找到 {total_files} 个文件待预热")
    
    def read_file_header_with_progress(file_path):
        try:
            handle = win32file.CreateFile(
                file_path,
                win32con.GENERIC_READ,
                win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_FLAG_SEQUENTIAL_SCAN,
                None
            )
            try:
                win32file.ReadFile(handle, 32)
            finally:
                handle.Close()
            logger.info(f"[#process]✅ 已预热: {os.path.basename(file_path)}")
        except Exception as e:
            logger.error(f"[#process]预热失败: {os.path.basename(file_path)} - {str(e)}")

    with ThreadPoolExecutor(max_workers=128) as executor:
        futures = [executor.submit(read_file_header_with_progress, file) for file in archive_files]
        completed = 0
        for future in as_completed(futures):
            completed += 1
            logger.info(f"[@current_progress]预热进度 {completed}/{total_files} ({(completed/total_files*100):.1f}%)")
    
    logger.info("[#current_stats]✨ 缓存预热完成")

def process_archives(target_directory, max_workers=5, handler=None):
    """遍历目录中的压缩文件，生成或更新JSON文件。"""
    if handler is None:
        return _process_archives_internal(target_directory, max_workers)
    else:
        return _process_archives_internal(target_directory, max_workers)

def _process_archives_internal(target_directory, max_workers):
    """处理压缩文件的内部实现"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    uuid_directory = r'E:\1BACKUP\ehv\uuid'
    os.makedirs(uuid_directory, exist_ok=True)

    logger.info("[#current_stats]🔍 开始扫描压缩文件")
    
    scan_task = logger.info("[#current_progress]扫描文件")
    
    archive_files = []
    file_count = 0
    for root, _, files in os.walk(target_directory):
        for file in files:
            if file.endswith(('.zip', '.rar', '.7z')):
                full_path = os.path.join(root, file)
                archive_files.append((full_path, os.path.getmtime(full_path)))
                file_count += 1
                logger.info(f"[@current_progress]扫描进度 ({file_count}) {(file_count/len(files)*100):.1f}%")
    
    # 按修改时间排序
    archive_files.sort(key=lambda x: x[1], reverse=True)
    archive_files = [file_path for file_path, _ in archive_files]
    
    logger.info(f"[#current_stats]📊 共发现 {file_count} 个压缩文件")
    
    # 加载现有UUID
    logger.info("[#current_stats]💾 正在加载现有UUID...")
    existing_uuids = load_existing_uuids()
    logger.info(f"[#current_stats]📝 已加载 {len(existing_uuids)} 个现有UUID")
    
    process_task = logger.info("[#current_progress]处理压缩文件")
    
    # 添加跳过计数器
    skip_count = 0
    
    def process_with_progress(archive_path):
        nonlocal skip_count
        try:
            start_time = time.time()
            result = process_single_archive(archive_path, target_directory, uuid_directory, timestamp)
            
            # 记录处理时长
            duration = time.time() - start_time
            if duration > 30:
                logger.warning(f"[#process]⏱️ 处理时间过长: {os.path.basename(archive_path)} 耗时{duration:.1f}秒")
            
            return result
        except Exception as e:
            logger.error(f"[#process]🔥 严重错误: {str(e)}")
            raise
    
    # 修改任务分发方式
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 使用批量提交任务
        batch_size = 100
        futures = []
        
        for i in range(0, len(archive_files), batch_size):
            batch = archive_files[i:i+batch_size]
            futures.extend(executor.submit(process_with_progress, path) for path in batch)
            
            # 实时显示提交进度
            submitted = min(i + batch_size, len(archive_files))
            total_files = len(archive_files)
            logger.info(f"[@current_progress]提交进度 ({submitted}/{total_files}) {(submitted/total_files*100):.1f}%")

        # 添加超时机制
        completed = 0
        for future in as_completed(futures, timeout=300):
            try:
                result = future.result(timeout=60)  # 每个任务最多60秒
                completed += 1
                logger.info(f"[@current_progress]处理进度 ({completed}/{total_files}) {(completed/total_files*100):.1f}%")
                if result == "SKIP_LIMIT_REACHED":
                    logger.info("[#process]⏩ 达到跳过限制，取消剩余任务...")
                    for f in futures:
                        f.cancel()
                    break
            except TimeoutError:
                logger.warning("[#process]⌛ 任务超时，已跳过")
                skip_count += 1
            except Exception as e:
                logger.error(f"[#process]任务失败: {str(e)}")
                skip_count = 0

    if skip_count >= 100:
        logger.info("[#current_stats]🔄 由于连续跳过次数达到100，提前结束当前阶段")
    else:
        logger.info("[#current_stats]✨ 所有文件处理完成")
    
    return skip_count >= 100

def load_json_uuid_from_archive(archive_path):
    """尝试从压缩包内加载JSON文件以获取UUID。"""
    try:
        short_path = get_short_path(archive_path)
        
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        command = ['7z', 'l', short_path]
        result = subprocess.run(
            command, 
            capture_output=True, 
            text=True, 
            encoding='gbk',
            errors='ignore',
            startupinfo=startupinfo,
            check=False
        )
        
        if result.returncode != 0:
            logger.error(f"列出压缩包内容失败: {archive_path}")
            return None
            
        if result.stdout:
            for line in result.stdout.splitlines():
                if not line:
                    continue
                    
                line = line.strip()
                if line.endswith('.json'):
                    parts = line.split()
                    if parts:
                        json_filename = parts[-1]
                        json_uuid = os.path.splitext(json_filename)[0]
                        return json_uuid

    except Exception as e:
        logger.error(f"无法加载压缩包中的JSON文件 ({archive_path}): {e}")
        
    return None

def get_short_path(long_path):
    """将长路径转换为短路径格式。"""
    try:
        import win32api
        return win32api.GetShortPathName(long_path)
    except ImportError:
        return long_path

def main():
    """主函数"""
    # 定义复选框选项
    checkbox_options = [
        ("无画师模式 - 不添加画师名", "no_artist", "--no-artist"),
        ("保持时间戳 - 保持文件的修改时间", "keep_timestamp", "--keep-timestamp", True),
        ("多画师模式 - 处理整个目录", "multi_mode", "--mode multi"),
        ("单画师模式 - 只处理单个画师的文件夹", "single_mode", "--mode single"),
        ("从剪贴板读取路径", "clipboard", "-c", True),  # 默认开启
        ("自动序列 - 执行完整处理流程", "auto_sequence", "-a"),  # 添加序列模式选项
        ("重组UUID - 按时间重组UUID文件", "reorganize", "-r"),  # 添加重组选项
        ("更新记录 - 更新UUID记录文件", "update_records", "-u"),  # 添加更新记录选项
        ("转换YAML - 转换现有YAML到JSON", "convert_yaml", "--convert"),  # 添加YAML转换选项
    ]

    # 定义输入框选项
    input_options = [
        ("路径", "path", "--path", "", "输入要处理的路径，留空使用默认路径"),
    ]

    # 预设配置
    preset_configs = {
        "标准多画师": {
            "description": "标准多画师模式，会添加画师名",
            "checkbox_options": ["keep_timestamp", "multi_mode", "clipboard"],
            "input_values": {"path": ""}
        },
        "标准单画师": {
            "description": "标准单画师模式，会添加画师名", 
            "checkbox_options": ["keep_timestamp", "single_mode", "clipboard"],
            "input_values": {"path": ""}
        },
        "无画师模式": {
            "description": "不添加画师名的重命名模式",
            "checkbox_options": ["no_artist", "keep_timestamp", "clipboard"],
            "input_values": {"path": ""}
        },
        "完整序列": {
            "description": "执行完整处理流程：UUID-JSON -> 自动文件名 -> UUID-JSON",
            "checkbox_options": ["keep_timestamp", "clipboard", "auto_sequence"],
            "input_values": {"path": ""}
        },
        "UUID更新": {
            "description": "重组UUID文件结构并更新记录",
            "checkbox_options": ["reorganize", "update_records"],
            "input_values": {"path": ""}
        },
        "完整维护": {
            "description": "执行完整序列并更新UUID记录",
            "checkbox_options": ["keep_timestamp", "clipboard", "auto_sequence", "reorganize", "update_records"],
            "input_values": {"path": ""}
        },
        "YAML转换": {
            "description": "转换现有YAML文件到JSON格式",
            "checkbox_options": ["convert_yaml"],
            "input_values": {"path": ""}
        }
    }

    # 创建并运行配置界面
    app = create_config_app(
        program=__file__,
        checkbox_options=checkbox_options,
        input_options=input_options,
        title="UUID-JSON 工具",
        preset_configs=preset_configs
    )
    app.run()

def reorganize_uuid_files(uuid_directory=r'E:\1BACKUP\ehv\uuid'):
    """根据最后修改时间重新组织UUID文件的目录结构"""
    logger.info("[#current_stats]🔄 开始重新组织UUID文件...")
    
    json_record_path = os.path.join(uuid_directory, 'uuid_records.json')
    if not os.path.exists(json_record_path):
        logger.error("[#process]❌ UUID记录文件不存在")
        return
        
    try:
        with open(json_record_path, 'r', encoding='utf-8') as f:
            records = json.load(f)
            
        total_records = len(records)
        processed = 0
        
        for uuid, data in records.items():
            if not data.get("timestamps"):
                continue
                
            latest_timestamp = max(data["timestamps"].keys())
            
            try:
                date = datetime.strptime(latest_timestamp, "%Y-%m-%d %H:%M:%S")
                year = str(date.year)
                month = f"{date.month:02d}"
                day = f"{date.day:02d}"
                
                year_dir = os.path.join(uuid_directory, year)
                month_dir = os.path.join(year_dir, month)
                day_dir = os.path.join(month_dir, day)
                target_path = os.path.join(day_dir, f"{uuid}.json")
                
                current_json_path = None
                for root, _, files in os.walk(uuid_directory):
                    if f"{uuid}.json" in files:
                        current_json_path = os.path.join(root, f"{uuid}.json")
                        break
                
                if current_json_path and current_json_path != target_path:
                    os.makedirs(day_dir, exist_ok=True)
                    shutil.move(current_json_path, target_path)
                    logger.info(f"[#process]✅ 已移动: {uuid}.json")
                
                processed += 1
                logger.info(f"[@current_progress]重组进度 {processed}/{total_records} ({(processed/total_records*100):.1f}%)")
                    
            except ValueError as e:
                logger.error(f"[#process]❌ UUID {uuid} 的时间戳格式无效: {latest_timestamp}")
                
    except Exception as e:
        logger.error(f"[#process]重组UUID文件失败: {e}")
    
    logger.info("[#current_stats]✨ UUID文件重组完成")

def update_json_records(uuid_directory=r'E:\1BACKUP\ehv\uuid'):
    """更新JSON记录文件，确保所有记录都被保存"""
    logger.info("[#current_stats]🔄 开始更新JSON记录...")
    
    json_record_path = os.path.join(uuid_directory, 'uuid_records.json')
    
    existing_records = JsonHandler.load(json_record_path)
    
    total_files = 0
    processed = 0
    
    # 首先计算总文件数
    for root, _, files in os.walk(uuid_directory):
        total_files += sum(1 for file in files if file.endswith('.json') and file != 'uuid_records.json')
    
    # 遍历目录结构查找所有JSON文件
    for root, _, files in os.walk(uuid_directory):
        for file in files:
            if file.endswith('.json') and file != 'uuid_records.json':
                uuid = os.path.splitext(file)[0]
                json_path = os.path.join(root, file)
                try:
                    file_data = JsonHandler.load(json_path)
                    if uuid not in existing_records:
                        existing_records[uuid] = file_data
                        logger.info(f"[#process]✅ 添加新记录: {uuid}")
                    else:
                        existing_records[uuid]["timestamps"].update(file_data.get("timestamps", {}))
                        logger.info(f"[#process]✅ 更新记录: {uuid}")
                        
                except Exception as e:
                    logger.error(f"[#process]处理JSON文件失败 {json_path}: {e}")
                
                processed += 1
                logger.info(f"[@current_progress]更新进度 {processed}/{total_files} ({(processed/total_files*100):.1f}%)")
    
    if JsonHandler.save(json_record_path, existing_records):
        logger.info("[#current_stats]✅ JSON记录更新完成")
    else:
        logger.error("[#process]❌ JSON记录更新失败")

def convert_yaml_to_json_structure():
    """将现有的YAML文件结构转换为JSON结构"""
    logger.info("[#current_stats]🔄 开始转换YAML到JSON结构...")
    
    uuid_directory = r'E:\1BACKUP\ehv\uuid'
    yaml_record_path = os.path.join(uuid_directory, 'uuid_records.yaml')
    json_record_path = os.path.join(uuid_directory, 'uuid_records.json')
    
    # 转换主记录文件
    if os.path.exists(yaml_record_path):
        try:
            with open(yaml_record_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)
                
            total_records = len(yaml_data)
            processed = 0
            
            json_records = {}
            for record in yaml_data:
                uuid = record.get('UUID')
                if not uuid:
                    continue
                    
                if uuid not in json_records:
                    json_records[uuid] = {"timestamps": {}}
                    
                timestamp = record.get('LastModified') or record.get('CreatedAt')
                if timestamp:
                    json_records[uuid]["timestamps"][timestamp] = {
                        "archive_name": record.get('ArchiveName', ''),
                        "artist_name": record.get('ArtistName', ''),
                        "relative_path": record.get('LastPath', '')
                    }
                
                processed += 1
                logger.info(f"[@current_progress]转换进度 {processed}/{total_records} ({(processed/total_records*100):.1f}%)")
            
            JsonHandler.save(json_record_path, json_records)
            logger.info("[#current_stats]✅ 主记录文件转换完成")
            
        except Exception as e:
            logger.error(f"[#process]转换主记录文件失败: {e}")
    
    # 转换目录中的YAML文件
    yaml_files = []
    for root, _, files in os.walk(uuid_directory):
        yaml_files.extend([os.path.join(root, f) for f in files if f.endswith('.yaml') and f != 'uuid_records.yaml'])
    
    total_files = len(yaml_files)
    processed = 0
    
    for yaml_path in yaml_files:
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)
                
            json_path = os.path.join(os.path.dirname(yaml_path), f"{os.path.splitext(os.path.basename(yaml_path))[0]}.json")
            
            json_data = JsonHandler.convert_yaml_to_json(yaml_data)
            json_data["uuid"] = os.path.splitext(os.path.basename(yaml_path))[0]
            
            if JsonHandler.save(json_path, json_data):
                os.remove(yaml_path)
                logger.info(f"[#process]✅ 转换完成: {os.path.basename(yaml_path)}")
            
            processed += 1
            logger.info(f"[@current_progress]文件转换进度 {processed}/{total_files} ({(processed/total_files*100):.1f}%)")
            
        except Exception as e:
            logger.error(f"[#process]转换文件失败 {os.path.basename(yaml_path)}: {e}")
    
    logger.info("[#current_stats]✨ YAML到JSON转换完成")

class CommandManager:
    """命令行参数管理器"""
    
    @staticmethod
    def init_parser():
        parser = argparse.ArgumentParser(description='处理文件UUID和JSON生成')
        parser.add_argument('-c', '--clipboard', action='store_true', help='从剪贴板读取路径')
        parser.add_argument('-m', '--mode', choices=['multi', 'single'], help='处理模式：multi(多人模式)或single(单人模式)')
        parser.add_argument('--no-artist', action='store_true', help='无画师模式 - 不添加画师名')
        parser.add_argument('--keep-timestamp', action='store_true', help='保持文件的修改时间')
        parser.add_argument('--path', help='要处理的路径')
        parser.add_argument('-a', '--auto-sequence', action='store_true', help='自动执行完整序列：UUID-JSON -> 自动文件名 -> UUID-JSON')
        parser.add_argument('-r', '--reorganize', action='store_true', help='重新组织 UUID 文件结构')
        parser.add_argument('-u', '--update-records', action='store_true', help='更新 UUID 记录文件')
        parser.add_argument('--convert', action='store_true', help='转换YAML到JSON结构')
        return parser

    @staticmethod
    def get_target_directory(args):
        if args.clipboard:
            try:
                target_directory = pyperclip.paste().strip().strip('"')
                if not os.path.exists(target_directory):
                    logger.error(f"[#process]剪贴板中的路径无效: {target_directory}")
                    sys.exit(1)
                logger.info(f"[#current_stats]已从剪贴板读取路径: {target_directory}")
            except Exception as e:
                logger.error(f"[#process]从剪贴板读取路径失败: {e}")
                sys.exit(1)
        else:
            target_directory = args.path or r"E:\1EHV"
            logger.info(f"[#current_stats]使用路径: {target_directory}")
        return target_directory

class TaskExecutor:
    """任务执行器"""
    
    def __init__(self, args, target_directory):
        self.args = args
        self.target_directory = target_directory
        self.max_workers = min(32, (multiprocessing.cpu_count() * 4) + 1)

    def execute_tasks(self):
        """执行所有任务"""
        # 初始化日志系统
        init_TextualLogger()
        
        logger.info(f"[#current_stats]当前模式: {'多人模式' if self.args.mode == 'multi' else '单人模式'}")

        if self.args.convert:
            self._execute_convert_task()
            return

        if self.args.reorganize:
            self._execute_reorganize_task()

        if self.args.update_records:
            self._execute_update_records_task()

        if self.args.auto_sequence:
            self._execute_auto_sequence()
        elif not self.args.reorganize and not self.args.update_records:
            self._execute_normal_process()

        self._validate_json_records()

    def _execute_convert_task(self):
        """执行YAML转JSON任务"""
        convert_yaml_to_json_structure()
        sys.exit(0)

    def _execute_reorganize_task(self):
        """执行重组任务"""
        logger.info("[#current_stats]📝 开始重新组织 UUID 文件...")
        reorganize_uuid_files(r'E:\1BACKUP\ehv\uuid')

    def _execute_update_records_task(self):
        """执行更新记录任务"""
        logger.info("[#current_stats]📝 开始更新 UUID 记录...")
        update_json_records(r'E:\1BACKUP\ehv\uuid')

    def _execute_auto_sequence(self):
        """执行自动序列任务"""
        logger.info("[#current_stats]🔄 开始执行完整序列...")
        
        # 第1步：UUID-JSON处理
        logger.info("[#current_stats]📝 第1步：执行UUID-JSON处理...")
        self._process_uuid_json()
        
        # 第2步：自动文件名处理
        logger.info("[#current_stats]📝 第2步：执行自动文件名处理...")
        self._run_auto_filename_script()
        
        # 第3步：再次UUID-JSON处理
        logger.info("[#current_stats]📝 第3步：再次执行UUID-JSON处理...")
        self._process_uuid_json()
        
        logger.info("[#current_stats]✨ 完整序列执行完成！")

    def _execute_normal_process(self):
        """执行普通处理流程"""
        if self.args.mode == 'multi':
            warm_up_cache(self.target_directory, self.max_workers)
        process_archives(self.target_directory, self.max_workers)

    def _process_uuid_json(self):
        """处理UUID-JSON相关任务"""
        if self.args.mode == 'multi':
            warm_up_cache(self.target_directory, self.max_workers)
        skip_limit_reached = process_archives(self.target_directory, self.max_workers)
        
        if skip_limit_reached:
            logger.info("[#current_stats]⏩ 由于连续跳过次数达到限制，提前进入下一阶段")

    def _run_auto_filename_script(self):
        """运行自动文件名脚本"""
        auto_filename_script = os.path.join(os.path.dirname(__file__), '011-自动唯一文件名.py')
        if not os.path.exists(auto_filename_script):
            logger.error(f"[#process]找不到自动文件名脚本: {auto_filename_script}")
            return

        try:
            cmd = [sys.executable, auto_filename_script]
            if self.args.clipboard:
                cmd.extend(['-c'])
            if self.args.mode:
                cmd.extend(['-m', self.args.mode])

            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                encoding='gbk',
                errors='ignore',
                startupinfo=startupinfo
            )

            for line in result.stdout.splitlines():
                if line.strip():
                    logger.info(line)

            logger.info("[#current_stats]✅ 自动文件名处理完成")
        except subprocess.CalledProcessError as e:
            logger.error(f"[#process]自动文件名处理失败: {str(e)}")
            if e.output:
                logger.error(f"[#process]错误输出: {e.output}")

    def _validate_json_records(self):
        """验证JSON记录文件"""
        json_record_path = r'E:\1BACKUP\ehv\uuid\uuid_records.json'
        if os.path.exists(json_record_path):
            try:
                with open(json_record_path, 'r', encoding='utf-8') as f:
                    json.load(f)
                logger.info("[#current_stats]✅ JSON记录文件验证通过")
            except json.JSONDecodeError as e:
                logger.error(f"[#process]❌ JSON记录文件验证失败: {e}")
                sys.exit(1)
        else:
            logger.warning("[#process]⚠️ JSON记录文件不存在")

if __name__ == '__main__':
    # 初始化命令行解析器
    parser = CommandManager.init_parser()
    args = parser.parse_args()

    # 如果没有命令行参数，启动TUI界面
    if len(sys.argv) == 1:
        main()
        sys.exit(0)

    # 获取目标目录
    target_directory = CommandManager.get_target_directory(args)

    # 执行任务
    executor = TaskExecutor(args, target_directory)
    executor.execute_tasks()
    
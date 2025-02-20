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
from typing import Dict, Any, Optional, List

# 定义日志布局配置
TEXTUAL_LAYOUT = {
    "current_stats": {
        "ratio": 2,
        "title": "📊 总体进度",
        "style": "lightyellow"
    },
    "current_progress": {
        "ratio": 2,
        "title": "🔄 当前进度",
        "style": "lightcyan"
    },
    "process": {
        "ratio": 3,
        "title": "📝 处理日志",
        "style": "lightpink"
    },
    "update": {
        "ratio": 2,
        "title": "ℹ️ 更新日志",
        "style": "lightblue"
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

    @staticmethod
    def check_and_update_record(json_content: Dict[str, Any], archive_name: str, artist_name: str, relative_path: str, timestamp: str) -> bool:
        """检查并更新JSON记录
        
        Returns:
            bool: True表示需要更新，False表示无需更新
        """
        if "timestamps" not in json_content:
            return True
            
        latest_record = None
        if json_content["timestamps"]:
            latest_timestamp = max(json_content["timestamps"].keys())
            latest_record = json_content["timestamps"][latest_timestamp]
            
        if not latest_record:
            return True
            
        # 检查是否需要更新
        need_update = False
        if latest_record.get("archive_name") != archive_name:
            need_update = True
        if latest_record.get("artist_name") != artist_name:
            need_update = True
        if latest_record.get("relative_path") != relative_path:
            need_update = True
            
        return need_update

    @staticmethod
    def update_record(json_content: Dict[str, Any], archive_name: str, artist_name: str, relative_path: str, timestamp: str) -> Dict[str, Any]:
        """更新JSON记录"""
        json_content["timestamps"][timestamp] = {
            "archive_name": archive_name,
            "artist_name": artist_name,
            "relative_path": relative_path
        }
        return json_content

class ArchiveHandler:
    """压缩包处理类"""
    
    @staticmethod
    def check_archive_integrity(archive_path: str) -> bool:
        """检查压缩包完整性
        
        Args:
            archive_path: 压缩包路径
            
        Returns:
            bool: 压缩包是否完整
        """
        try:
            # 尝试使用zipfile
            try:
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    # 测试压缩包完整性
                    if zf.testzip() is not None:
                        logger.warning(f"[#process]压缩包损坏: {os.path.basename(archive_path)}")
                        return False
                    return True
            except zipfile.BadZipFile:
                # 如果不是zip文件，使用7z测试
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                result = subprocess.run(
                    ['7z', 't', archive_path],
                    capture_output=True,
                    text=True,
                    encoding='gbk',
                    errors='ignore',
                    startupinfo=startupinfo,
                    check=False
                )
                
                if result.returncode != 0:
                    logger.warning(f"[#process]压缩包损坏: {os.path.basename(archive_path)}")
                    return False
                return True
                
        except Exception as e:
            logger.error(f"[#process]检查压缩包完整性失败: {str(e)}")
            return False
    
    @staticmethod
    def load_yaml_uuid_from_archive(archive_path: str) -> Optional[str]:
        """从压缩包中加载YAML文件的UUID"""
        # 首先检查压缩包完整性
        if not ArchiveHandler.check_archive_integrity(archive_path):
            return None
            
        try:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                for name in zf.namelist():
                    if name.endswith('.yaml'):
                        return os.path.splitext(name)[0]
        except zipfile.BadZipFile:
            # 如果不是zip文件，尝试使用7z
            return ArchiveHandler._load_uuid_from_7z(archive_path, '.yaml')
        except Exception as e:
            logger.error(f"[#process]读取压缩包失败: {archive_path}")
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
    def extract_yaml_from_archive(archive_path: str, yaml_uuid: str, temp_dir: str) -> Optional[str]:
        """从压缩包中提取YAML文件
        
        Args:
            archive_path: 压缩包路径
            yaml_uuid: YAML文件的UUID（不含扩展名）
            temp_dir: 临时目录路径
            
        Returns:
            Optional[str]: 提取的YAML文件路径，失败返回None
        """
        yaml_path = os.path.join(temp_dir, f"{yaml_uuid}.yaml")
        
        try:
            # 尝试使用zipfile
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extract(f"{yaml_uuid}.yaml", temp_dir)
                return yaml_path
        except Exception:
            # 如果zipfile失败，尝试使用7z
            try:
                subprocess.run(
                    ['7z', 'e', archive_path, f"{yaml_uuid}.yaml", f"-o{temp_dir}"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True
                )
                if os.path.exists(yaml_path):
                    return yaml_path
            except subprocess.CalledProcessError:
                logger.warning(f"[#process]提取YAML文件失败: {os.path.basename(archive_path)}")
        
        return None

    @staticmethod
    def delete_files_from_archive(archive_path: str, files_to_delete: List[str]) -> bool:
        """从压缩包中删除指定文件
        
        Args:
            archive_path: 压缩包路径
            files_to_delete: 要删除的文件列表
            
        Returns:
            bool: 是否删除成功
        """
        try:
            # 尝试使用zipfile
            try:
                with zipfile.ZipFile(archive_path, 'a') as zf:
                    for file in files_to_delete:
                        try:
                            zf.remove(file)
                            logger.info(f"[#process]删除文件: {file}")
                        except KeyError:
                            pass
                return True
            except Exception:
                # 如果zipfile失败，使用7z
                for file in files_to_delete:
                    try:
                        subprocess.run(
                            ['7z', 'd', archive_path, file],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=True
                        )
                        logger.info(f"[#process]删除文件: {file}")
                    except subprocess.CalledProcessError:
                        continue
                return True
        except Exception as e:
            logger.error(f"[#process]删除文件失败: {str(e)}")
            return False

    @staticmethod
    def add_json_to_archive(archive_path: str, json_path: str, json_name: str) -> bool:
        """添加JSON文件到压缩包
        
        Args:
            archive_path: 压缩包路径
            json_path: JSON文件路径
            json_name: 要保存在压缩包中的文件名
            
        Returns:
            bool: 是否添加成功
        """
        try:
            # 尝试使用zipfile
            with zipfile.ZipFile(archive_path, 'a') as zf:
                zf.write(json_path, json_name)
                logger.info(f"[#process]添加JSON文件: {json_name}")
                return True
        except Exception:
            # 如果zipfile失败，使用7z
            try:
                subprocess.run(
                    ['7z', 'a', archive_path, json_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True
                )
                logger.info(f"[#process]添加JSON文件: {json_name}")
                return True
            except subprocess.CalledProcessError:
                logger.error(f"[#process]添加JSON文件失败: {json_name}")
                return False

    @staticmethod
    def convert_yaml_archive_to_json(archive_path: str) -> Optional[Dict[str, Any]]:
        """转换压缩包中的YAML文件为JSON格式"""
        try:
            # 首先检查压缩包完整性
            if not ArchiveHandler.check_archive_integrity(archive_path):
                logger.warning(f"[#process]跳过损坏的压缩包: {os.path.basename(archive_path)}")
                return None
            
            # 检查是否存在YAML文件
            yaml_uuid = ArchiveHandler.load_yaml_uuid_from_archive(archive_path)
            if not yaml_uuid:
                return None
            
            # 创建临时目录
            temp_dir = os.path.join(os.path.dirname(archive_path), '.temp_extract')
            os.makedirs(temp_dir, exist_ok=True)
            
            try:
                # 1. 提取YAML文件
                yaml_path = ArchiveHandler.extract_yaml_from_archive(archive_path, yaml_uuid, temp_dir)
                if not yaml_path or not os.path.exists(yaml_path):
                    logger.error(f"[#process]无法提取YAML文件: {os.path.basename(archive_path)}")
                    return None
                
                # 2. 读取并转换YAML数据
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    yaml_data = yaml.safe_load(f)
                
                # 3. 检查是否存在同名JSON文件
                json_files = []
                try:
                    with zipfile.ZipFile(archive_path, 'r') as zf:
                        json_files = [f for f in zf.namelist() if f.endswith('.json')]
                except Exception:
                    # 如果zipfile失败，使用7z列出文件
                    try:
                        result = subprocess.run(
                            ['7z', 'l', archive_path],
                            capture_output=True,
                            text=True,
                            encoding='gbk',
                            errors='ignore',
                            check=True
                        )
                        if result.returncode == 0:
                            json_files = [line.split()[-1] for line in result.stdout.splitlines() 
                                        if line.strip() and line.endswith('.json')]
                    except subprocess.CalledProcessError:
                        pass
                
                # 如果存在JSON文件，删除它们并生成新的UUID
                if json_files:
                    logger.info(f"[#process]发现现有JSON文件，将删除并生成新UUID: {os.path.basename(archive_path)}")
                    ArchiveHandler.delete_files_from_archive(archive_path, json_files)
                    yaml_uuid = UuidHandler.generate_uuid(UuidHandler.load_existing_uuids())
                
                # 4. 转换为JSON格式
                json_data = JsonHandler.convert_yaml_to_json(yaml_data)
                json_data["uuid"] = yaml_uuid
                
                # 5. 保存JSON文件
                json_path = os.path.join(temp_dir, f"{yaml_uuid}.json")
                if not JsonHandler.save(json_path, json_data):
                    logger.error(f"[#process]保存JSON文件失败: {os.path.basename(archive_path)}")
                    return None
                
                # 6. 添加JSON到压缩包并删除YAML
                if ArchiveHandler.add_json_to_archive(archive_path, json_path, f"{yaml_uuid}.json"):
                    # 删除YAML文件
                    ArchiveHandler.delete_files_from_archive(archive_path, [f"{yaml_uuid}.yaml"])
                    logger.info(f"[#process]✅ YAML转换完成: {os.path.basename(archive_path)}")
                    return json_data
                
                logger.error(f"[#process]更新压缩包失败: {os.path.basename(archive_path)}")
                return None
                
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
                
        except Exception as e:
            logger.error(f"[#process]转换失败 {os.path.basename(archive_path)}: {str(e)}")
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

class PathHandler:
    """路径处理类"""
    
    @staticmethod
    def get_artist_name(target_directory: str, archive_path: str, mode: str = 'multi') -> str:
        """从压缩文件路径中提取艺术家名称
        
        Args:
            target_directory: 目标目录路径
            archive_path: 压缩文件路径
            mode: 处理模式，'multi'表示多人模式，'single'表示单人模式
            
        Returns:
            str: 艺术家名称
        """
        if mode == 'single':
            # 单人模式：直接使用目标目录的最后一个文件夹名作为画师名
            return Path(target_directory).name
        else:
            # 多人模式：使用相对路径的第一级子文件夹名作为画师名
            try:
                # 将路径转换为相对路径
                archive_path = Path(archive_path)
                target_path = Path(target_directory)
                
                # 获取相对于目标目录的路径
                relative_path = archive_path.relative_to(target_path)
                
                # 获取第一级子文件夹名
                if len(relative_path.parts) > 0:
                    return relative_path.parts[0]
                
                logger.warning(f"[#process]无法从路径提取画师名: {archive_path}")
                return ""
                
            except Exception as e:
                logger.error(f"[#process]提取画师名失败: {str(e)}")
                return ""
    
    @staticmethod
    def get_relative_path(target_directory: str, archive_path: str) -> str:
        """获取相对路径
        
        Args:
            target_directory: 目标目录路径
            archive_path: 压缩文件路径
            
        Returns:
            str: 相对路径，不包含文件名
        """
        try:
            # 将路径转换为Path对象并规范化
            archive_path = Path(archive_path).resolve()
            target_path = Path(target_directory).resolve()
            
            # 获取相对路径
            relative_path = archive_path.relative_to(target_path)
            
            # 如果是直接在目标目录下的文件，返回"."
            if not relative_path.parent.parts:
                return "."
                
            # 返回父目录的相对路径（不包含文件名）
            return str(relative_path.parent)
            
        except Exception as e:
            # 如果出错，记录错误但返回一个安全的默认值
            logger.error(f"[#process]获取相对路径失败 ({archive_path}): {str(e)}")
            return "."
    
    @staticmethod
    def get_uuid_path(uuid_directory: str, timestamp: str) -> str:
        """根据时间戳生成按年月日分层的UUID文件路径"""
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
    
    @staticmethod
    def get_short_path(long_path: str) -> str:
        """将长路径转换为短路径格式"""
        try:
            import win32api
            return win32api.GetShortPathName(long_path)
        except ImportError:
            return long_path

class UuidHandler:
    """UUID处理类"""
    
    @staticmethod
    def generate_uuid(existing_uuids: set) -> str:
        """生成一个唯一的16位UUID"""
        while True:
            new_uuid = generate(size=16)
            if new_uuid not in existing_uuids:
                return new_uuid
    
    @staticmethod
    def load_existing_uuids() -> set:
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

class YamlHandler:
    """YAML文件处理类"""
    
    @staticmethod
    def read_yaml(yaml_path: str) -> list:
        """读取YAML文件内容，如果文件损坏则尝试修复"""
        if not os.path.exists(yaml_path):
            return []
            
        try:
            with open(yaml_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                if not isinstance(data, list):
                    data = [data] if data is not None else []
                return data
        except yaml.YAMLError as e:
            logger.error(f"YAML文件 {yaml_path} 已损坏，尝试修复...")
            return YamlHandler.repair_yaml_file(yaml_path)
        except Exception as e:
            logger.error(f"读取YAML文件时出错 {yaml_path}: {e}")
            return []
    
    @staticmethod
    def write_yaml(yaml_path: str, data: list) -> bool:
        """将数据写入YAML文件，确保写入完整性"""
        temp_path = yaml_path + '.tmp'
        try:
            with open(temp_path, 'w', encoding='utf-8') as file:
                yaml.dump(data, file, allow_unicode=True)
            
            try:
                with open(temp_path, 'r', encoding='utf-8') as file:
                    yaml.safe_load(file)
            except yaml.YAMLError:
                logger.error(f"写入的YAML文件验证失败: {yaml_path}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return False
                
            if os.path.exists(yaml_path):
                os.replace(temp_path, yaml_path)
            else:
                os.rename(temp_path, yaml_path)
            return True
                
        except Exception as e:
            logger.error(f"写入YAML文件时出错 {yaml_path}: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False
    
    @staticmethod
    def repair_yaml_file(yaml_path: str) -> list:
        """修复损坏的YAML文件"""
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

            YamlHandler.write_yaml(yaml_path, valid_data)
            return valid_data

        except Exception as e:
            logger.error(f"修复YAML文件时出错 {yaml_path}: {e}")
            return []

class FileSystemHandler:
    """文件系统操作类"""
    
    @staticmethod
    def warm_up_cache(target_directory: str, max_workers: int = 32) -> None:
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

class ArchiveProcessor:
    """压缩文件处理类"""
    
    def __init__(self, target_directory: str, uuid_directory: str, max_workers: int = 5):
        self.target_directory = target_directory
        self.uuid_directory = uuid_directory
        self.max_workers = max_workers
    
    def process_archives(self) -> bool:
        """处理所有压缩文件"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        os.makedirs(self.uuid_directory, exist_ok=True)

        logger.info("[#current_stats]🔍 开始扫描压缩文件")
        scan_task = logger.info("[#current_progress]扫描文件")
        
        archive_files = []
        file_count = 0
        for root, _, files in os.walk(self.target_directory):
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
        existing_uuids = UuidHandler.load_existing_uuids()
        logger.info(f"[#current_stats]📝 已加载 {len(existing_uuids)} 个现有UUID")
        
        process_task = logger.info("[#current_progress]处理压缩文件")
        
        # 添加跳过计数器
        skip_count = 0
        
        def process_with_progress(archive_path):
            nonlocal skip_count
            try:
                start_time = time.time()
                result = self.process_single_archive(archive_path, timestamp)
                
                # 记录处理时长
                duration = time.time() - start_time
                if duration > 30:
                    logger.warning(f"[#process]⏱️ 处理时间过长: {os.path.basename(archive_path)} 耗时{duration:.1f}秒")
                
                return result
            except Exception as e:
                logger.error(f"[#process]🔥 严重错误: {str(e)}")
                raise
        
        # 修改任务分发方式
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
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
    
    def process_single_archive(self, archive_path: str, timestamp: str) -> bool:
        """处理单个压缩文件"""
        try:
            # 检查是否存在YAML文件并转换为JSON
            json_data = ArchiveHandler.convert_yaml_archive_to_json(archive_path)
            if json_data:
                logger.info(f"[#process]检测到YAML文件: {os.path.basename(archive_path)}")
                logger.info(f"[#process]YAML转换完成: {os.path.basename(archive_path)}")
                return True  # 如果是YAML转换流程,完成后直接返回
            
            # 获取文件信息
            artist_name = PathHandler.get_artist_name(self.target_directory, archive_path, args.mode if hasattr(args, 'mode') else 'multi')
            archive_name = os.path.basename(archive_path)
            relative_path = PathHandler.get_relative_path(self.target_directory, archive_path)
            
            # 检查是否已存在UUID JSON文件
            json_uuid = ArchiveHandler.load_json_uuid_from_archive(archive_path)
            if json_uuid:
                # 验证JSON文件内容
                try:
                    with zipfile.ZipFile(archive_path, 'r') as zf:
                        with zf.open(f"{json_uuid}.json") as f:
                            json_content = orjson.loads(f.read())
                            # 检查是否是我们的UUID记录文件
                            if "uuid" in json_content:
                                # 检查是否需要更新
                                if JsonHandler.check_and_update_record(json_content, archive_name, artist_name, relative_path, timestamp):
                                    logger.info(f"[#process]检测到记录需要更新: {os.path.basename(archive_path)}")
                                    # 更新记录
                                    json_content = JsonHandler.update_record(json_content, archive_name, artist_name, relative_path, timestamp)
                                    # 创建临时文件并更新压缩包
                                    temp_dir = os.path.join(os.path.dirname(archive_path), '.temp_update')
                                    os.makedirs(temp_dir, exist_ok=True)
                                    try:
                                        temp_json = os.path.join(temp_dir, f"{json_uuid}.json")
                                        if JsonHandler.save(temp_json, json_content):
                                            # 更新压缩包中的JSON
                                            try:
                                                with zipfile.ZipFile(archive_path, 'a') as zf:
                                                    zf.write(temp_json, f"{json_uuid}.json")
                                                logger.info(f"[#update]✅ 已更新压缩包中的JSON记录: {archive_name}")
                                            except Exception:
                                                subprocess.run(
                                                    ['7z', 'u', archive_path, temp_json],
                                                    stdout=subprocess.DEVNULL,
                                                    stderr=subprocess.DEVNULL,
                                                    check=True
                                                )
                                                logger.info(f"[#update]✅ 已更新压缩包中的JSON记录: {archive_name}")
                                    finally:
                                        shutil.rmtree(temp_dir, ignore_errors=True)
                                else:
                                    logger.info(f"[#process]记录无需更新: {os.path.basename(archive_path)}")
                                return True
                            else:
                                logger.info(f"[#process]压缩包中的JSON不是UUID记录，将创建新记录: {os.path.basename(archive_path)}")
                except Exception:
                    logger.info(f"[#process]压缩包中的JSON无法读取或格式不正确，将创建新记录: {os.path.basename(archive_path)}")
            
            # 获取或创建新的UUID
            uuid_value = UuidHandler.generate_uuid(UuidHandler.load_existing_uuids())
            json_filename = f"{uuid_value}.json"
            
            logger.info(f"[#current_stats]处理文件: {archive_name}")
            logger.info(f"[#current_stats]艺术家: {artist_name}")
            logger.info(f"[#current_stats]相对路径: {relative_path}")
            
            # 获取按年月日分层的目录路径
            day_dir = PathHandler.get_uuid_path(self.uuid_directory, timestamp)
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
    
    def __init__(self, args, target_directory: str):
        self.args = args
        self.target_directory = target_directory
        self.max_workers = min(32, (multiprocessing.cpu_count() * 4) + 1)
        self.confirmed_artists = set()
        self.uuid_directory = r'E:\1BACKUP\ehv\uuid'
        self.archive_processor = ArchiveProcessor(self.target_directory, self.uuid_directory, self.max_workers)
        self.uuid_record_manager = UuidRecordManager(self.uuid_directory)

    def _confirm_artists(self) -> None:
        """确认画师信息"""
        print("\n正在扫描画师信息...")
        artists = set()
        
        # 扫描所有压缩文件以获取画师信息
        for root, _, files in os.walk(self.target_directory):
            for file in files:
                if file.endswith(('.zip', '.rar', '.7z')):
                    archive_path = os.path.join(root, file)
                    artist = PathHandler.get_artist_name(self.target_directory, archive_path, self.args.mode)
                    if artist:
                        artists.add(artist)
        
        # 显示画师信息并等待确认
        if self.args.mode == 'single':
            if len(artists) > 1:
                print("\n⚠️ 警告：在单人模式下检测到多个画师名称：")
                for i, artist in enumerate(sorted(artists), 1):
                    print(f"{i}. {artist}")
                print("\n请确认这是否符合预期？如果不符合，请检查目录结构。")
            elif len(artists) == 1:
                print(f"\n检测到画师: {next(iter(artists))}")
            else:
                print("\n⚠️ 警告：未检测到画师名称！")
            
            input("\n按回车键继续...")
            
        else:  # 多人模式
            print(f"\n共检测到 {len(artists)} 个画师目录：")
            for i, artist in enumerate(sorted(artists), 1):
                print(f"{i}. {artist}")
            
            input("\n按回车键继续...")
        
        self.confirmed_artists = artists

    def execute_tasks(self) -> None:
        """执行所有任务"""
        # 首先确认画师信息
        self._confirm_artists()
        
        # 然后初始化日志系统
        init_TextualLogger()
        
        logger.info(f"[#current_stats]当前模式: {'多人模式' if self.args.mode == 'multi' else '单人模式'}")
        if self.confirmed_artists:
            logger.info(f"[#current_stats]已确认画师: {', '.join(sorted(self.confirmed_artists))}")
            logger.info(f"[#current_stats]开始下一步")

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

    def _execute_convert_task(self) -> None:
        """执行YAML转JSON任务"""
        self.uuid_record_manager.convert_yaml_to_json_structure()
        sys.exit(0)

    def _execute_reorganize_task(self) -> None:
        """执行重组任务"""
        logger.info("[#current_stats]📝 开始重新组织 UUID 文件...")
        self.uuid_record_manager.reorganize_uuid_files()

    def _execute_update_records_task(self) -> None:
        """执行更新记录任务"""
        logger.info("[#current_stats]📝 开始更新 UUID 记录...")
        self.uuid_record_manager.update_json_records()

    def _execute_auto_sequence(self) -> None:
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

    def _execute_normal_process(self) -> None:
        """执行普通处理流程"""
        if self.args.mode == 'multi':
            FileSystemHandler.warm_up_cache(self.target_directory, self.max_workers)
        self.archive_processor.process_archives()

    def _process_uuid_json(self) -> None:
        """处理UUID-JSON相关任务"""
        if self.args.mode == 'multi':
            FileSystemHandler.warm_up_cache(self.target_directory, self.max_workers)
        skip_limit_reached = self.archive_processor.process_archives()
        
        if skip_limit_reached:
            logger.info("[#current_stats]⏩ 由于连续跳过次数达到限制，提前进入下一阶段")

    def _run_auto_filename_script(self) -> None:
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

    def _validate_json_records(self) -> None:
        """验证JSON记录文件"""
        json_record_path = os.path.join(self.uuid_directory, 'uuid_records.json')
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

class UuidRecordManager:
    """UUID记录管理类"""
    
    def __init__(self, uuid_directory: str = r'E:\1BACKUP\ehv\uuid'):
        self.uuid_directory = uuid_directory
    
    def reorganize_uuid_files(self) -> None:
        """根据最后修改时间重新组织UUID文件的目录结构"""
        logger.info("[#current_stats]🔄 开始重新组织UUID文件...")
        
        json_record_path = os.path.join(self.uuid_directory, 'uuid_records.json')
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
                    
                    year_dir = os.path.join(self.uuid_directory, year)
                    month_dir = os.path.join(year_dir, month)
                    day_dir = os.path.join(month_dir, day)
                    target_path = os.path.join(day_dir, f"{uuid}.json")
                    
                    current_json_path = None
                    for root, _, files in os.walk(self.uuid_directory):
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
    
    def update_json_records(self) -> None:
        """更新JSON记录文件，确保所有记录都被保存"""
        logger.info("[#current_stats]🔄 开始更新JSON记录...")
        
        json_record_path = os.path.join(self.uuid_directory, 'uuid_records.json')
        
        existing_records = JsonHandler.load(json_record_path)
        
        total_files = 0
        processed = 0
        
        # 首先计算总文件数
        for root, _, files in os.walk(self.uuid_directory):
            total_files += sum(1 for file in files if file.endswith('.json') and file != 'uuid_records.json')
        
        # 遍历目录结构查找所有JSON文件
        for root, _, files in os.walk(self.uuid_directory):
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
    
    def convert_yaml_to_json_structure(self) -> None:
        """将现有的YAML文件结构转换为JSON结构"""
        logger.info("[#current_stats]🔄 开始转换YAML到JSON结构...")
        
        yaml_record_path = os.path.join(self.uuid_directory, 'uuid_records.yaml')
        json_record_path = os.path.join(self.uuid_directory, 'uuid_records.json')
        
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
        for root, _, files in os.walk(self.uuid_directory):
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
    
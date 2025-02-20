import os
import uuid
import yaml
import time
import subprocess
import difflib
from pathlib import Path
from nanoid import generate
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import pyperclip
import sys
import threading
import logging
from datetime import datetime
from colorama import init, Fore, Style
from logging.handlers import RotatingFileHandler
import win32file
import win32con
import shutil
import logging
import numpy as np
import yaml as yaml_c
from rich.progress import Progress, BarColumn, TextColumn
# 导入自定义日志模块
# 添加父目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from tui.config import create_config_app
# ================= 日志配置 =================
script_name = os.path.basename(__file__).replace('.py', '')
logspath=r"D:/1VSCODE/1ehv/logs"
LOG_BASE_DIR = Path(logspath + f"/{script_name}")
DATE_STR = datetime.now().strftime("%Y%m%d")
HOUR_STR = datetime.now().strftime("%H")  # 新增小时目录
LOG_DIR = LOG_BASE_DIR / DATE_STR / HOUR_STR  # 修改目录结构
LOG_FILE = LOG_DIR / f"{datetime.now().strftime('%M%S')}.log"  # 文件名只保留分秒

# 创建日志目录
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 配置日志格式
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
formatter = logging.Formatter(LOG_FORMAT)

# 文件处理器
file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)

# 控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

# 主日志器配置
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 禁用第三方库的日志
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
# 初始化 colorama
init()

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
                    return records
        except Exception:
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
            
            return valid_records
    except Exception as e:
        print(f"修复UUID记录文件失败: {e}")
        return []

def load_existing_uuids():
    """添加超时机制的加载函数"""
    logger.info("🔍 开始加载现有UUID...")
    start_time = time.time()
    loader = FastUUIDLoader(r'E:\1BACKUP\ehv\uuid\uuid_records.yaml')
    
    # 超时设置（5分钟）
    timeout = 300  
    last_percent = 0
    
    while True:
        if time.time() - start_time > timeout:
            raise TimeoutError(f"UUID加载超时，已等待{timeout}秒")
            
        progress = loader.get_loading_progress()
        
        # 进度监控
        if progress['percentage'] != last_percent:
            logger.info(f"⏳ {progress['message']} [{progress['percentage']:.1f}%]")
            last_percent = progress['percentage']
            
        if progress['percentage'] >= 100:
            if progress['message'].startswith("构建失败"):
                raise RuntimeError("缓存构建失败")
            break
            
        # 动态调整轮询间隔
        sleep_time = 0.5 if progress['percentage'] < 50 else 0.1
        time.sleep(sleep_time)
    
    uuids = loader.get_uuids()
    elapsed = time.time() - start_time
    logger.info(f"✅ 加载完成！共加载 {len(uuids)} 个UUID，耗时 {elapsed:.2f} 秒")
    return uuids

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

def get_artist_name(target_directory, archive_path):
    """从压缩文件路径中提取艺术家名称。"""
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
        logging.info(f"✨ 创建新的YAML记录 [UUID: {new_uuid}]")
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
        logging.info(f"📝 {os.path.basename(archive_name)}\n    " + "\n    ".join(changes))

    if not changes_data:
        logging.info("✓ 未检测到变化")
        return False

    logging.info(f"🔄 检测到变化，添加新记录...")
    new_record = {
        'Timestamp': timestamp,
        **changes_data
    }

    data.append(new_record)
    write_yaml(yaml_path, data)
    logging.info("✅ 成功更新YAML文件")
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
        yaml_uuid = load_yaml_uuid_from_archive(archive_path)
        artist_name = get_artist_name(target_directory, archive_path)
        archive_name = os.path.basename(archive_path)
        relative_path = get_relative_path(target_directory, archive_path)
        
        if yaml_uuid:
            yaml_filename = f"{yaml_uuid}.yaml"
            # 更新现有UUID的记录
            add_uuid_to_file(yaml_uuid, timestamp, archive_name, artist_name, relative_path)
        else:
            new_uuid = generate_uuid(load_existing_uuids())
            yaml_filename = f"{new_uuid}.yaml"
            # 添加新UUID的记录
            add_uuid_to_file(new_uuid, timestamp, archive_name, artist_name, relative_path)
            yaml_uuid = new_uuid

        # 获取按年月日分层的目录路径
        day_dir = get_uuid_path(uuid_directory, timestamp)
        yaml_path = os.path.join(day_dir, yaml_filename)
        
        if os.path.exists(yaml_path):
            updated = update_yaml(yaml_path, artist_name, archive_name, relative_path, timestamp)
            if not updated:
                logging.info(f"⏭️ 跳过更新: {archive_name}")
                return False
        else:
            create_yaml(yaml_path, artist_name, archive_name, relative_path, timestamp, yaml_uuid)

        # 确保yaml文件存在后再添加到压缩包
        if os.path.exists(yaml_path):
            try:
                add_yaml_to_zip(yaml_path, archive_path)
                logging.info(f"✅ 已添加YAML到压缩包: {archive_name}")
            except Exception as e:
                logging.error(f"添加YAML到压缩包失败: {archive_name} - {str(e)}")
        else:
            logging.error(f"YAML文件不存在，无法添加到压缩包: {archive_name}")
            
        return True

    except subprocess.CalledProcessError:
        logging.error(f"发现损坏的压缩包: {archive_path}")
        return True
    except Exception as e:
        logging.info(f"处理压缩包时出错 {archive_path}: {str(e)}")
        return True  # 错误情况不计入跳过次数

def warm_up_cache(target_directory, max_workers=32, handler=None):
    """并行预热系统缓存"""
    return _warm_up_cache_internal(target_directory, max_workers)

def _warm_up_cache_internal(target_directory, max_workers):
    """预热缓存的内部实现"""
    logging.info("🔄 开始预热系统缓存")
    
    # 首先计算总文件数
    total_files = 0
    for root, _, files in os.walk(target_directory):
        total_files += sum(1 for file in files if file.endswith(('.zip', '.rar', '.7z')))
    
    scan_task = logging.info("扫描文件")
    archive_files = []
    current_count = 0
    for root, _, files in os.walk(target_directory):
        for file in files:
            if file.endswith(('.zip', '.rar', '.7z')):
                archive_files.append(os.path.join(root, file))
                current_count += 1
                logging.info("已扫描 %d 个文件", current_count)
    
    logging.info(f"📊 找到 {total_files} 个文件待预热")
    
    warm_task = logging.info("预热缓存")
    
    def read_file_header_with_progress(file_path):
        try:
            # 使用Windows API直接打开文件
            handle = win32file.CreateFile(
                file_path,
                win32con.GENERIC_READ,
                win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_FLAG_SEQUENTIAL_SCAN,  # 提示系统这是顺序读取
                None
            )
            try:
                # 读取文件头部
                win32file.ReadFile(handle, 32)
            finally:
                handle.Close()
            logging.info(f"✅ 已预热: {os.path.basename(file_path)}")
        except Exception as e:
            logging.info(f"预热失败: {os.path.basename(file_path)} - {str(e)}")
        finally:
            logging.info( advance=1)

    # 使用更多线程
    with ThreadPoolExecutor(max_workers=128) as executor:
        executor.map(read_file_header_with_progress, archive_files)
        
    logging.info("✨ 缓存预热完成")

def process_archives(target_directory, max_workers=5, handler=None):
    """遍历目录中的压缩文件，生成或更新YAML文件。"""
    if handler is None:
        return _process_archives_internal(target_directory, max_workers)
    else:
        return _process_archives_internal(target_directory, max_workers)

def _process_archives_internal(target_directory, max_workers):
    """处理压缩文件的内部实现"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    uuid_directory = r'E:\1BACKUP\ehv\uuid'
    os.makedirs(uuid_directory, exist_ok=True)

    logging.info("🔍 开始扫描压缩文件")
    
    scan_task = logging.info("扫描文件")
    
    archive_files = []
    file_count = 0
    for root, _, files in os.walk(target_directory):
        for file in files:
            if file.endswith(('.zip', '.rar', '.7z')):
                full_path = os.path.join(root, file)
                archive_files.append((full_path, os.path.getmtime(full_path)))
                file_count += 1
                logging.info(f"已扫描 {file_count} 个文件")
    
    # 按修改时间排序
    archive_files.sort(key=lambda x: x[1], reverse=True)
    archive_files = [file_path for file_path, _ in archive_files]
    
    logging.info(f"📊 共发现 {file_count} 个压缩文件")
    
    # 加载现有UUID
    logging.info("💾 正在加载现有UUID...")
    existing_uuids = load_existing_uuids()
    logging.info(f"📝 已加载 {len(existing_uuids)} 个现有UUID")
    
    process_task = logging.info("处理压缩文件")
    
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
                logging.warning(f"⏱️ 处理时间过长: {os.path.basename(archive_path)} 耗时{duration:.1f}秒")
            
            return result
        except Exception as e:
            logging.error(f"🔥 严重错误: {str(e)}")
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
            logging.info(f"🗂️ 已提交 {submitted}/{total_files} 个文件到处理队列")

        # 添加超时机制
        for future in as_completed(futures, timeout=300):
            try:
                result = future.result(timeout=60)  # 每个任务最多60秒
                if result == "SKIP_LIMIT_REACHED":
                    logging.info("⏩ 达到跳过限制，取消剩余任务...")
                    for f in futures:
                        f.cancel()
                    break
            except TimeoutError:
                logging.warning("⌛ 任务超时，已跳过")
                skip_count += 1
            except Exception as e:
                logging.error(f"任务失败: {str(e)}")
                skip_count = 0

    if skip_count >= 100:
        logging.info("🔄 由于连续跳过次数达到100，提前结束当前阶段")
    else:
        logging.info("✨ 所有文件处理完成")
    
    return skip_count >= 100  # 返回是否因为跳过次数达到限制而提前结束

def load_yaml_uuid_from_archive(archive_path):
    """尝试从压缩包内加载 YAML 文件以获取 UUID。"""
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
            encoding='gbk',  # 使用GBK编码
            errors='ignore',  # 忽略无法解码的字符
            startupinfo=startupinfo,
            check=False
        )
        
        if result.returncode != 0:
            print(f"列出压缩包内容失败: {archive_path}")
            return None
            
        if result.stdout:
            for line in result.stdout.splitlines():
                if not line:
                    continue
                    
                line = line.strip()
                if line.endswith('.yaml'):
                    parts = line.split()
                    if parts:
                        yaml_filename = parts[-1]
                        yaml_uuid = os.path.splitext(yaml_filename)[0]
                        return yaml_uuid

    except Exception as e:
        print(f"无法加载压缩包中的 YAML 文件 ({archive_path}): {e}")
        
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
            "description": "执行完整处理流程：UUID-YAML -> 自动文件名 -> UUID-YAML",
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
        }
    }

    # 创建并运行配置界面
    app = create_config_app(
        program=__file__,
        checkbox_options=checkbox_options,
        input_options=input_options,
        title="UUID-YAML 工具",
        preset_configs=preset_configs
    )
    app.run()

def reorganize_uuid_files(uuid_directory=r'E:\1BACKUP\ehv\uuid', handler=None):
    """根据最后修改时间重新组织 UUID 文件的目录结构"""
    logging.info("🔄 开始重新组织 UUID 文件...")
    
    # 加载记录文件
    uuid_record_path = os.path.join(uuid_directory, 'uuid_records.yaml')
    if not os.path.exists(uuid_record_path):
        logging.info("❌ UUID 记录文件不存在")
        return
    
    try:
        with open(uuid_record_path, 'r', encoding='utf-8') as file:
            records = yaml.safe_load(file) or []
    except Exception as e:
        logging.info(f"❌ 读取记录文件失败: {e}")
        return
    
    
    # 遍历所有记录
    for record in records:
        try:
            uuid = record.get('UUID')
            if not uuid:
                continue
                
            # 获取时间戳
            timestamp = record.get('LastModified') or record.get('CreatedAt')
            if not timestamp:
                continue
            
            # 查找当前 UUID 的 YAML 文件
            yaml_found = False
            current_yaml_path = None
            
            # 在目录结构中查找现有的 YAML 文件
            for root, _, files in os.walk(uuid_directory):
                for file in files:
                    if file == f"{uuid}.yaml":
                        current_yaml_path = os.path.join(root, file)
                        yaml_found = True
                        break
                if yaml_found:
                    break
            
            if not yaml_found:
                logging.info(f"⚠️ 未找到 UUID {uuid} 的 YAML 文件")
                continue
            
            # 获取目标路径
            try:
                date = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                year = str(date.year)
                month = f"{date.month:02d}"
                day = f"{date.day:02d}"
                
                # 创建年月日层级目录
                year_dir = os.path.join(uuid_directory, year)
                month_dir = os.path.join(year_dir, month)
                day_dir = os.path.join(month_dir, day)
                target_path = os.path.join(day_dir, f"{uuid}.yaml")
                
                # 如果文件已经在正确的位置，跳过
                if current_yaml_path == target_path:
                    logging.info(f"✓ UUID {uuid} 已在正确位置")
                    continue
                
                # 如果文件在年/月目录下但没有日期目录
                current_parts = current_yaml_path.split(os.sep)
                target_parts = target_path.split(os.sep)
                
                # 检查是否需要移动
                need_move = True
                if len(current_parts) >= 2:
                    current_year = current_parts[-3] if len(current_parts) >= 3 else None
                    current_month = current_parts[-2] if len(current_parts) >= 2 else None
                    
                    if current_year == year and current_month == month:
                        # 如果年月正确，只需要移动到日期目录
                        logging.info(f"📁 UUID {uuid} 已在正确的年月目录，移动到日期目录")
                    
                if need_move:
                    # 确保目标目录存在
                    os.makedirs(day_dir, exist_ok=True)
                    # 移动文件
                    shutil.move(current_yaml_path, target_path)
                
            except ValueError as e:
                logging.info(f"❌ UUID {uuid} 的时间戳格式无效: {timestamp}")
            
        except Exception as e:
            logging.info(f"❌ 处理 UUID {uuid} 时出错: {e}")

    
    logging.info("✨ UUID 文件重组完成")

def update_uuid_records(uuid_directory=r'E:\1BACKUP\ehv\uuid', handler=None):
    """更新 UUID 记录文件，确保所有 UUID 都被记录"""
    logging.info("🔄 开始更新 UUID 记录...")
    
    uuid_record_path = os.path.join(uuid_directory, 'uuid_records.yaml')
    
    # 加载现有记录
    existing_records = {}
    if os.path.exists(uuid_record_path):
        try:
            with open(uuid_record_path, 'r', encoding='utf-8') as file:
                records = yaml.safe_load(file) or []
                existing_records = {record['UUID']: record for record in records if 'UUID' in record}
        except Exception as e:
            logging.info(f"❌ 读取记录文件失败: {e}")
            return
    
    # 遍历目录结构查找所有 YAML 文件
    new_uuids = []
    for root, _, files in os.walk(uuid_directory):
        for file in files:
            if file.endswith('.yaml') and file != 'uuid_records.yaml':
                uuid = os.path.splitext(file)[0]
                if uuid not in existing_records:
                    yaml_path = os.path.join(root, file)
                    try:
                        with open(yaml_path, 'r', encoding='utf-8') as f:
                            yaml_data = yaml.safe_load(f)
                            if yaml_data and isinstance(yaml_data, list):
                                latest_record = yaml_data[-1]
                                new_record = {
                                    'UUID': uuid,
                                    'CreatedAt': latest_record.get('Timestamp', ''),
                                    'ArchiveName': latest_record.get('ArchiveName', ''),
                                    'ArtistName': latest_record.get('ArtistName', ''),
                                    'LastModified': latest_record.get('Timestamp', ''),
                                    'LastPath': latest_record.get('RelativePath', '')
                                }
                                new_uuids.append(new_record)
                                logging.info(f"✨ 发现新 UUID: {uuid}")
                    except Exception as e:
                        logging.info(f"❌ 处理 YAML 文件失败 {yaml_path}: {e}")
    
    if new_uuids:
        # 更新记录文件
        all_records = list(existing_records.values()) + new_uuids
        try:
            # 创建备份
            if os.path.exists(uuid_record_path):
                backup_path = f"{uuid_record_path}.bak"
                shutil.copy2(uuid_record_path, backup_path)
            
            # 写入更新后的记录
            with open(uuid_record_path, 'w', encoding='utf-8') as file:
                yaml.dump(all_records, file, allow_unicode=True, sort_keys=False)
            
            logging.info(f"✅ 已添加 {len(new_uuids)} 个新 UUID 到记录")
        except Exception as e:
            logging.info(f"❌ 更新记录文件失败: {e}")
    else:
        logging.info("✓ 所有 UUID 都已在记录中")

def validate_yaml_file(file_path):
    """交互式YAML文件验证工具"""
    from yaml import scanner
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            print(f"✅ 文件验证通过，共包含{len(data)}条记录")
            return True
    except scanner.ScannerError as e:
        print(f"❌ 扫描错误：{e}")
        print(f"建议：检查第{e.problem_mark.line+1}行附近的缩进和符号")
    except yaml.parser.ParserError as e:
        print(f"❌ 解析错误：{e}")
        print(f"建议：检查第{e.problem_mark.line+1}行的语法结构")
    except Exception as e:
        print(f"❌ 未知错误：{e}")
    return False

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='处理文件UUID和YAML生成')
    parser.add_argument('-c', '--clipboard', action='store_true', help='从剪贴板读取路径')
    parser.add_argument('-m', '--mode', choices=['multi', 'single'], help='处理模式：multi(多人模式)或single(单人模式)')
    parser.add_argument('--no-artist', action='store_true', help='无画师模式 - 不添加画师名')
    parser.add_argument('--keep-timestamp', action='store_true', help='保持文件的修改时间')
    parser.add_argument('--path', help='要处理的路径')
    parser.add_argument('-a', '--auto-sequence', action='store_true', help='自动执行完整序列：UUID-YAML -> 自动文件名 -> UUID-YAML')
    parser.add_argument('-r', '--reorganize', action='store_true', help='重新组织 UUID 文件结构')
    parser.add_argument('-u', '--update-records', action='store_true', help='更新 UUID 记录文件')
    args = parser.parse_args()

    if len(sys.argv) == 1:  # 如果没有命令行参数，启动TUI界面
        main()
        sys.exit(0)

    # 处理路径参数
    if args.clipboard:
        try:
            target_directory = pyperclip.paste().strip().strip('"')
            if not os.path.exists(target_directory):
                print(f"{Fore.RED}剪贴板中的路径无效: {target_directory}{Style.RESET_ALL}")
                exit(1)
            print(f"{Fore.GREEN}已从剪贴板读取路径: {target_directory}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}从剪贴板读取路径失败: {e}{Style.RESET_ALL}")
            exit(1)
    else:
        target_directory = args.path or r"E:\1EHV"
        print(f"{Fore.GREEN}使用路径: {target_directory}{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}当前模式: {'多人模式' if args.mode == 'multi' else '单人模式'}{Style.RESET_ALL}")

    # 根据系统资源自动设置线程数
    import multiprocessing
    max_workers = min(32, (multiprocessing.cpu_count() * 4) + 1)
    
    
    if args.reorganize:
        logging.info("\n📝 开始重新组织 UUID 文件...")
        reorganize_uuid_files(r'E:\1BACKUP\ehv\uuid')
        
    if args.update_records:
        logging.info("\n📝 开始更新 UUID 记录...")
        update_uuid_records(r'E:\1BACKUP\ehv\uuid')
    
    if args.auto_sequence:
        logging.info("🔄 开始执行完整序列...")
        
        logging.info("\n📝 第1步：执行UUID-YAML处理...")
        if args.mode == 'multi':
            warm_up_cache(target_directory, max_workers)
        elif args.mode == 'single':
            logging.info("🔄 开始执行单人模式...")
            skip_limit_reached = process_archives(target_directory, max_workers)
        else:
            logging.info("🔄 开始执行无人模式...")
            skip_limit_reached = process_archives(target_directory, max_workers)
        
        if skip_limit_reached:
            logging.info("\n⏩ 由于连续跳过次数达到限制，提前进入下一阶段")
        
        logging.info("\n📝 第2步：执行自动文件名处理...")
        auto_filename_script = os.path.join(os.path.dirname(__file__), '011-自动唯一文件名.py')
        if os.path.exists(auto_filename_script):
            try:
                cmd = [sys.executable, auto_filename_script]
                if args.clipboard:
                    cmd.extend(['-c'])
                if args.mode:
                    cmd.extend(['-m', args.mode])
                
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
                        logging.info(line)
                
                logging.info("✅ 自动文件名处理完成")
            except subprocess.CalledProcessError as e:
                logging.info(f"自动文件名处理失败: {str(e)}")
                if e.output:
                    logging.info(f"错误输出: {e.output}")
        else:
            logging.info(f"找不到自动文件名脚本: {auto_filename_script}")
            
        logging.info("\n📝 第3步：再次执行UUID-YAML处理...")
        if args.mode == 'multi':
            warm_up_cache(target_directory, max_workers)
        process_archives(target_directory, max_workers)
        
        logging.info("\n✨ 完整序列执行完成！")
    
    elif not args.reorganize and not args.update_records:
        if args.mode == 'multi':
            warm_up_cache(target_directory, max_workers)
        process_archives(target_directory, max_workers)
    
    if not validate_yaml_file(r'E:\1BACKUP\ehv\uuid\uuid_records.yaml'):
        print("请先修复YAML文件后再继续操作")
        sys.exit(1)
    
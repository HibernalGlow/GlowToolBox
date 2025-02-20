import os
import logging
import subprocess
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import zipfile
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional
import argparse
import pyperclip
import shutil
import time
import tempfile
from pathlib import Path
import hashlib

# 配置类
@dataclass
class FormatConfig:
    """格式配置类"""
    format_name: str  # 格式名称
    check_type: str  # 检查类型：'lossless', 'lossy', 'both'
    min_avg_size: int  # 最小平均大小（字节）
    max_avg_size: int  # 最大平均大小（字节）
    mark_prefix: str  # 标记前缀

# 全局配置
TEMP_ROOT_DIR = r'E:\1BACKUP\test'  # 统一的临时文件夹根目录
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 0.5  # 重试延迟（秒）

# 内置配置
DEFAULT_CONFIGS = {
    'jxl': FormatConfig(
        format_name='jxl',
        check_type='lossless',
        min_avg_size=500_000,  # 500KB
        max_avg_size=5_000_000,  # 5MB
        mark_prefix='[#jxl]'
    ),
    'avif': FormatConfig(
        format_name='avif',
        check_type='both',
        min_avg_size=100_000,  # 100KB
        max_avg_size=2_000_000,  # 2MB
        mark_prefix='[#avif]'
    ),
    'webp': FormatConfig(
        format_name='webp',
        check_type='both',
        min_avg_size=50_000,  # 50KB
        max_avg_size=1_000_000,  # 1MB
        mark_prefix='[#webp]'
    )
}

# 黑名单路径配置
BLACKLIST_PATHS = [
    # r'E:\1EHV\[02COS]',
    # 可以添加更多黑名单路径
]

def parse_size(size_str: str) -> int:
    """解析大小字符串（支持KB、MB、GB后缀）"""
    size_str = size_str.upper()
    multipliers = {
        'K': 1024,
        'M': 1024 * 1024,
        'G': 1024 * 1024 * 1024
    }
    
    if size_str[-2:] in ['KB', 'MB', 'GB']:
        number = float(size_str[:-2])
        unit = size_str[-2:-1]
        return int(number * multipliers[unit])
    elif size_str[-1:] in ['K', 'M', 'G']:
        number = float(size_str[:-1])
        unit = size_str[-1]
        return int(number * multipliers[unit])
    else:
        return int(size_str)

def create_arg_parser():
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(description='压缩包格式检查和标记工具')
    
    # 添加参数
    parser.add_argument('directory', nargs='?', help='要处理的目录路径')
    parser.add_argument('-c', '--clipboard', action='store_true', 
                        help='从剪贴板读取多个路径（每行一个路径）')
    parser.add_argument('-f', '--format', choices=['jxl', 'avif', 'webp'], 
                        help='要检查的格式')
    parser.add_argument('-t', '--type', choices=['lossless', 'lossy', 'both'],
                        help='检查类型（有损/无损/两者）')
    parser.add_argument('--min-size', help='最小平均文件大小 (例如: 500K, 1M, 1.5GB)')
    parser.add_argument('--max-size', help='最大平均文件大小 (例如: 500K, 1M, 1.5GB)')
    parser.add_argument('-p', '--prefix', help='标记前缀')
    parser.add_argument('--dry-run', action='store_true',
                        help='仅检查不标记，用于测试查看哪些文件会被标记')
    
    return parser

class FormatChecker(ABC):
    """格式检查器抽象基类"""
    def __init__(self, config: FormatConfig):
        self.config = config
    
    @abstractmethod
    def check_format(self, file_path: str) -> tuple[bool, str]:
        """检查文件格式，返回(是否符合要求, 检查类型)"""
        pass

    def get_mark_prefix(self) -> str:
        """获取标记前缀"""
        return self.config.mark_prefix

def check_required_tools():
    """检查必要工具是否已安装"""
    tools = {
        '7z': '7z',
        'jxlinfo': 'jxlinfo'
    }
    
    missing_tools = []
    for tool_name, command in tools.items():
        try:
            subprocess.run([command, '--version'], capture_output=True)
        except FileNotFoundError:
            missing_tools.append(tool_name)
    
    if missing_tools:
        error_msg = f"缺少必要工具: {', '.join(missing_tools)}\n"
        error_msg += "请确保安装以下工具:\n"
        error_msg += "- 7-Zip (7z)\n"
        error_msg += "- JPEG XL tools (jxlinfo)"
        raise RuntimeError(error_msg)

class JXLChecker(FormatChecker):
    """JXL格式检查器"""
    def check_format(self, file_path: str) -> tuple[bool, str]:
        try:
            # 首先尝试使用jxlinfo
            cmd = ['jxlinfo', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=10)
            
            if result.returncode == 0:
                output = result.stdout.lower()
                is_lossless = 'lossless: true' in output or 'compression: lossless' in output
                return is_lossless, 'lossless' if is_lossless else 'lossy'
            
            raise Exception("无法使用jxlinfo检测JXL格式")
            
        except Exception as e:
            logging.error(f"检查JXL格式失败: {e}")
            return False, 'unknown'

class AVIFChecker(FormatChecker):
    """AVIF格式检查器"""
    def check_format(self, file_path: str) -> tuple[bool, str]:
        try:
            # TODO: 实现AVIF格式检查
            # 这里需要实现实际的AVIF格式检查逻辑
            return True, 'unknown'
        except Exception as e:
            logging.error(f"检查AVIF格式失败: {e}")
            return False, 'unknown'

class WebPChecker(FormatChecker):
    """WebP格式检查器"""
    def check_format(self, file_path: str) -> tuple[bool, str]:
        try:
            # TODO: 实现WebP格式检查
            # 这里需要实现实际的WebP格式检查逻辑
            return True, 'unknown'
        except Exception as e:
            logging.error(f"检查WebP格式失败: {e}")
            return False, 'unknown'

@dataclass
class ProcessStats:
    """处理统计信息"""
    total_archives: int = 0  # 总压缩包数
    total_size: int = 0  # 总大小
    processed_archives: int = 0  # 处理的压缩包数
    marked_archives: int = 0  # 标记的压缩包数
    marked_size: int = 0  # 标记的压缩包总大小
    error_archives: int = 0  # 错误的压缩包数
    format_stats: Dict[str, Dict[str, int]] = None  # 每种格式的统计信息
    
    def __post_init__(self):
        self.format_stats = {}
    
    def add_format_stat(self, fmt: str, type_str: str, size: int):
        """添加格式统计信息"""
        if fmt not in self.format_stats:
            self.format_stats[fmt] = {
                'count': 0,
                'total_size': 0,
                'lossless_count': 0,
                'lossy_count': 0,
                'unknown_count': 0
            }
        
        self.format_stats[fmt]['count'] += 1
        self.format_stats[fmt]['total_size'] += size
        if type_str == 'lossless':
            self.format_stats[fmt]['lossless_count'] += 1
        elif type_str == 'lossy':
            self.format_stats[fmt]['lossy_count'] += 1
        else:
            self.format_stats[fmt]['unknown_count'] += 1
    
    def format_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f}{unit}"
            size /= 1024
        return f"{size:.2f}TB"
    
    def __str__(self) -> str:
        """生成统计报告"""
        report = [
            "\n处理统计信息",
            "=" * 50,
            f"总压缩包数: {self.total_archives}",
            f"总大小: {self.format_size(self.total_size)}",
            f"处理的压缩包数: {self.processed_archives}",
            f"成功标记数: {self.marked_archives}",
            f"标记压缩包总大小: {self.format_size(self.marked_size)}",
            f"错误数: {self.error_archives}",
            "\n格式统计:",
        ]
        
        for fmt, stats in self.format_stats.items():
            report.extend([
                f"\n{fmt.upper()} 格式:",
                f"  文件数: {stats['count']}",
                f"  总大小: {self.format_size(stats['total_size'])}",
                f"  无损文件数: {stats['lossless_count']}",
                f"  有损文件数: {stats['lossy_count']}",
                f"  未知类型数: {stats['unknown_count']}"
            ])
        
        return "\n".join(report)

def ensure_temp_root():
    """确保临时根目录存在"""
    try:
        if not os.path.exists(TEMP_ROOT_DIR):
            os.makedirs(TEMP_ROOT_DIR, exist_ok=True)
            logging.info(f"创建临时根目录: {TEMP_ROOT_DIR}")
    except Exception as e:
        logging.error(f"创建临时根目录失败: {e}")
        raise

def create_temp_directory() -> str:
    """
    在统一的临时目录下创建唯一的临时子目录
    """
    ensure_temp_root()
    timestamp = int(time.time() * 1000)  # 毫秒级时间戳
    temp_dir = os.path.join(TEMP_ROOT_DIR, f"temp_{timestamp}")
    try:
        os.makedirs(temp_dir, exist_ok=True)
        logging.debug(f"创建临时目录: {temp_dir}")
        return temp_dir
    except Exception as e:
        logging.error(f"创建临时目录失败: {e}")
        raise

def cleanup_temp_directory(temp_dir: str):
    """安全清理临时目录，带重试机制"""
    if not temp_dir or not os.path.exists(temp_dir):
        return
        
    for retry in range(MAX_RETRIES):
        try:
            # 先尝试清理目录中的文件
            for root, dirs, files in os.walk(temp_dir, topdown=False):
                for name in files:
                    try:
                        file_path = os.path.join(root, name)
                        if os.path.exists(file_path):
                            os.chmod(file_path, 0o777)  # 确保有删除权限
                            os.remove(file_path)
                    except:
                        pass
                        
                for name in dirs:
                    try:
                        dir_path = os.path.join(root, name)
                        if os.path.exists(dir_path):
                            os.chmod(dir_path, 0o777)  # 确保有删除权限
                            os.rmdir(dir_path)
                    except:
                        pass
            
            # 最后删除根目录
            if os.path.exists(temp_dir):
                os.chmod(temp_dir, 0o777)  # 确保有删除权限
                os.rmdir(temp_dir)
            return
        except Exception as e:
            if retry < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
                continue
            logging.debug(f"清理临时目录失败: {temp_dir}, 错误: {e}")

def check_jxl_format(file_path):
    """
    使用 jxlinfo 检查 JXL 文件是否为无损格式
    返回: (bool, str) - (是否为无损格式, 错误信息)
    """
    try:
        # 确保文件存在且可访问
        if not os.path.exists(file_path):
            return False, f"文件不存在: {file_path}"
            
        # 确保文件有读取权限
        try:
            os.chmod(file_path, 0o777)
        except:
            pass
            
        # 等待文件系统同步
        time.sleep(0.1)
        
        # 使用 jxlinfo 命令获取图片信息
        cmd = ['jxlinfo', file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=10)
        
        if result.returncode != 0:
            return False, f"检查失败: {result.stderr}"
            
        # 检查输出中是否包含无损相关的信息
        output = result.stdout.lower()
        
        # jxlinfo 输出中包含 "lossless" 表示无损
        if 'lossless' in output:
            return True, ""
            
        return False, ""
        
    except subprocess.TimeoutExpired:
        return False, "命令执行超时"
    except Exception as e:
        return False, f"检查出错: {str(e)}"

def get_md5(file_path: str) -> str:
    """获取文件的 MD5 值"""
    try:
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            # 读取文件块
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    except Exception as e:
        logging.error(f"计算MD5失败: {e}")
        # 如果计算失败，返回时间戳作为备选
        return str(int(time.time() * 1000))

def is_path_blacklisted(path: str) -> bool:
    """检查路径是否在黑名单中"""
    return any(path.startswith(blacklist) for blacklist in BLACKLIST_PATHS)

class ArchiveProcessor:
    """压缩包处理器"""
    def __init__(self, args=None):
        self.lock = Lock()
        self.error_prefix = "[#e]"
        self.stats = ProcessStats()
        self.dry_run = args.dry_run if args else False
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("format_mark_log.log", encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        # 禁用警告
        warnings.filterwarnings('ignore', message='File is not a zip file', category=UserWarning)
        
        # 初始化格式检查器
        self.format_checkers = {
            'jxl': JXLChecker,
            'avif': AVIFChecker,
            'webp': WebPChecker,
        }
        
        # 使用内置配置并根据命令行参数更新
        self.format_configs = DEFAULT_CONFIGS.copy()
        if args:
            self.update_config_from_args(args)
    
    def update_config_from_args(self, args):
        """根据命令行参数更新配置"""
        if args.format:
            config = self.format_configs.get(args.format)
            if config:
                if args.type:
                    config.check_type = args.type
                if args.min_size:
                    config.min_avg_size = parse_size(args.min_size)
                if args.max_size:
                    config.max_avg_size = parse_size(args.max_size)
                if args.prefix:
                    config.mark_prefix = args.prefix
                
                # 只保留指定的格式配置
                self.format_configs = {args.format: config}

    def check_size_requirements(self, files_info: List[tuple[str, int]], config: FormatConfig) -> bool:
        """检查文件大小要求"""
        if not files_info:
            return False
        
        total_size = sum(size for _, size in files_info)
        avg_size = total_size / len(files_info)
        
        return config.min_avg_size <= avg_size <= config.max_avg_size

    def should_mark_zip(self, zip_path, formats):
        """检查压缩包是否需要标记"""
        temp_dir = None
        try:
            # 在统一目录下创建临时目录
            temp_dir = create_temp_directory()
            
            # 使用 7z 列出压缩包内容
            cmd = ['7z', 'l', zip_path]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                return False
            
            # 检查是否包含目标格式文件
            found_target_file = False
            for line in result.stdout.splitlines():
                if found_target_file:
                    break
                    
                for ext in formats:
                    if line.lower().endswith(ext):
                        # 找到目标文件，获取文件名
                        parts = line.split()
                        if len(parts) >= 6:
                            file_name = ' '.join(parts[5:])  # 文件名可能包含空格
                            
                            # 使用时间戳作为临时文件名
                            timestamp = int(time.time() * 1000)
                            temp_name = f"temp_{timestamp}{os.path.splitext(os.path.basename(file_name))[1]}"
                            temp_path = os.path.join(temp_dir, temp_name)
                            
                            # 使用 7z 提取单个文件
                            extract_cmd = ['7z', 'e', zip_path, f'-o{temp_dir}', file_name, '-y']
                            extract_result = subprocess.run(extract_cmd, capture_output=True, 
                                                          encoding='utf-8', errors='ignore')
                            
                            if extract_result.returncode != 0:
                                continue
                            
                            # 等待文件系统同步
                            time.sleep(0.1)
                            
                            # 重命名提取的文件
                            extracted_file = os.path.join(temp_dir, os.path.basename(file_name))
                            if os.path.exists(extracted_file):
                                try:
                                    if os.path.exists(temp_path):
                                        os.remove(temp_path)
                                    os.rename(extracted_file, temp_path)
                                    extracted_file = temp_path
                                    # 等待文件系统同步
                                    time.sleep(0.1)
                                except:
                                    pass
                            
                            if not os.path.exists(extracted_file):
                                continue
                            
                            try:
                                # 检查文件格式
                                if ext == '.jxl':
                                    is_lossless, error = check_jxl_format(extracted_file)
                                    if error:
                                        logging.warning(f"检查JXL文件失败: {error}")
                                        continue
                                    
                                    # 根据压缩类型决定是否标记
                                    if (is_lossless and 'lossless' in formats[ext]) or \
                                       (not is_lossless and 'lossy' in formats[ext]):
                                        found_target_file = True
                                        return True
                                else:
                                    # 其他格式直接标记
                                    found_target_file = True
                                    return True
                            finally:
                                # 删除提取的文件
                                try:
                                    if os.path.exists(extracted_file):
                                        os.chmod(extracted_file, 0o777)  # 确保有删除权限
                                        os.remove(extracted_file)
                                except:
                                    pass
                                
                            # 找到一个符合条件的文件就退出
                            if found_target_file:
                                break
                                
            return False
            
        except Exception as e:
            logging.error(f"检查压缩包失败: {str(e)}")
            return False
        finally:
            # 清理临时目录
            if temp_dir:
                cleanup_temp_directory(temp_dir)

    def process_zip(self, zip_path: str):
        """处理单个压缩包"""
        try:
            logging.debug(f"开始处理压缩包: {zip_path}")
            
            # 检查文件是否存在
            if not os.path.exists(zip_path):
                logging.error(f"压缩包不存在: {zip_path}")
                return
                
            # 更新总压缩包统计
            file_size = os.path.getsize(zip_path)
            with self.lock:
                self.stats.total_archives += 1
                self.stats.total_size += file_size
                self.stats.processed_archives += 1
            
            logging.debug(f"压缩包大小: {self.stats.format_size(file_size)}")
            
            # 构建格式配置字典
            formats = {}
            for fmt_name, config in self.format_configs.items():
                formats[f'.{fmt_name}'] = [config.check_type]
                logging.debug(f"检查格式: {fmt_name}, 类型: {config.check_type}")
            
            # 检查是否需要标记
            logging.debug(f"开始检查压缩包内容: {zip_path}")
            should_mark = self.should_mark_zip(zip_path, formats)
            
            if should_mark:
                logging.info(f"找到符合条件的文件: {zip_path}")
                # 获取文件名和目录
                dir_path = os.path.dirname(zip_path)
                base_name = os.path.basename(zip_path)
                
                # 获取对应的格式配置
                config = next(iter(self.format_configs.values()))
                mark_prefix = config.mark_prefix
                
                # 如果已经有标记前缀，跳过
                if base_name.startswith(mark_prefix):
                    logging.info(f"压缩包已标记，跳过: {zip_path}")
                    return
                    
                # 添加标记前缀
                new_path = os.path.join(dir_path, f"{mark_prefix}{base_name}")
                
                if self.dry_run:
                    logging.info(f"[测试模式] 将标记: {zip_path} -> {new_path}")
                    with self.lock:
                        self.stats.marked_archives += 1
                        self.stats.marked_size += file_size
                else:
                    logging.debug(f"新文件路径: {new_path}")
                    with self.lock:
                        os.rename(zip_path, new_path)
                        self.stats.marked_archives += 1
                        self.stats.marked_size += file_size
                    logging.info(f"成功标记压缩包: {zip_path} -> {new_path}")
            else:
                logging.debug(f"压缩包不符合标记条件: {zip_path}")
                
        except Exception as e:
            # 发生错误时添加错误前缀
            try:
                if not self.dry_run:
                    dir_path = os.path.dirname(zip_path)
                    base_name = os.path.basename(zip_path)
                    error_path = os.path.join(dir_path, f"{self.error_prefix}{base_name}")
                    
                    with self.lock:
                        if not os.path.exists(error_path):
                            os.rename(zip_path, error_path)
                with self.lock:
                    self.stats.error_archives += 1
                logging.error(f"处理失败: {zip_path}, 错误: {str(e)}", exc_info=True)
            except Exception as rename_error:
                logging.error(f"添加错误标记失败: {zip_path}, 错误: {str(rename_error)}", exc_info=True)

    def process_directories(self, directories: List[str]):
        """处理多个目录"""
        all_zip_files = []
        
        # 收集所有目录中的压缩包
        for directory in directories:
            if not os.path.exists(directory):
                logging.warning(f"目录不存在，跳过: {directory}")
                continue
                
            # 检查是否在黑名单中
            if is_path_blacklisted(directory):
                logging.info(f"目录在黑名单中，跳过: {directory}")
                continue
                
            logging.info(f"正在扫描目录: {directory}")
            for root, _, files in os.walk(directory):
                # 检查子目录是否在黑名单中
                if is_path_blacklisted(root):
                    logging.debug(f"子目录在黑名单中，跳过: {root}")
                    continue
                    
                for file in files:
                    if file.endswith(('.zip', '.cbz')):
                        full_path = os.path.join(root, file)
                        # 预先检查文件是否可访问
                        try:
                            with open(full_path, 'rb') as f:
                                # 只读取文件头部来验证可访问性
                                f.read(1024)
                            all_zip_files.append(full_path)
                        except Exception as e:
                            logging.warning(f"文件无法访问，跳过: {full_path}, 错误: {e}")
                            continue
                            
            logging.info(f"在目录 {directory} 中找到 {len(all_zip_files)} 个压缩包")
        
        total_files = len(all_zip_files)
        logging.info(f"在{len(directories)}个目录中共找到{total_files}个压缩包")
        
        if not all_zip_files:
            logging.warning("未找到任何压缩包")
            return
        
        # 使用线程池处理
        logging.info("开始并行处理压缩包...")
        with ThreadPoolExecutor(max_workers=min(32, os.cpu_count() * 2)) as executor:
            futures = []
            # 分批提交任务，避免内存占用过大
            batch_size = 1000
            for i in range(0, len(all_zip_files), batch_size):
                batch = all_zip_files[i:i + batch_size]
                for zip_path in batch:
                    futures.append(executor.submit(self.process_zip, zip_path))
                
                # 使用tqdm显示进度
                for future in tqdm(as_completed(futures), total=len(futures), 
                                 desc=f"处理第{i//batch_size + 1}批", unit="个"):
                    try:
                        future.result()
                    except Exception as e:
                        logging.error(f"处理任务失败: {str(e)}", exc_info=True)
                futures.clear()
        
        # 输出统计信息
        logging.info("处理完成，统计信息如下：")
        logging.info(str(self.stats))
        print("\n处理完成，统计信息如下：")
        print(str(self.stats))

def main():
    """主函数"""
    try:
        # 检查必要工具
        logging.info("正在检查必要工具...")
        check_required_tools()
        logging.info("工具检查完成，所有必要工具已安装")
        
        parser = create_arg_parser()
        args = parser.parse_args()
        
        directories = []
        
        # 从剪贴板读取路径
        if args.clipboard:
            try:
                logging.info("正在从剪贴板读取路径...")
                clipboard_content = pyperclip.paste()
                # 分割并过滤空行
                paths = [path.strip() for path in clipboard_content.splitlines() if path.strip()]
                if not paths:
                    logging.error("剪贴板中没有找到有效路径")
                    return
                directories.extend(paths)
                logging.info(f"从剪贴板成功读取了{len(paths)}个路径:")
                for idx, path in enumerate(paths, 1):
                    logging.info(f"  {idx}. {path}")
            except Exception as e:
                logging.error(f"读取剪贴板失败: {e}")
                return
        
        # 如果有命令行指定的目录，添加到列表
        if args.directory:
            logging.info(f"从命令行参数读取目录: {args.directory}")
            directories.append(args.directory)
        
        # 如果既没有剪贴板路径也没有命令行路径，则提示输入
        if not directories:
            directory = input("请输入压缩包目录路径: ").strip()
            if not directory:
                logging.error("未输入有效路径")
                return
            logging.info(f"从用户输入读取目录: {directory}")
            directories.append(directory)
        
        # 验证所有目录路径是否存在
        valid_directories = []
        for directory in directories:
            if not os.path.exists(directory):
                logging.error(f"目录不存在: {directory}")
                continue
            if not os.path.isdir(directory):
                logging.error(f"路径不是目录: {directory}")
                continue
            valid_directories.append(directory)
        
        if not valid_directories:
            logging.error("没有找到有效的目录路径")
            return
        
        logging.info(f"开始处理{len(valid_directories)}个有效目录:")
        for idx, directory in enumerate(valid_directories, 1):
            logging.info(f"  {idx}. {directory}")
        
        # 创建处理器实例并处理目录
        processor = ArchiveProcessor(args)
        processor.process_directories(valid_directories)
        
    except Exception as e:
        logging.error(f"程序执行失败: {str(e)}", exc_info=True)
        print(f"处理失败: {e}")

if __name__ == "__main__":
    # 设置日志格式
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("format_mark.log", encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    main() 
import os
import shutil
import logging
from tqdm import tqdm
import subprocess
from typing import List, Set, Optional, Tuple, Dict
from pathlib import Path, WindowsPath
import concurrent.futures
from dataclasses import dataclass
import pyperclip
import argparse
import time
import stat
import win32security
import win32api
import win32con
import ntsecuritycon as con
import tempfile
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import checkboxlist_dialog
from prompt_toolkit.styles import Style
from nodes.tui.textual_logger import TextualLoggerManager
from nodes.record.logger_config import setup_logger
config = {
    'script_name': 'comic_auto_repack',
    'console_enabled': False
}
logger, config_info = setup_logger(config)

# 配置常量
SEVEN_ZIP_PATH = "C:\\Program Files\\7-Zip\\7z.exe"
COMPRESSION_LEVEL = 5  # 1-9, 9为最高压缩率
MAX_WORKERS = 4  # 并行处理的最大工作线程数

# 不需要压缩的文件类型
UNWANTED_EXTENSIONS: Set[str] = {
    '.url', '.txt', '.tsd', '.db', '.js', '.htm', '.html', '.docx'
}

# 黑名单关键词
BLACKLIST_KEYWORDS = ['_temp', '画集', '00去图', '00不需要', '[00不需要]', '动画']

# 媒体文件类型
MEDIA_TYPES = {
    '[00不需要]': {
        'extensions': ['.url', '.txt', '.tsd', '.db', '.js', '.htm', '.html', '.docx'],
        'associated_extensions': []  # 关联的字幕和图片文件
    },
    '[01视频]': {
        'extensions': ['.mp4', '.avi', '.webm', '.rmvb', '.mov', '.mkv','.flv','.wmv', '.nov'],
        'associated_extensions': ['.ass', '.srt', '.ssa', '.jxl', '.avif', '.jpg', '.jpeg', '.png', '.webp']  # 关联的字幕和图片文件
    },
    # '[02动图]': {
    #     'extensions': ['.gif'],
    #     'associated_extensions': []
    # },
    '[04cbz]': {
        'extensions': ['.cbz'],
        'associated_extensions': []
    }
}

# 定义图像文件扩展名集合
IMAGE_EXTENSIONS: Set[str] = {
    '.webp', '.avif', '.jxl', '.jpg', '.jpeg',
    '.png', '.gif', '.yaml', '.log', '.bmp'
}

@dataclass
class CompressionResult:
    success: bool
    original_size: int = 0
    compressed_size: int = 0
    error_message: str = ""

@dataclass
class CompressionStats:
    total_original_size: int = 0
    total_compressed_size: int = 0
    successful_compressions: int = 0
    failed_compressions: int = 0
    
    @property
    def total_space_saved(self) -> int:
        return self.total_original_size - self.total_compressed_size
    
    @property
    def compression_ratio(self) -> float:
        if self.total_original_size == 0:
            return 0
        return (self.total_compressed_size / self.total_original_size) * 100
    
    def format_size(self, size_in_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_in_bytes < 1024:
                return f"{size_in_bytes:.2f} {unit}"
            size_in_bytes /= 1024
        return f"{size_in_bytes:.2f} TB"
    
    def get_summary(self) -> str:
        return (
            f"\n压缩统计摘要:\n"
            f"总处理文件夹数: {self.successful_compressions + self.failed_compressions}\n"
            f"成功压缩: {self.successful_compressions}\n"
            f"失败数量: {self.failed_compressions}\n"
            f"原始总大小: {self.format_size(self.total_original_size)}\n"
            f"压缩后总大小: {self.format_size(self.total_compressed_size)}\n"
            f"节省空间: {self.format_size(self.total_space_saved)}\n"
            f"平均压缩率: {self.compression_ratio:.1f}%"
        )

@dataclass
class ZipCompressor:
    """压缩处理类，封装所有压缩相关的操作"""
    seven_zip_path: str = SEVEN_ZIP_PATH
    compression_level: int = COMPRESSION_LEVEL
    
    
    def create_temp_workspace(self) -> Tuple[Path, Path]:
        """创建临时工作目录"""
        temp_base = tempfile.mkdtemp(prefix="zip_")
        temp_base_path = Path(temp_base)
        temp_work_dir = temp_base_path / "work"
        temp_work_dir.mkdir(exist_ok=True)
        return temp_base_path, temp_work_dir
    
    def compress_files(self, source_path: Path, target_zip: Path, files_to_zip: List[Path] = None, delete_source: bool = False) -> subprocess.CompletedProcess:
        """压缩文件到目标路径"""
        if files_to_zip:
            # 压缩指定的文件列表
            files_str = " ".join(f'"{safe_path(f)}"' for f in files_to_zip)
            cmd = f'"{self.seven_zip_path}" a -r -aoa -tzip -mx={self.compression_level} "{safe_path(target_zip)}" {files_str}'
        else:
            # 压缩整个目录
            cmd = f'"{self.seven_zip_path}" a -r -aoa -tzip -mx={self.compression_level} "{safe_path(target_zip)}" "{safe_path(source_path)}\\*"'
            if delete_source:
                cmd += " -sdel"
        
        return subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    def process_normal_folder(self, folder_path: Path) -> CompressionResult:
        """处理普通文件夹的压缩"""
        if self.handler is None:
            raise ValueError("Handler is not set")
            
        zip_name = folder_path.name
        zip_path = folder_path.parent / f"{zip_name}.zip"
        original_size = get_folder_size(folder_path)
        
        try:
            if not folder_path.exists():
                return CompressionResult(False, error_message=f"Folder not found: {folder_path}")
            
            # 创建临时工作目录
            temp_base_path, _ = self.create_temp_workspace()
            temp_zip_path = temp_base_path / f"{zip_name}_temp.zip"
            
            try:
                # 压缩文件夹
                result = self.compress_files(folder_path, temp_zip_path, delete_source=True)
                
                if result.returncode == 0:
                    if temp_zip_path.exists():
                        # 处理目标文件
                        final_zip_path = self._handle_existing_zip(temp_zip_path, zip_path, zip_name)
                        if final_zip_path:
                            compressed_size = final_zip_path.stat().st_size
                            self._cleanup_empty_folder(folder_path)
                            return CompressionResult(True, original_size, compressed_size)
                
                return CompressionResult(False, error_message=f"Compression failed: {result.stderr}")
            finally:
                # 清理临时目录
                shutil.rmtree(temp_base_path, ignore_errors=True)
                
        except Exception as e:
            return CompressionResult(False, error_message=f"Error: {str(e)}")
    
    def process_scattered_images(self, folder_path: Path, image_files: List[Path]) -> CompressionResult:
        """处理散图文件夹的压缩"""
        zip_name = folder_path.name
        zip_path = folder_path / f"{zip_name}_散图.zip"
        original_size = sum(f.stat().st_size for f in image_files)
        
        try:
            # 创建临时工作目录
            temp_base_path, temp_work_dir = self.create_temp_workspace()
            temp_zip_path = temp_base_path / f"{zip_name}_temp.zip"
            
            try:
                # 复制图片到临时目录
                copy_success = True
                for idx, file in enumerate(image_files, 1):
                    temp_file = temp_work_dir / f"img_{idx:03d}{file.suffix}"
                    if not safe_copy_file(file, temp_file):
                        copy_success = False
                        break
                
                if not copy_success:
                    return CompressionResult(False, error_message="Failed to copy files to temp folder")
                
                # 压缩临时目录中的文件
                result = self.compress_files(temp_work_dir, temp_zip_path)
                
                if result.returncode == 0:
                    if temp_zip_path.exists():
                        # 处理目标文件
                        final_zip_path = self._handle_existing_zip(temp_zip_path, zip_path, zip_name)
                        if final_zip_path:
                            # 删除原始图片文件
                            self._delete_source_files(image_files)
                            compressed_size = final_zip_path.stat().st_size
                            return CompressionResult(True, original_size, compressed_size)
                
                return CompressionResult(False, error_message=f"Compression failed: {result.stderr}")
            finally:
                # 清理临时目录
                shutil.rmtree(temp_base_path, ignore_errors=True)
                
        except Exception as e:
            return CompressionResult(False, error_message=f"Error: {str(e)}")
    
    def _handle_existing_zip(self, temp_zip_path: Path, target_zip_path: Path, base_name: str) -> Optional[Path]:
        """处理已存在的压缩包"""
        try:
            if target_zip_path.exists():
                if compare_zip_contents(temp_zip_path, target_zip_path, self.handler):
                    # 内容相同，替换原文件
                    target_zip_path.unlink()
                    shutil.move(str(temp_zip_path), str(target_zip_path))
                    self.logger.info(f"📦 压缩包内容相同，已覆盖原文件: {target_zip_path}")
                    return target_zip_path
                else:
                    # 内容不同，使用新名称
                    counter = 1
                    while True:
                        new_zip_path = target_zip_path.parent / f"{base_name}_{counter}.zip"
                        if not new_zip_path.exists():
                            shutil.move(str(temp_zip_path), str(new_zip_path))
                            return new_zip_path
                        counter += 1
            else:
                # 目标文件不存在，直接移动
                shutil.move(str(temp_zip_path), str(target_zip_path))
                return target_zip_path
        except Exception as e:
            self.logger.info(f"❌ 处理压缩包时发生错误: {e}")
            return None
    
    def _cleanup_empty_folder(self, folder_path: Path) -> None:
        """清理空文件夹"""
        if not any(folder_path.iterdir()):
            try:
                folder_path.rmdir()
                self.logger.info(f"🗑️ 已删除空文件夹: {folder_path}")
            except Exception as e:
                self.logger.info(f"❌ 删除空文件夹失败: {folder_path}, 错误: {e}")
    
    def _delete_source_files(self, files: List[Path]) -> None:
        """删除源文件"""
        delete_failures = []
        for file in files:
            if file.exists():
                if not safe_remove_file(file, self.handler):
                    delete_failures.append(str(file))
                    self.logger.info(f"⚠️ 无法删除原始文件: {file}")
        
        if delete_failures:
            try:
                files_list = '" "'.join(delete_failures)
                if not cmd_delete(f'"{files_list}"', handler=self.handler):
                    self.logger.info(f"❌ 批量删除失败: {files_list}")
            except Exception as e:
                self.logger.info(f"❌ 批量删除命令执行失败: {e}")

def get_folder_size(folder_path: Path) -> int:
    return sum(f.stat().st_size for f in folder_path.rglob('*') if f.is_file())

def find_min_folder_with_images(base_path: Path, exclude_keywords: List[str]) -> Optional[Tuple[Path, bool, int]]:
    """
    查找需要打包的文件夹
    返回: (文件夹路径, 是否需要特殊处理, 图片数量)
    """
    # 检查路径是否包含黑名单关键词
    if any(keyword in str(base_path) for keyword in BLACKLIST_KEYWORDS):
        logger.info(f"跳过黑名单路径: {base_path}")
        return None
        
    # 如果路径不存在或不是目录，返回 None
    if not base_path.exists() or not base_path.is_dir():
        return None
    
    # 检查文件夹名称是否是媒体类型文件夹
    if base_path.name in MEDIA_TYPES:
        return None
        
    # 检查是否在任何媒体类型文件夹内
    if any(part in MEDIA_TYPES for part in base_path.parts):
        return None
        
    # 检查是否在排除列表中
    if any(keyword in str(base_path) for keyword in exclude_keywords):
        return None
    
    # 获取文件夹内容
    try:
        contents = list(base_path.iterdir())
    except Exception:
        return None
    
    # 检查是否有子文件夹
    if any(item.is_dir() for item in contents):
        return None
    
    # 获取所有文件
    files = [f for f in contents if f.is_file()]
    if not files:  # 空文件夹
        return None
    
    # 检查文件类型
    image_files = [f for f in files if f.suffix.lower() in IMAGE_EXTENSIONS]
    zip_files = [f for f in files if f.suffix.lower() == '.zip']
    media_files = []
    for media_type in MEDIA_TYPES.values():
        media_files.extend([f for f in files if any(f.suffix.lower() == ext for ext in media_type['extensions'])])
    unwanted_files = [f for f in files if f.suffix.lower() in UNWANTED_EXTENSIONS]
    
    # 计算有效文件（排除不需要的文件）
    valid_files = [f for f in files if f.suffix.lower() not in UNWANTED_EXTENSIONS]
    if not valid_files:  # 只包含不需要的文件
        return None
    
    # 先检查是否是散图情况
    is_scattered = False
    if zip_files and len(image_files) >= 3:
        is_scattered = True
    elif len(image_files) >= 3 and len(valid_files) == len(image_files):
        is_scattered = True
    
    # 如果是散图文件夹，返回 None，让散图处理功能去处理它
    if is_scattered:
        logger.info(f"跳过散图文件夹: {base_path}")
        return None
    
    # 如果包含其他有效文件（非图片、非压缩包、非不需要的文件），则作为普通文件夹打包
    if valid_files:
        return base_path, False, len(image_files)
    
    return None

def compare_zip_contents(zip1_path: Path, zip2_path: Path) -> bool:
    """
    比较两个压缩包的内容是否相同
    返回: 如果两个压缩包的文件数量和大小都相同，返回True
    """
    try:
        # 使用7z l命令列出压缩包内容
        cmd1 = f'"{SEVEN_ZIP_PATH}" l "{zip1_path}"'
        cmd2 = f'"{SEVEN_ZIP_PATH}" l "{zip2_path}"'
        
        result1 = subprocess.run(cmd1, shell=True, capture_output=True, text=True)
        result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True)
        
        if result1.returncode != 0 or result2.returncode != 0:
            return False
            
        # 解析输出，获取文件列表和大小
        def parse_7z_output(output: str) -> Dict[str, int]:
            files = {}
            for line in output.split('\n'):
                # 7z输出格式：日期 时间 属性 大小 压缩后大小 文件名
                parts = line.strip().split()
                if len(parts) >= 5 and parts[0][0].isdigit():  # 确保是文件行
                    try:
                        size = int(parts[3])
                        name = ' '.join(parts[5:])  # 文件名可能包含空格
                        files[name] = size
                    except (ValueError, IndexError):
                        continue
            return files
            
        files1 = parse_7z_output(result1.stdout)
        files2 = parse_7z_output(result2.stdout)
        
        # 比较文件数量和总大小
        if len(files1) != len(files2):
            return False
            
        # 比较每个文件的大小
        return all(files1.get(name) == files2.get(name) for name in files1)
    except Exception as e:
        logger.info(f"❌ 比较压缩包时发生错误: {e}")
        return False

def get_long_path_name(path_str: str) -> str:
    """转换为长路径格式"""
    if not path_str.startswith("\\\\?\\"):
        if os.path.isabs(path_str):
            return "\\\\?\\" + path_str
    return path_str

def safe_path(path: Path) -> str:
    """确保路径支持长文件名"""
    return get_long_path_name(str(path.absolute()))

def create_temp_dir(parent_dir: Path) -> Path:
    """在指定目录下创建临时目录"""
    temp_dir = parent_dir / f"temp_{int(time.time())}_{os.getpid()}"
    temp_dir.mkdir(exist_ok=True)
    return temp_dir

def safe_copy_file(src: Path, dst: Path) -> bool:
    """安全地复制文件，处理各种错误情况"""
    logger.info(f"🔄 开始复制文件: {src} -> {dst}")
    try:
        # 使用长路径
        src_long = safe_path(src)
        dst_long = safe_path(dst)
        
        # 确保目标目录存在
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        # 尝试直接复制
        try:
            logger.info("🔄 尝试直接复制文件...")
            with open(src_long, 'rb') as fsrc:
                with open(dst_long, 'wb') as fdst:
                    shutil.copyfileobj(fsrc, fdst)
            logger.info("✅ 文件复制成功")
            return True
        except Exception as e:
            logger.info(f"❌ 复制文件失败: {e}")
            return False
    except Exception as e:
        logger.info(f"❌ 复制文件失败: {src} -> {dst}, 错误: {str(e)}")
        return False

def safe_remove_file(file_path: Path) -> bool:
    """安全地删除文件，处理各种错误情况"""
    try:
        # 使用长路径
        long_path = safe_path(file_path)
        
        # 尝试清除只读属性
        try:
            if file_path.exists():
                current_mode = file_path.stat().st_mode
                file_path.chmod(current_mode | stat.S_IWRITE)
        except Exception as e:
            logger.info(f"⚠️ 清除只读属性失败: {file_path}, 错误: {e}")
        
        # 尝试使用不同的方法删除文件
        try:
            # 方法1：直接删除
            os.remove(long_path)
            return True
        except Exception as e1:
            logger.info(f"❌ 直接删除失败，尝试其他方法: {e1}")
            try:
                # 方法2：使用Windows API删除
                if os.path.exists(long_path):
                    import ctypes
                    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
                    if kernel32.DeleteFileW(long_path):
                        return True
                    error = ctypes.get_last_error()
                    if error == 0:  # ERROR_SUCCESS
                        return True
                    logger.info(f"⚠️ Windows API删除失败，错误码: {error}")
            except Exception as e2:
                logger.info(f"❌ Windows API删除失败: {e2}")
                try:
                    # 方法3：使用shell删除
                    import subprocess
                    subprocess.run(['cmd', '/c', 'del', '/f', '/q', long_path], 
                                 shell=True, 
                                 capture_output=True)
                    if not os.path.exists(long_path):
                        return True
                except Exception as e3:
                    logger.info(f"❌ Shell删除失败: {e3}")
        
        return False
    except Exception as e:
        logger.info(f"❌ 删除文件失败: {file_path}, 错误: {str(e)}")
        return False

def zip_folder_with_7zip(folder_path: Path, only_images: bool = False, image_count: int = 0) -> CompressionResult:
    """
    压缩文件夹，可以选择是否只压缩图片文件
    """
    # 如果是只压缩图片且图片数量小于3，跳过处理
    if only_images and image_count < 3:
        return CompressionResult(False, error_message=f"Skip folder with less than 3 images: {folder_path}")
        
    # 使用当前文件夹名称作为压缩包名称
    zip_name = folder_path.name
    # 散图压缩包存放在当前文件夹，普通压缩包存放在父文件夹
    zip_path = (folder_path / f"{zip_name}_散图.zip") if only_images else (folder_path.parent / f"{zip_name}.zip")
    original_size = get_folder_size(folder_path)
    
    try:
        if not folder_path.exists():
            return CompressionResult(False, error_message=f"Folder not found: {folder_path}")
        
        # 使用系统临时目录创建工作目录
        with tempfile.TemporaryDirectory(prefix="zip_") as temp_base:
            temp_base_path = Path(temp_base)
            temp_work_dir = temp_base_path / "work"
            temp_work_dir.mkdir(exist_ok=True)
            
            # 如果目标压缩包已存在，创建临时压缩包
            temp_zip_path = temp_base_path / f"{zip_name}_temp.zip"
            
            # 构建要压缩的文件列表
            if only_images:
                # 只压缩图片文件
                files_to_zip = [f for f in folder_path.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS]
                if not files_to_zip:
                    return CompressionResult(False, error_message=f"No image files found in: {folder_path}")
                
                # 复制文件到临时目录，使用简化的文件名
                copy_success = True
                original_to_temp_map = {}
                for idx, file in enumerate(files_to_zip, 1):
                    # 创建简化的文件名
                    temp_filename = f"img_{idx:03d}{file.suffix}"
                    temp_file = temp_work_dir / temp_filename
                    if not safe_copy_file(file, temp_file):
                        copy_success = False
                        break
                    original_to_temp_map[file] = temp_file
                
                if not copy_success:
                    return CompressionResult(False, error_message=f"Failed to copy files to temp folder")
                
                # 压缩临时目录中的文件
                cmd = f'"{SEVEN_ZIP_PATH}" a -r -aoa -tzip -mx={COMPRESSION_LEVEL} "{safe_path(temp_zip_path)}" "{safe_path(temp_work_dir)}\\*"'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                # 如果压缩成功，删除原始图片文件
                if result.returncode == 0:
                    delete_success = True
                    for file in files_to_zip:
                        if not safe_remove_file(file):
                            delete_success = False
                            logger.info(f"⚠️ 无法删除原始文件: {file}")
                    
                    if not delete_success:
                        logger.info("部分原始文件删除失败，但压缩包已创建成功")
            else:
                # 压缩整个文件夹内容到父目录
                cmd = f'"{SEVEN_ZIP_PATH}" a -r -aoa -tzip -mx={COMPRESSION_LEVEL} "{safe_path(temp_zip_path)}" "{safe_path(folder_path)}\\*" -sdel'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                if temp_zip_path.exists():
                    try:
                        # 如果目标文件已存在，先检查内容
                        if zip_path.exists():
                            if compare_zip_contents(temp_zip_path, zip_path):
                                # 内容相同，替换原文件
                                zip_path.unlink()
                                shutil.move(str(temp_zip_path), str(zip_path))
                                logger.info(f"📦 压缩包内容相同，已覆盖原文件: {zip_path}")
                            else:
                                # 内容不同，使用新名称
                                counter = 1
                                while True:
                                    new_zip_path = zip_path.parent / f"{zip_name}_{counter}.zip"
                                    if not new_zip_path.exists():
                                        shutil.move(str(temp_zip_path), str(new_zip_path))
                                        zip_path = new_zip_path
                                        break
                                    counter += 1
                        else:
                            # 目标文件不存在，直接移动
                            shutil.move(str(temp_zip_path), str(zip_path))
                        
                        compressed_size = zip_path.stat().st_size
                        compression_ratio = (compressed_size / original_size) * 100 if original_size > 0 else 0
                        
                        logger.info(f"Compressed '{folder_path}' - Original: {original_size/1024/1024:.2f}MB, "
                                   f"Compressed: {compressed_size/1024/1024:.2f}MB, Ratio: {compression_ratio:.1f}%")
                        
                        # 如果文件夹为空，删除它
                        if not any(folder_path.iterdir()):
                            try:
                                folder_path.rmdir()
                                logger.info(f"🗑️ 已删除空文件夹: {folder_path}")
                            except Exception as e:
                                logger.info(f"❌ 删除空文件夹失败: {folder_path}, 错误: {e}")
                        
                        return CompressionResult(True, original_size, compressed_size)
                    except Exception as e:
                        return CompressionResult(False, error_message=f"Error moving zip file: {str(e)}")
            
            return CompressionResult(False, error_message=f"Compression failed: {result.stderr}")
    except Exception as e:
        return CompressionResult(False, error_message=f"Error: {str(e)}")

def process_folders(base_path: str, exclude_keywords: List[str]) -> List[Path]:
    base_path = Path(base_path)
    if not base_path.exists():
        logger.info(f"基础路径不存在: {base_path}")
        return []
    
    stats = CompressionStats()
    zip_paths: List[Path] = []
    compressor = ZipCompressor()
    
    # 查找需要打包的文件夹
    logger.info("🔍 开始查找需要打包的文件夹...")
    folders_to_process = []
    
    # 遍历所有文件夹
    for root, dirs, _ in os.walk(base_path):
        root_path = Path(root)
        
        # 检查是否包含黑名单关键词
        if any(keyword in str(root_path) for keyword in BLACKLIST_KEYWORDS):
            logger.info(f"跳过黑名单路径: {root_path}")
            dirs.clear()  # 跳过子目录
            continue
        
        # 如果当前文件夹是媒体类型文件夹，跳过它和它的所有子文件夹
        if root_path.name in MEDIA_TYPES:
            dirs.clear()  # 清空子文件夹列表，这样就不会继续遍历
            continue
            
        # 如果当前文件夹的任何父文件夹是媒体类型文件夹，也跳过
        if any(part in MEDIA_TYPES for part in root_path.parts):
            continue
        
        # 检查当前文件夹
        result = find_min_folder_with_images(root_path, exclude_keywords)
        if result:
            folders_to_process.append(result[0])  # 只保存文件夹路径
            logger.info(f"📁 找到需要打包的文件夹: {result[0]}")
    
    if folders_to_process:
        logger.info(f"📊 共找到 {len(folders_to_process)} 个文件夹需要打包")
        
        # 创建进度任务
        process_task = logger.info(total=len(folders_to_process), description="处理文件夹")
        
        # 使用线程池处理普通文件夹
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = []
            for folder in folders_to_process:
                future = executor.submit(compressor.process_normal_folder, folder)
                futures.append((future, folder))
            
            for future, folder in futures:
                try:
                    result = future.result()
                    if result.success:
                        stats.successful_compressions += 1
                        stats.total_original_size += result.original_size
                        stats.total_compressed_size += result.compressed_size
                        zip_paths.append(folder.parent / f"{folder.name}.zip")
                        logger.info(f"✅ 成功处理: {folder.name}")
                    else:
                        stats.failed_compressions += 1
                        logger.info(f"处理失败 {folder}: {result.error_message}")
                except Exception as e:
                    stats.failed_compressions += 1
                    logger.info(f"处理异常 {folder}: {str(e)}")
                finally:
                    logger.info(process_task, advance=1)
    else:
        logger.info("⚠️ 未找到需要打包的文件夹")
    
    logger.info(stats.get_summary())
    return zip_paths

def process_scattered_images_in_directory(directory: Path) -> int:
    """处理目录中的散图
    返回：处理的散图文件夹数量
    """
    processed_scattered = 0
    for root, _, _ in os.walk(directory):
        root_path = Path(root)
        
        # 检查是否包含黑名单关键词
        if any(keyword in str(root_path) for keyword in BLACKLIST_KEYWORDS):
            logger.info(f"跳过黑名单路径: {root_path}")
            continue
        
        if any(media_type in str(root_path) for media_type in MEDIA_TYPES):
            logger.info(f"跳过媒体文件夹: {root_path}")
            continue
        
        has_scattered, image_files = find_scattered_images(root_path)
        if has_scattered:
            logger.info(f"发现散图文件夹: {root_path}")
            result = zip_scattered_images(root_path, image_files)
            if result.success:
                processed_scattered += 1
                logger.info(f"成功处理散图 - 原始大小: {result.original_size/1024/1024:.2f}MB, "
                           f"压缩后: {result.compressed_size/1024/1024:.2f}MB")
            else:
                logger.info(f"处理散图失败: {result.error_message}")
    
    return processed_scattered

def move_unwanted_files(source_folder: Path, target_base: Path) -> Tuple[int, int]:
    """
    移动不需要的文件到指定目录，保持原有的目录结构
    返回: (移动的文件数量, 移动的文件总大小)
    """
    moved_count = 0
    moved_size = 0
    
    for file_path in source_folder.rglob('*'):
        if not file_path.is_file():
            continue
            
        if file_path.suffix.lower() in UNWANTED_EXTENSIONS:
            # 计算相对路径，以保持目录结构
            rel_path = file_path.relative_to(source_folder)
            target_path = target_base / rel_path
            
            # 确保目标目录存在
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                # 如果目标文件已存在，添加数字后缀
                final_target_path = target_path
                counter = 1
                while final_target_path.exists():
                    final_target_path = target_path.parent / f"{target_path.stem}_{counter}{target_path.suffix}"
                    counter += 1
                
                # 移动文件
                try:
                    shutil.move(str(file_path), str(final_target_path))
                    # 验证文件是否确实被移动成功
                    if final_target_path.exists() and not file_path.exists():
                        moved_count += 1
                        moved_size += final_target_path.stat().st_size
                        logger.info(f"📦 已移动文件: {file_path.name} -> {final_target_path}")
                    else:
                        logger.info(f"❌ 移动文件可能未成功完成 {file_path} -> {final_target_path}")
                except (shutil.Error, OSError) as e:
                    logger.info(f"❌ 移动文件失败 {file_path}: {str(e)}")
            except Exception as e:
                logger.info(f"❌ 移动文件时发生未知错误 {file_path}: {str(e)}")
    
    return moved_count, moved_size

def organize_media_files(source_path: Path, target_base_path: Path) -> Tuple[int, int]:
    """
    整理媒体文件，保持原有文件夹结构，同时处理关联文件
    返回: (移动的文件数量, 移动的文件总大小)
    """
    moved_count = 0
    moved_size = 0
    
    # 检查源路径是否在媒体类型文件夹内（包括父路径）
    if any(media_type in str(source_path) for media_type in MEDIA_TYPES):
        logger.info(f"跳过已整理的媒体文件夹路径: {source_path}")
        return moved_count, moved_size
    
    # 遍历源路径
    for root, _, files in os.walk(source_path):
        root_path = Path(root)
        
        # 检查当前路径是否在媒体类型文件夹内（包括父路径）
        if any(media_type in str(root_path) for media_type in MEDIA_TYPES):
            logger.info(f"跳过已整理的媒体文件夹路径: {root_path}")
            continue
            
        # 检查当前文件夹是否包含需要处理的媒体文件
        media_files = {}
        
        # 第一步：找出所有主媒体文件
        for file in files:
            file_path = root_path / file
            if not file_path.exists() or not file_path.is_file():
                continue
                
            for media_type, type_info in MEDIA_TYPES.items():
                if any(file.lower().endswith(ext) for ext in type_info['extensions']):
                    if media_type not in media_files:
                        media_files[media_type] = {'main': [], 'associated': []}
                    media_files[media_type]['main'].append(file_path)
        
        # 第二步：查找关联文件
        for file in files:
            file_path = root_path / file
            file_stem = file_path.stem
            
            for media_type, type_info in MEDIA_TYPES.items():
                if media_type in media_files:  # 只在已找到主媒体文件的类型中查找关联文件
                    for main_file in media_files[media_type]['main']:
                        if (file_path != main_file and  # 不是主文件本身
                            file_path.stem == main_file.stem and  # 文件名相同（不含扩展名）
                            any(file.lower().endswith(ext) for ext in type_info['associated_extensions'])):
                            media_files[media_type]['associated'].append(file_path)
                            break
        
        # 如果文件夹包含媒体文件，移动文件
        if media_files:
            try:
                relative_path = root_path.relative_to(source_path)
            except ValueError:
                logger.info(f"无法计算相对路径: {root_path} 相对于 {source_path}")
                continue
                
            for media_type, file_lists in media_files.items():
                target_dir = target_base_path / media_type / relative_path
                
                # 创建目标文件夹
                try:
                    target_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    logger.info(f"❌ 创建目标文件夹失败 {target_dir}: {e}")
                    continue
                
                # 移动主文件和关联文件
                for file_list in [file_lists['main'], file_lists['associated']]:
                    for file_path in file_list:
                        try:
                            if not file_path.exists() or not file_path.is_file():
                                continue
                                
                            target_file = target_dir / file_path.name
                            # 处理文件名冲突
                            final_target = target_file
                            counter = 1
                            while final_target.exists():
                                final_target = target_dir / f"{target_file.stem}_{counter}{target_file.suffix}"
                                counter += 1
                                
                            # 获取文件大小（移动前）
                            file_size = file_path.stat().st_size
                            
                            # 移动文件
                            shutil.move(str(file_path), str(final_target))
                            moved_count += 1
                            moved_size += file_size
                            logger.info(f"📦 已移动{'关联' if file_path in file_lists['associated'] else '主要'}媒体文件: {file_path.name} -> {final_target}")
                        except FileNotFoundError:
                            continue
                        except Exception as e:
                            logger.info(f"❌ 移动媒体文件失败 {file_path}: {e}")
    
    return moved_count, moved_size

def cmd_delete(path: str, is_directory: bool = False,) -> bool:
    """
    使用 CMD 命令删除文件或文件夹
    """
    try:
        if is_directory:
            # 删除目录及其所有内容
            cmd = f'cmd /c rmdir /s /q "{path}"'
        else:
            # 删除单个文件
            cmd = f'cmd /c del /f /q "{path}"'
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        logger.info(f"❌ CMD删除失败 {path}: {e}")
        return False

def delete_empty_folders(directory: Path):
    """删除空文件夹"""
    for root, dirs, files in os.walk(directory, topdown=False):
        for dir_name in dirs:
            dir_path = Path(root) / dir_name
            try:
                if not any(dir_path.iterdir()):
                    if not cmd_delete(str(dir_path), is_directory=True):
                        logger.info(f"❌ 删除空文件夹失败 {dir_path}")
                    else:
                        logger.info(f"🗑️ 已删除空文件夹: {dir_path}")
            except Exception as e:
                logger.info(f"❌ 检查空文件夹失败 {dir_path}: {e}")

def find_scattered_images(folder_path: Path) -> Tuple[bool, List[Path]]:
    """
    检查文件夹中是否存在散落图片，满足以下任一条件：
    1. 条件一：同时满足
       - 存在压缩包
       - 有3张以上图片
       - 没有子文件夹
    2. 条件二：同时满足
       - 文件夹内至少有1张图片
       - 存在子文件夹，且子文件夹内：
         - 包含多个图片 或
         - 包含1个或多个压缩包
    返回: (是否有散落图片, 散落图片文件列表)
    """
    image_files = []
    subdirs = []
    has_zip = False
    
    # 检查当前文件夹内容
    for item in folder_path.iterdir():
        if item.is_dir():
            subdirs.append(item)
        elif item.is_file():
            if item.suffix.lower() in IMAGE_EXTENSIONS:
                image_files.append(item)
            elif item.suffix.lower() == '.zip':
                has_zip = True
    
    # 条件一：压缩包 + 3张以上图片 + 无子文件夹
    if has_zip and len(image_files) >= 3 and not subdirs:
        return True, image_files
        
    # 条件二：至少1张图片 + 子文件夹（包含多图片或压缩包）
    if len(image_files) >= 1 and subdirs:
        for subdir in subdirs:
            subdir_images = []
            subdir_has_zip = False
            
            # 检查子文件夹内容
            for item in subdir.rglob('*'):
                if item.is_file():
                    if item.suffix.lower() in IMAGE_EXTENSIONS:
                        subdir_images.append(item)
                    elif item.suffix.lower() == '.zip':
                        subdir_has_zip = True
                        break  # 找到压缩包就可以停止搜索
            
            # 如果子文件夹包含多个图片或任意压缩包
            if len(subdir_images) > 1 or subdir_has_zip:
                return True, image_files  # 返回主文件夹中的图片
                
    return False, []

def zip_scattered_images(folder_path: Path, image_files: List[Path]) -> CompressionResult:
    """
    专门处理散落图片的压缩
    """
    zip_path = folder_path / f"{folder_path.name}_散图.zip"
    original_size = sum(f.stat().st_size for f in image_files)
    temp_folder = folder_path / f"{folder_path.name}_temp"
    
    try:
        # 如果临时文件夹已存在，先尝试删除
        if temp_folder.exists():
            if not cmd_delete(str(temp_folder), is_directory=True):
                logger.info(f"❌ 删除已存在的临时文件夹失败: {temp_folder}")
                # 使用不同的临时文件夹名称
                temp_folder = folder_path / f"{folder_path.name}_temp_{int(time())}"
        
        # 创建临时文件夹
        temp_folder.mkdir(exist_ok=True)
        
        # 复制图片到临时文件夹
        for file in image_files:
            try:
                shutil.copy2(file, temp_folder / file.name)
            except Exception as e:
                logger.info(f"❌ 复制文件失败 {file}: {e}")
                # 清理并返回错误
                cmd_delete(str(temp_folder), is_directory=True)
                return CompressionResult(False, error_message=f"复制文件失败: {str(e)}")
        
        # 压缩临时文件夹
        cmd = f'"{SEVEN_ZIP_PATH}" a -r -aoa -tzip -mx={COMPRESSION_LEVEL} "{zip_path}" "{temp_folder}\\*"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        # 等待一小段时间确保文件被释放
        time.sleep(0.5)
        
        # 删除临时文件夹
        if not cmd_delete(str(temp_folder), is_directory=True):
            logger.info(f"❌ 无法删除临时文件夹 {temp_folder}")
        
        # 如果压缩成功，删除原始图片文件
        if result.returncode == 0:
            delete_failures = []
            for file in image_files:
                if file.exists():
                    if not cmd_delete(str(file)):
                        delete_failures.append(str(file))
                        logger.info(f"❌ 删除原始文件失败 {file}")
            
            if delete_failures:
                # 如果有删除失败的文件，尝试批量删除
                try:
                    files_list = '" "'.join(delete_failures)
                    if not cmd_delete(f'"{files_list}"'):
                        logger.info(f"❌ 批量删除失败: {files_list}")
                except Exception as e:
                    logger.info(f"❌ 批量删除命令执行失败: {e}")
            
            if zip_path.exists():
                compressed_size = zip_path.stat().st_size
                return CompressionResult(True, original_size, compressed_size)
        
        return CompressionResult(False, error_message=f"Compression failed: {result.stderr}")
    except Exception as e:
        # 最后的清理尝试
        if temp_folder.exists():
            cmd_delete(str(temp_folder), is_directory=True)
        return CompressionResult(False, error_message=f"Error: {str(e)}")

def ensure_file_access(file_path: Path) -> bool:
    """
    确保文件可访问，通过修改文件权限和清除只读属性
    """
    logger.info(f"🔍 开始处理文件权限: {file_path}")
    try:
        if not file_path.exists():
            logger.info(f"❌ 文件不存在: {file_path}")
            return False
            
        # 检查文件当前权限
        try:
            current_mode = file_path.stat().st_mode
            logger.info(f"📝 当前文件权限: {current_mode:o}")
            
            # 检查是否为只读
            is_readonly = not bool(current_mode & stat.S_IWRITE)
            logger.info(f"🔒 文件是否只读: {is_readonly}")
            
            if is_readonly:
                file_path.chmod(current_mode | stat.S_IWRITE)
                logger.info("✅ 已清除只读属性")
        except Exception as e:
            logger.info(f"⚠️ 检查/修改文件属性失败: {file_path}, 错误: {str(e)}")
        
        try:
            # 获取当前进程的句柄
            logger.info("🔄 尝试获取进程句柄...")
            ph = win32api.GetCurrentProcess()
            logger.info(f"✅ 成功获取进程句柄: {ph}")
            
            # 打开进程令牌
            logger.info("🔄 尝试打开进程令牌...")
            th = win32security.OpenProcessToken(ph, win32con.TOKEN_QUERY)
            logger.info("✅ 成功打开进程令牌")
            
            # 获取用户SID
            logger.info("🔄 尝试获取用户SID...")
            user = win32security.GetTokenInformation(th, win32security.TokenUser)
            user_sid = user[0]
            logger.info(f"✅ 成功获取用户SID: {user_sid}")
            
            # 获取文件的安全描述符
            logger.info("🔄 尝试获取文件安全描述符...")
            sd = win32security.GetFileSecurity(
                str(file_path), 
                win32security.DACL_SECURITY_INFORMATION
            )
            logger.info("✅ 成功获取文件安全描述符")
            
            # 获取DACL
            logger.info("🔄 尝试获取DACL...")
            dacl = sd.GetSecurityDescriptorDacl()
            if dacl is None:
                logger.info("📝 DACL不存在，创建新的DACL")
                dacl = win32security.ACL()
            else:
                logger.info("✅ 成功获取现有DACL")
            
            # 添加完全控制权限
            logger.info("🔄 尝试添加完全控制权限...")
            dacl.AddAccessAllowedAce(
                win32security.ACL_REVISION,
                con.FILE_ALL_ACCESS | con.FILE_GENERIC_READ | con.FILE_GENERIC_WRITE,
                user_sid
            )
            logger.info("✅ 成功添加完全控制权限")
            
            # 设置新的DACL
            logger.info("🔄 尝试设置新的DACL...")
            sd.SetSecurityDescriptorDacl(1, dacl, 0)
            win32security.SetFileSecurity(
                str(file_path),
                win32security.DACL_SECURITY_INFORMATION,
                sd
            )
            logger.info("✅ 成功设置新的DACL")
            
            # 验证权限
            try:
                # 尝试打开文件进行读写测试
                with open(file_path, 'ab') as f:
                    pass
                logger.info("✅ 权限验证成功：文件可以打开进行写入")
            except Exception as e:
                logger.info(f"⚠️ 权限验证失败：无法打开文件进行写入: {e}")
                
        except Exception as e:
            logger.info(f"⚠️ 修改文件安全描述符失败: {file_path}, 错误: {str(e)}")
            # 即使修改安全描述符失败，也继续尝试
            pass
            
        return True
    except Exception as e:
        logger.info(f"❌ 修改文件权限失败: {file_path}, 错误: {str(e)}")
        return False

def process_with_prompt(directories: List[Path]) -> None:
    """使用prompt_toolkit处理目录"""
    # 定义选项
    values = [
        ("organize_media", "整理媒体文件"),
        ("move_unwanted", "移动不需要的文件"),
        ("compress", "压缩文件夹"),
        ("process_scattered", "处理散图"),
        ("select_all", "【全选】")
    ]
    
    # 第一次显示对话框
    options = checkboxlist_dialog(
        title="选择操作",
        text="请选择要执行的操作：\n" + "\n".join(f"- {d}" for d in directories),
        values=values,
        default_values=["compress"]  # 默认选中压缩选项
    ).run()
    
    # 如果用户取消了选择，直接返回
    if not options:
        return
    
    # 处理全选
    if "select_all" in options:
        options = [value[0] for value in values if value[0] != "select_all"]
    
    selected_options = {
        'organize_media': 'organize_media' in options,
        'move_unwanted': 'move_unwanted' in options,
        'compress': 'compress' in options,
        'process_scattered': 'process_scattered' in options
    }
    
    # 在完成选择后，启动日志界面并处理文件
    for directory in directories:
        logger.info(f"\n📂 开始处理目录: {directory}")
        
        if selected_options['move_unwanted']:
            unwanted_target_path = directory / "[00不需要]"
            unwanted_target_path.mkdir(exist_ok=True)
            logger.info(f"📁 创建不需要文件存放目录: {unwanted_target_path}")
            
            logger.info("🔄 开始处理不需要的文件...")
            moved_count, moved_size = move_unwanted_files(directory, unwanted_target_path)
            logger.info(f"✅ 已移动 {moved_count} 个文件，总大小: {moved_size/1024/1024:.2f}MB")
        
        if selected_options['organize_media']:
            logger.info("🔄 开始整理媒体文件...")
            media_count, media_size = organize_media_files(directory, directory)
            logger.info(f"✅ 已整理 {media_count} 个媒体文件，总大小: {media_size/1024/1024:.2f}MB")
        
        logger.info("🧹 清理空文件夹...")
        delete_empty_folders(directory)
        
        if selected_options['compress']:
            exclude_keywords = [
                *BLACKLIST_KEYWORDS,  # 包含所有黑名单关键词
                *[k for k in MEDIA_TYPES.keys()]  # 包含所有媒体类型文件夹
            ]
            zip_paths = process_folders(str(directory), exclude_keywords)
            logger.info(f"✅ 已完成文件夹压缩，共处理 {len(zip_paths)} 个文件夹")

        if selected_options['process_scattered']:
            logger.info("\n🔍 开始查找和处理散图...")
            processed_count = process_scattered_images_in_directory(directory)
            logger.info(f"✅ 散图处理完成，共处理 {processed_count} 个散图文件夹")
    
    logger.info("\n✨ 所有操作已完成")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='文件处理和压缩工具')
    parser.add_argument('--clipboard', action='store_true', help='从剪贴板读取路径')
    args = parser.parse_args()
    
    # 获取输入路径
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

    # 验证路径
    directories = []
    for path in input_text.strip().split('\n'):
        clean_path = path.strip().strip('"').strip("'").strip()
        if os.path.exists(clean_path):
            directories.append(Path(clean_path))
        else:
            print(f"⚠️ 警告：路径不存在: {clean_path}")
    
    if not directories:
        print("❌ 错误：未输入有效路径，程序退出")
        return

    # 使用prompt_toolkit界面处理目录
    process_with_prompt(directories)

if __name__ == '__main__':
    main()
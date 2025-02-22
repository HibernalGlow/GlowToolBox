from pathlib import Path
import sys
import os
import json
import logging
from typing import List, Dict, Set, Tuple
import time
import subprocess
import argparse
import pyperclip
from nodes.config.import_bundles import *
from nodes.record.logger_config import setup_logger
from nodes.tui.mode_manager import create_mode_manager
from nodes.file_ops.backup_handler import BackupHandler
from nodes.file_ops.archive_handler import ArchiveHandler
from nodes.pics.image_filter import ImageFilter
from nodes.io.input_handler import InputHandler
from nodes.io.config_handler import ConfigHandler
from nodes.io.path_handler import PathHandler, ExtractMode
import platform
import stat
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import multiprocessing

# 在文件开头添加常量
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.avif', '.heic', '.heif', '.jxl'}

config = {
    'script_name': 'recruit_cover_filter',
    'console_enabled': False,
}
logger, config_info = setup_logger(config)
DEBUG_MODE = False

TEXTUAL_LAYOUT = {
    "cur_stats": {
        "ratio": 1,
        "title": "📊 总体进度",
        "style": "lightyellow"
    },
    "cur_progress": {
        "ratio": 1,
        "title": "🔄 当前进度",
        "style": "lightcyan"
    },
    "file_ops": {
        "ratio": 2,
        "title": "📂 文件操作",
        "style": "lightpink"
    },
    "ocr_results": {
        "ratio": 2,
        "title": "📝 OCR结果",
        "style": "lightgreen"
    },
    "update_log": {
        "ratio": 1,
        "title": "🔧 系统消息",
        "style": "lightwhite"
    }
}

def initialize_textual_logger(layout: dict, log_file: str) -> None:
    """
    初始化日志布局
    
    Args:
        layout: 布局配置字典
        log_file: 日志文件路径
    """
    try:
        TextualLoggerManager.set_layout(layout, config_info['log_file'])
        logger.info("[#update_log]✅ 日志系统初始化完成")
    except Exception as e:
        print(f"❌ 日志系统初始化失败: {e}") 

class RecruitCoverFilter:
    """封面图片过滤器"""
    
    def __init__(self, hash_file: str = None, hamming_threshold: int = 16, watermark_keywords: List[str] = None, max_workers: int = None):
        """初始化过滤器"""
        self.image_filter = ImageFilter(hash_file, hamming_threshold)
        self.watermark_keywords = watermark_keywords
        self.max_workers = max_workers or multiprocessing.cpu_count()
        # 初始化日志系统（只初始化一次）
        initialize_textual_logger(TEXTUAL_LAYOUT, config_info['log_file'])
        
    def prepare_hash_file(self, recruit_folder: str, workers: int = 16, force_update: bool = False) -> str:
        """
        准备哈希文件
        
        Args:
            recruit_folder: 招募文件夹路径
            workers: 工作线程数
            force_update: 是否强制更新
            
        Returns:
            str: 哈希文件路径，失败返回None
        """
        try:
            from nodes.pics.hash_process_config import process_artist_folder
            hash_file = process_artist_folder(recruit_folder, workers, force_update)
            if hash_file:
                logger.info(f"[#update_log]✅ 成功生成哈希文件: {hash_file}")
                self.image_filter.hash_file = hash_file
                self.image_filter.hash_cache = self.image_filter._load_hash_file()
                return hash_file
            else:
                logger.error("[#update_log]❌ 生成哈希文件失败")
                return None
        except Exception as e:
            logger.error(f"[#update_log]❌ 准备哈希文件时出错: {e}")
            return None

    def _robust_cleanup(self, temp_dir: str) -> None:
        """更健壮的文件清理方法，处理文件被占用的情况"""
        if not os.path.exists(temp_dir):
            return

        def on_rm_error(func, path, exc_info):
            try:
                os.chmod(path, stat.S_IWRITE)
                os.unlink(path)
                logger.info(f"[#file_ops]成功删除 {path}")
            except Exception as e:
                logger.warning(f"[#file_ops]无法删除 {path}: {e}")

        try:
            # 尝试标准删除
            shutil.rmtree(temp_dir, onerror=on_rm_error)
        except Exception as e:
            logger.warning(f"[#file_ops]标准删除失败，尝试强制删除: {temp_dir}")
            try:
                # 使用系统命令强制删除（Windows）
                if platform.system() == 'Windows':
                    subprocess.run(f'rmdir /s /q "{temp_dir}"', shell=True, check=True)
                else:  # Linux/MacOS
                    subprocess.run(f'rm -rf "{temp_dir}"', shell=True, check=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"[#update_log]强制删除失败: {temp_dir}")
                raise

    def process_archive(self, zip_path: str, extract_mode: str = ExtractMode.ALL, extract_params: dict = None, is_dehash_mode: bool = False) -> bool:
        """处理单个压缩包"""
        logger.info(f"[#file_ops]开始处理压缩包: {zip_path}")
        
        # 列出压缩包内容并预先过滤图片文件
        files = [f for f in ArchiveHandler.list_archive_contents(zip_path)
                if PathHandler.get_file_extension(f).lower() in SUPPORTED_EXTENSIONS]
        
        if not files:
            logger.info("[#file_ops]未找到图片文件")
            return False
            
        # 获取要解压的文件索引
        extract_params = extract_params or {}
        
        # 去汉化模式特殊处理：合并前N张和后N张的索引
        if is_dehash_mode:
            front_n = extract_params.get('front_n', 3)  # 默认前3张
            back_n = extract_params.get('back_n', 5)    # 默认后5张
            
            # 直接计算索引，避免多次列表操作
            total_files = len(files)
            front_indices = range(min(front_n, total_files))
            back_indices = range(max(0, total_files - back_n), total_files)
            selected_indices = sorted(set(front_indices) | set(back_indices))
        else:
            selected_indices = ExtractMode.get_selected_indices(extract_mode, len(files), extract_params)
            
        if not selected_indices:
            logger.error("[#file_ops]未选择任何文件进行解压")
            return False
            
        # 生成解压目录名称
        zip_name = os.path.splitext(os.path.basename(zip_path))[0]
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        extract_dir = os.path.join(os.path.dirname(zip_path), f"temp_{zip_name}_{timestamp}")
            
        # 解压选定文件
        selected_files = [files[i] for i in selected_indices]
        success, extract_dir = ArchiveHandler.extract_files(zip_path, selected_files, extract_dir)
        if not success:
            return False
            
        try:
            # 获取解压后的图片文件（使用列表推导式优化）
            image_files = [
                PathHandler.join_paths(root, file)
                for root, _, files in os.walk(extract_dir)
                for file in files
                if PathHandler.get_file_extension(file).lower() in SUPPORTED_EXTENSIONS
            ]
                        
            # 处理图片
            to_delete, removal_reasons = self.image_filter.process_images(
                image_files,
                enable_duplicate_filter=True,   # 启用重复图片过滤
                duplicate_filter_mode='hash' if self.image_filter.hash_file else 'watermark',  # 如果有哈希文件则使用哈希模式
                watermark_keywords=None if is_dehash_mode else self.watermark_keywords  # 去汉化模式不启用水印检测
            )
            
            if not to_delete:
                logger.info("[#file_ops]没有需要删除的图片")
                self._robust_cleanup(extract_dir)
                return False
                
            # 备份要删除的文件
            backup_results = BackupHandler.backup_removed_files(zip_path, to_delete, removal_reasons)
            
            # 从压缩包中删除文件（使用列表推导式优化）
            files_to_delete = [os.path.relpath(file_path, extract_dir) for file_path in to_delete]
                
            # 使用7z删除文件
            delete_list_file = os.path.join(extract_dir, '@delete.txt')
            with open(delete_list_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(files_to_delete))
                    
            # 在执行删除操作前备份原始压缩包
            backup_success, backup_path = BackupHandler.backup_source_file(zip_path)
            if backup_success:
                logger.info(f"[#file_ops]✅ 源文件备份成功: {backup_path}")
            else:
                logger.warning(f"[#file_ops]⚠️ 源文件备份失败: {backup_path}")

            # 使用7z删除文件
            cmd = ['7z', 'd', zip_path, f'@{delete_list_file}']
            result = subprocess.run(cmd, capture_output=True, text=True)
            os.remove(delete_list_file)
            
            if result.returncode != 0:
                logger.error(f"[#file_ops]从压缩包删除文件失败: {result.stderr}")
                self._robust_cleanup(extract_dir)
                return False
                
            logger.info(f"[#file_ops]成功处理压缩包: {zip_path}")
            self._robust_cleanup(extract_dir)
            return True
            
        except Exception as e:
            logger.error(f"[#file_ops]处理压缩包失败 {zip_path}: {e}")
            self._robust_cleanup(extract_dir)
            return False

class Application:
    """应用程序类"""
    
    def __init__(self, max_workers: int = None):
        """初始化应用程序
        
        Args:
            max_workers: 最大工作线程数，默认为CPU核心数
        """
        self.max_workers = max_workers or multiprocessing.cpu_count()
        self.archive_queue = Queue()
        
    def _process_single_archive(self, args):
        """处理单个压缩包的包装函数"""
        zip_path, filter_instance, extract_params, is_dehash_mode = args
        try:
            return filter_instance.process_archive(zip_path, extract_params=extract_params, is_dehash_mode=is_dehash_mode)
        except Exception as e:
            logger.error(f"[#update_log]处理压缩包失败 {zip_path}: {e}")
            return False
    
    def process_directory(self, directory: str, filter_instance: RecruitCoverFilter, is_dehash_mode: bool = False, extract_params: dict = None):
        """处理目录"""
        try:
            # 定义黑名单关键词
            blacklist_keywords = ["画集", "CG", "图集"]
            
            # 收集所有需要处理的压缩包
            archives_to_process = []
            
            if os.path.isfile(directory):
                if directory.lower().endswith('.zip'):
                    archives_to_process.append(directory)
            else:
                for root, _, files in os.walk(directory):
                    # 检查当前目录路径是否包含黑名单关键词
                    root_lower = root.lower()
                    if any(kw in root_lower for kw in blacklist_keywords):
                        logger.info(f"[#file_ops]跳过黑名单目录: {root}")
                        continue
                    
                    for file in files:
                        if file.lower().endswith('.zip'):
                            zip_path = os.path.join(root, file)
                            archives_to_process.append(zip_path)
            
            if not archives_to_process:
                return
                
            # 使用线程池并行处理压缩包
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 创建任务列表
                future_to_archive = {
                    executor.submit(
                        self._process_single_archive, 
                        (archive, filter_instance, extract_params, is_dehash_mode)
                    ): archive for archive in archives_to_process
                }
                
                # 等待所有任务完成
                for future in as_completed(future_to_archive):
                    archive = future_to_archive[future]
                    try:
                        success = future.result()
                        if success:
                            logger.info(f"[#file_ops]✅ 成功处理: {os.path.basename(archive)}")
                        else:
                            logger.warning(f"[#file_ops]⚠️ 处理失败: {os.path.basename(archive)}")
                    except Exception as e:
                        logger.error(f"[#file_ops]处理出错 {os.path.basename(archive)}: {e}")
                        
        except Exception as e:
            logger.error(f"[#update_log]处理目录失败 {directory}: {e}")

def setup_cli_parser():
    """设置命令行参数解析器"""
    parser = argparse.ArgumentParser(description='招募封面图片过滤工具')
    parser.add_argument('--debug', '-d', action='store_true',
                      help='启用调试模式')
    parser.add_argument('--hash-file', '-hf', type=str,
                      help='哈希文件路径（可选，默认使用全局配置）')
    parser.add_argument('--hamming-threshold', '-ht', type=int, default=16,
                      help='汉明距离阈值 (默认: 16)')
    parser.add_argument('--clipboard', '-c', action='store_true',
                      help='从剪贴板读取路径')
    parser.add_argument('--watermark-keywords', '-wk', nargs='*',
                      help='水印关键词列表，不指定则使用默认列表')
    parser.add_argument('--duplicate-filter-mode', '-dfm', type=str,
                      choices=['quality', 'watermark', 'hash'],
                      default='quality', help='重复过滤模式 (默认: quality)')
    parser.add_argument('--extract-mode', '-em', type=str, 
                      choices=[ExtractMode.ALL, ExtractMode.FIRST_N, ExtractMode.LAST_N, ExtractMode.RANGE],
                      default=ExtractMode.ALL, help='解压模式 (默认: all)')
    parser.add_argument('--extract-n', '-en', type=int,
                      help='解压数量 (用于 first_n 和 last_n 模式)')
    parser.add_argument('--extract-range', '-er', type=str,
                      help='解压范围 (用于 range 模式，格式: start:end)')
    parser.add_argument('--dehash-mode', '-dm', action='store_true',
                      help='启用去汉化模式')
    parser.add_argument('--front-n', '-fn', type=int, default=3,
                      help='去汉化模式：处理前N张图片 (默认: 3)')
    parser.add_argument('--back-n', '-bn', type=int, default=5,
                      help='去汉化模式：处理后N张图片 (默认: 5)')
    parser.add_argument('--workers', '-w', type=int, default=16,
                      help='最大工作线程数，默认为CPU核心数')
    parser.add_argument('path', nargs='*', help='要处理的文件或目录路径')
    return parser

def run_application(args):
    """运行应用程序"""
    try:
        paths = InputHandler.get_input_paths(
            cli_paths=args.path,
            use_clipboard=args.clipboard,
            path_normalizer=PathHandler.normalize_path
        )
        
        if not paths:
            logger.error("[#update_log]未提供任何有效路径")
            return False
            
        filter_instance = RecruitCoverFilter(
            hash_file=args.hash_file,
            hamming_threshold=args.hamming_threshold,
            watermark_keywords=args.watermark_keywords,
            max_workers=args.workers  # 传递线程数参数
        )
        
        # 准备解压参数
        extract_params = {}
        if args.dehash_mode:
            extract_params['front_n'] = args.front_n
            extract_params['back_n'] = args.back_n
        elif args.extract_mode in [ExtractMode.FIRST_N, ExtractMode.LAST_N]:
            extract_params['n'] = args.extract_n
        elif args.extract_mode == ExtractMode.RANGE:
            extract_params['range_str'] = args.extract_range
            
        # 创建应用程序实例，使用指定的线程数
        app = Application(max_workers=args.workers)
        
        for path in paths:
            if args.dehash_mode:
                if not filter_instance.image_filter.hash_file:
                    recruit_folder = r"E:\1EHV\[01杂]\zzz去图"
                    hash_file = filter_instance.prepare_hash_file(recruit_folder)
                    if not hash_file:
                        logger.error(f"[#update_log]❌ 去汉化模式需要哈希文件，但准备失败")
                        continue
                
                app.process_directory(path, filter_instance, is_dehash_mode=True, extract_params=extract_params)
            else:
                app.process_directory(path, filter_instance, extract_params=extract_params)
            
        logger.info("[#update_log]✅ 所有任务已完成")
        return True
        
    except Exception as e:
        logger.error(f"[#update_log]程序执行失败: {e}")
        return False

def get_mode_config():
    """获取模式配置"""
    return {
        'use_debugger': True,
        'use_tui': True,
        'debug_config': {
            'base_modes': {
                "1": {
                    "name": "去水印模式",
                    "description": "检测并删除带水印的图片",
                    "base_args": ["-ht", "--duplicate-filter-mode", "watermark"],
                    "default_params": {
                        "ht": "16"
                    }
                },
                "2": {
                    "name": "去汉化模式",
                    "description": "处理前后N张图片并使用哈希去重",
                    "base_args": ["-dm", "-ht", "-fn", "-bn"],
                    "default_params": {
                        "ht": "16",
                        "fn": "3",
                        "bn": "5"
                    }
                }
            },
            'param_options': {
                "ht": {"name": "汉明距离阈值", "arg": "-ht", "default": "16", "type": int},
                "en": {"name": "解压数量", "arg": "-en", "default": "3", "type": int},
                "er": {"name": "解压范围", "arg": "-er", "default": "0:3", "type": str},
                "fn": {"name": "前N张数量", "arg": "-fn", "default": "3", "type": int},
                "bn": {"name": "后N张数量", "arg": "-bn", "default": "5", "type": int},
                "c": {"name": "从剪贴板读取", "arg": "-c", "is_flag": True},
                "dfm": {"name": "重复过滤模式", "arg": "--duplicate-filter-mode", "default": "quality", "type": str}
            }
        },
        'tui_config': {
            'checkbox_options': [
                ("从剪贴板读取", "clipboard", "-c"),
                ("去汉化模式", "dehash_mode", "-dm"),
            ],
            'input_options': [
                ("汉明距离阈值", "hamming_threshold", "-ht", "16", "输入数字(默认16)"),
                ("解压数量", "extract_n", "-en", "3", "输入数字(默认3)"),
                ("解压范围", "extract_range", "-er", "0:3", "格式: start:end"),
                ("前N张数量", "front_n", "-fn", "3", "输入数字(默认3)"),
                ("后N张数量", "back_n", "-bn", "5", "输入数字(默认5)"),
                ("哈希文件路径", "hash_file", "-hf", "", "输入哈希文件路径(可选)"),
                ("重复过滤模式", "duplicate_filter_mode", "--duplicate-filter-mode", "quality", "quality/watermark/hash"),
            ],
            'preset_configs': {
                "去水印模式": {
                    "description": "检测并删除带水印的图片",
                    "checkbox_options": ["clipboard"],
                    "input_values": {
                        "hamming_threshold": "16",
                        "front_n": "3",
                        "duplicate_filter_mode": "watermark"
                    }
                },
                "去汉化模式": {
                    "description": "处理前后N张图片并使用哈希去重",
                    "checkbox_options": ["clipboard", "dehash_mode"],
                    "input_values": {
                        "hamming_threshold": "16",
                        "front_n": "3",
                        "back_n": "5",
                        "duplicate_filter_mode": "hash"
                    }
                }
            }
        }
    }

# 调试模式开关

if __name__ == '__main__':
    mode_manager = create_mode_manager(
        config=get_mode_config(),
        cli_parser_setup=setup_cli_parser,
        application_runner=run_application
    )
    
    if DEBUG_MODE:
        success = mode_manager.run_debug()
    elif len(sys.argv) > 1:
        success = mode_manager.run_cli()
    else:
        success = mode_manager.run_tui()
    
    if not success:
        sys.exit(1) 
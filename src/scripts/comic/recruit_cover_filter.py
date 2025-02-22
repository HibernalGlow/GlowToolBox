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
import zipfile
from datetime import datetime
import re

# 在文件开头添加常量
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.avif', '.heic', '.heif', '.jxl'}
LOGS_DIR = r"D:\1VSCODE\GlowToolBox\logs\recruit_cover_filter"
PROCESSED_PATHS_FILE = r"D:\1VSCODE\GlowToolBox\data\processed_paths.txt"
PROCESSED_CACHE = set()

config = {
    'script_name': 'recruit_cover_filter',
    'console_enabled': False,
}
logger, config_info = setup_logger(config)
DEBUG_MODE = False

TEXTUAL_LAYOUT = {
    # "global_progress": {
    #     "ratio": 1,
    #     "title": "🌐 总体进度",
    #     "style": "lightyellow"
    # },
    "path_progress": {
        "ratio": 1,
        "title": "🔄 当前进度",
        "style": "lightcyan"
    },
    "file_ops": {
        "ratio": 2,
        "title": "📂 文件操作",
        "style": "lightpink"
    },
    "sys_log": {
        "ratio": 1,
        "title": "🔧 系统消息",
        "style": "lightgreen"
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
        logger.info("[#sys_log]✅ 日志系统初始化完成")
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
                logger.info(f"[#sys_log]✅ 成功生成哈希文件: {hash_file}")
                self.image_filter.hash_file = hash_file
                self.image_filter.hash_cache = self.image_filter._load_hash_file()
                return hash_file
            else:
                logger.error("[#sys_log]❌ 生成哈希文件失败")
                return None
        except Exception as e:
            logger.error(f"[#sys_log]❌ 准备哈希文件时出错: {e}")
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
                logger.error(f"[#sys_log]强制删除失败: {temp_dir}")
                raise

    def process_archive(self, zip_path: str, extract_mode: str = ExtractMode.ALL, extract_params: dict = None, is_dehash_mode: bool = False) -> Tuple[bool, str]:
        """处理单个压缩包
        
        Returns:
            Tuple[bool, str]: (是否成功, 失败原因)
        """
        logger.info(f"[#file_ops]开始处理压缩包: {zip_path}")
        
        # 列出压缩包内容并预先过滤图片文件
        files = [f for f in ArchiveHandler.list_archive_contents(zip_path)
                if PathHandler.get_file_extension(f).lower() in SUPPORTED_EXTENSIONS]
        
        if not files:
            logger.info("[#file_ops]未找到图片文件")
            return False, "未找到图片文件"
            
        # 获取要解压的文件索引
        extract_params = extract_params or {}
        
        # 如果指定了front_n或back_n，强制使用RANGE模式
        if extract_params.get('front_n', 0) > 0 or extract_params.get('back_n', 0) > 0:
            extract_mode = ExtractMode.RANGE
            logger.info(f"[#file_ops]使用前后N张模式: front_n={extract_params.get('front_n', 0)}, back_n={extract_params.get('back_n', 0)}")
        
        # 获取选中的文件索引
        selected_indices = ExtractMode.get_selected_indices(extract_mode, len(files), extract_params)
        
        # 记录选中的文件信息
        logger.info(f"[#file_ops]总文件数: {len(files)}, 选中文件数: {len(selected_indices)}")
        if len(selected_indices) > 0:
            logger.info(f"[#file_ops]选中的文件索引: {sorted(selected_indices)}")
            
        if not selected_indices:
            logger.error("[#file_ops]未选择任何文件进行解压")
            return False, "未选择任何文件进行解压"
            
        # 生成解压目录名称
        zip_name = os.path.splitext(os.path.basename(zip_path))[0]
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        extract_dir = os.path.join(os.path.dirname(zip_path), f"temp_{zip_name}_{timestamp}")
            
        # 解压选定文件
        selected_files = [files[i] for i in selected_indices]
        logger.info(f"[#sys_log]准备解压文件: {[os.path.basename(f) for f in selected_files]}")
        
        # 更新解压进度
        logger.info(f"[#path_progress]解压文件: {os.path.basename(zip_path)}")
        logger.info(f"[#path_progress]当前进度: 0%")

        success, extract_dir = ArchiveHandler.extract_files(zip_path, selected_files, extract_dir)
        if not success:
            logger.info(f"[#path_progress]解压文件: {os.path.basename(zip_path)} (失败)")
            return False, "解压文件失败"
        logger.info(f"[#path_progress]解压文件: {os.path.basename(zip_path)}")
        logger.info(f"[#path_progress]当前进度: 50%")
            
        try:
            # 获取解压后的图片文件
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
                logger.info("[#sys_log]没有需要删除的图片")
                self._robust_cleanup(extract_dir)
                logger.info(f"[#path_progress]处理文件: {os.path.basename(zip_path)}")
                logger.info(f"[@path_progress]当前进度: 100%")
                return True, "没有需要删除的图片"
                
            # 备份要删除的文件
            backup_results = BackupHandler.backup_removed_files(zip_path, to_delete, removal_reasons)
            
            # 从压缩包中删除文件
            files_to_delete = [os.path.relpath(file_path, extract_dir) for file_path in to_delete]
            logger.info(f"[#path_progress]处理文件: {os.path.basename(zip_path)}")
            logger.info(f"[@path_progress]当前进度: 75%")
                
            # 使用7z删除文件
            delete_list_file = os.path.join(extract_dir, '@delete.txt')
            with open(delete_list_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(files_to_delete))
                    
            # 在执行删除操作前备份原始压缩包
            backup_success, backup_path = BackupHandler.backup_source_file(zip_path)
            if backup_success:
                logger.info(f"[#sys_log]✅ 源文件备份成功: {backup_path}")
            else:
                logger.warning(f"[#sys_log]⚠️ 源文件备份失败: {backup_path}")
                return False, "源文件备份失败"

            # 使用7z删除文件
            cmd = ['7z', 'd', zip_path, f'@{delete_list_file}']
            result = subprocess.run(cmd, capture_output=True, text=True)
            os.remove(delete_list_file)
            
            if result.returncode != 0:
                logger.error(f"[#sys_log]从压缩包删除文件失败: {result.stderr}")
                self._robust_cleanup(extract_dir)
                logger.info(f"[#path_progress]处理文件: {os.path.basename(zip_path)} (失败)")
                return False, f"从压缩包删除文件失败: {result.stderr}"
                
            logger.info(f"[#file_ops]成功处理压缩包: {zip_path}")
            self._robust_cleanup(extract_dir)
            logger.info(f"[#path_progress]处理文件: {os.path.basename(zip_path)}")
            logger.info(f"[@path_progress]当前进度: 100%")
            return True, ""
            
        except Exception as e:
            logger.error(f"[#sys_log]处理压缩包失败 {zip_path}: {e}")
            self._robust_cleanup(extract_dir)
            logger.info(f"[#path_progress]处理文件: {os.path.basename(zip_path)} (错误)")
            return False, f"处理过程出错: {str(e)}"

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
        """处理单个压缩包或目录的包装函数
        
        Args:
            args: 包含处理参数的元组 (path, filter_instance, extract_params, is_dehash_mode)
            
        Returns:
            Tuple[bool, str]: (是否成功, 失败原因)
        """
        path, filter_instance, extract_params, is_dehash_mode = args
        try:
            # 检查路径是否存在
            if not os.path.exists(path):
                raise FileNotFoundError(f"路径不存在: {path}")
                
            # 检查路径是否可访问
            if not os.access(path, os.R_OK):
                raise PermissionError(f"路径无法访问: {path}")
            
            # 定义黑名单关键词
            blacklist_keywords = ["画集", "CG", "图集"]
            
            # 如果是目录，递归处理目录下的所有zip文件
            if os.path.isdir(path):
                success = True
                error_msg = ""
                for root, _, files in os.walk(path):
                    # 检查当前目录路径是否包含黑名单关键词
                    root_lower = root.lower()
                    if any(kw in root_lower for kw in blacklist_keywords):
                        logger.info(f"[#sys_log]跳过黑名单目录: {root}")
                        continue
                        
                    for file in files:
                        if file.lower().endswith('.zip'):
                            zip_path = os.path.join(root, file)
                            # 检查文件名是否包含黑名单关键词
                            if any(kw in file.lower() for kw in blacklist_keywords):
                                logger.info(f"[#sys_log]跳过黑名单文件: {file}")
                                continue
                                
                            try:
                                if not zipfile.is_zipfile(zip_path):
                                    logger.warning(f"[#sys_log]跳过无效的ZIP文件: {zip_path}")
                                    continue
                                    
                                # 处理单个zip文件
                                file_success, file_error = filter_instance.process_archive(
                                    zip_path,
                                    extract_mode=ExtractMode.RANGE,  # 默认使用RANGE模式
                                    extract_params=extract_params,
                                    is_dehash_mode=is_dehash_mode
                                )
                                if not file_success:
                                    logger.warning(f"[#file_ops]处理返回失败: {os.path.basename(zip_path)}, 原因: {file_error}")
                                    error_msg = file_error
                                success = success and file_success
                            except Exception as e:
                                error_msg = str(e)
                                logger.error(f"[#file_ops]处理ZIP文件失败 {zip_path}: {error_msg}")
                                success = False
                return success, error_msg
                
            # 如果是文件，确保是zip文件
            elif path.lower().endswith('.zip'):
                # 检查文件名是否包含黑名单关键词
                if any(kw in os.path.basename(path).lower() for kw in blacklist_keywords):
                    logger.info(f"[#file_ops]跳过黑名单文件: {os.path.basename(path)}")
                    return False, "黑名单文件"
                    
                if not zipfile.is_zipfile(path):
                    raise ValueError(f"不是有效的ZIP文件: {path}")
                    
                # 去汉化模式特殊处理
                if is_dehash_mode:
                    if not filter_instance.image_filter.hash_file:
                        logger.error("[#sys_log]❌ 去汉化模式需要哈希文件")
                        return False, "去汉化模式需要哈希文件"
                    logger.info("[#sys_log]✅ 使用去汉化模式处理")
                
                # 处理压缩包
                return filter_instance.process_archive(
                    path,
                    extract_mode=ExtractMode.RANGE,
                    extract_params=extract_params,
                    is_dehash_mode=is_dehash_mode
                )
            else:
                logger.warning(f"[#file_ops]跳过非ZIP文件: {path}")
                return False, "非ZIP文件"
            
        except FileNotFoundError as e:
            logger.error(f"[#file_ops]路径不存在: {path}")
            raise
        except PermissionError as e:
            logger.error(f"[#file_ops]路径访问权限错误: {path}")
            raise
        except Exception as e:
            logger.error(f"[#file_ops]处理过程出错: {path}: {str(e)}")
            raise
            
    def process_directory(self, directory: str, filter_instance: RecruitCoverFilter, is_dehash_mode: bool = False, extract_params: dict = None):
        """处理目录或文件"""
        try:
            # 加载已处理文件的缓存
            global PROCESSED_CACHE
            if not PROCESSED_CACHE:
                PROCESSED_CACHE = load_processed_files(PROCESSED_PATHS_FILE)
            
            # 获取当前路径
            abs_path = os.path.abspath(directory)
            
            # 检查当前路径或其父目录是否已处理
            for processed_dir in PROCESSED_CACHE:
                if abs_path.startswith(processed_dir):
                    logger.info(f"[#sys_log]跳过已处理目录: {abs_path}")
                    return True, "目录已处理"
            
            return self._process_single_archive((directory, filter_instance, extract_params, is_dehash_mode))
        
        except Exception as e:
            logger.error(f"[#sys_log]处理失败 {directory}: {e}")
            return False, "处理失败"

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
                      default='watermark',
                      help='重复过滤模式 (hash=去汉化模式, watermark=去水印模式, quality=质量模式)')
    parser.add_argument('--extract-mode', '-em', type=str, 
                      choices=[ExtractMode.ALL, ExtractMode.RANGE],
                      default=ExtractMode.ALL, help='解压模式 (默认: all)')
    parser.add_argument('--extract-range', '-er', type=str,
                      help='解压范围 (用于 range 模式，格式: start:end)')
    parser.add_argument('--front-n', '-fn', type=int, default=3,
                      help='处理前N张图片 (默认: 3)')
    parser.add_argument('--back-n', '-bn', type=int, default=5,
                      help='处理后N张图片 (默认: 5)')
    parser.add_argument('--workers', '-w', type=int, default=16,
                      help='最大工作线程数，默认为CPU核心数')
    parser.add_argument('path', nargs='*', help='要处理的文件或目录路径')
    return parser

def run_application(args):
    """运行应用程序"""
    try:
        # 根据过滤模式判断是否为去汉化模式
        is_dehash_mode = args.duplicate_filter_mode == 'hash'
        
        # 添加模式判断的日志
        logger.info(f"[#sys_log]运行模式: {'去汉化模式' if is_dehash_mode else '去水印模式'}")
        logger.info(f"[#sys_log]过滤模式: {args.duplicate_filter_mode}")

        paths = InputHandler.get_input_paths(
            cli_paths=args.path,
            use_clipboard=args.clipboard,
            path_normalizer=PathHandler.normalize_path
        )
        
        if not paths:
            logger.error("[#sys_log]未提供任何有效路径")
            return False
            
        # 修改过滤器初始化逻辑
        filter_instance = RecruitCoverFilter(
            hash_file=args.hash_file,
            hamming_threshold=args.hamming_threshold,
            # 如果是去汉化模式，则不使用水印关键词
            watermark_keywords=None if is_dehash_mode else args.watermark_keywords,
            max_workers=args.workers
        )

        # 如果是去汉化模式且没有指定哈希文件，自动准备哈希文件
        if is_dehash_mode and not args.hash_file:
            recruit_folder = r"E:\1EHV\[01杂]\zzz去图"
            hash_file = filter_instance.prepare_hash_file(recruit_folder)
            if not hash_file:
                logger.error("[#sys_log]❌ 去汉化模式需要哈希文件，但准备失败")
                return False

        # 准备解压参数
        extract_params = {
            'front_n': args.front_n,
            'back_n': args.back_n
        }
        
        if args.extract_mode == ExtractMode.RANGE and args.extract_range:
            extract_params['range_str'] = args.extract_range
            
        # 创建应用程序实例
        app = Application(max_workers=args.workers)
        
        # 记录处理参数
        logger.info(f"[#sys_log]处理参数: front_n={args.front_n}, back_n={args.back_n}, mode={args.extract_mode}")
        if args.extract_range:
            logger.info(f"[#sys_log]解压范围: {args.extract_range}")
        
        total_count = len(paths)
        success_count = 0
        error_count = 0
        error_details = []
        
        # 显示初始全局进度
        logger.info(f"[@global_progress]总任务进度 (0/{total_count}) 0%")
        
        # 使用线程池并行处理压缩包
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            # 创建任务列表
            future_to_archive = {
                executor.submit(
                    app._process_single_archive, 
                    (archive, filter_instance, extract_params, is_dehash_mode)
                ): archive for archive in paths
            }
            
            # 等待所有任务完成
            for future in as_completed(future_to_archive):
                archive = future_to_archive[future]
                try:
                    # 显示当前处理的文件进度
                    logger.info(f"[#path_progress]处理文件: {os.path.basename(archive)}")
                    logger.info(f"[@path_progress]当前进度: 0%")
                    
                    success, error_msg = future.result()
                    if success:
                        success_count += 1
                        logger.info(f"[#file_ops]✅ 成功处理: {os.path.basename(archive)}")
                        # 更新当前文件进度为100%
                        logger.info(f"[#path_progress]处理文件: {os.path.basename(archive)}")
                        logger.info(f"[@path_progress]当前进度: 100%")
                    else:
                        error_count += 1
                        error_msg = f"处理返回失败: {os.path.basename(archive)}, 原因: {error_msg}"
                        error_details.append(error_msg)
                        logger.warning(f"[#file_ops]⚠️ {error_msg}")
                        # 更新当前文件进度为失败
                        logger.info(f"[#path_progress]处理文件: {os.path.basename(archive)} (失败)")
                except Exception as e:
                    error_count += 1
                    import traceback
                    error_trace = traceback.format_exc()
                    error_msg = f"处理出错 {os.path.basename(archive)}: {str(e)}\n{error_trace}"
                    error_details.append(error_msg)
                    logger.error(f"[#file_ops]❌ {error_msg}")
                    # 更新当前文件进度为错误
                    logger.info(f"[#path_progress]处理文件: {os.path.basename(archive)} (错误)")
                
                # 更新全局进度
                completed = success_count + error_count
                progress = (completed / total_count) * 100
                logger.info(f"[@global_progress]总任务进度 ({completed}/{total_count}) {progress:.1f}%")
        
        # 输出最终统计信息
        logger.info(f"[#sys_log]处理完成 ✅成功: {success_count} ❌失败: {error_count} 总数: {total_count}")
        
        # 如果有错误，输出详细信息
        if error_details:
            logger.info("[#sys_log]错误详情:")
            for i, error in enumerate(error_details, 1):
                logger.info(f"[#sys_log]{i}. {error}")
        
        return True
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"[#sys_log]程序执行失败: {str(e)}\n{error_trace}")
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
                        "ht": "16",
                        "front_n": "3",
                        "back_n": "0"
                    }
                },
                "2": {
                    "name": "去汉化模式",
                    "description": "处理前后N张图片并使用哈希去重",
                    "base_args": ["-ht", "-fn", "-bn"],
                    "default_params": {
                        "ht": "16",
                        "front_n": "3",
                        "back_n": "5"
                    }
                }
            },
            'param_options': {
                "ht": {"name": "汉明距离阈值", "arg": "-ht", "default": "16", "type": int},
                "front_n": {"name": "前N张数量", "arg": "-fn", "default": "3", "type": int},
                "back_n": {"name": "后N张数量", "arg": "-bn", "default": "5", "type": int},
                "c": {"name": "从剪贴板读取", "arg": "-c", "is_flag": True},
                "dfm": {"name": "重复过滤模式", "arg": "--duplicate-filter-mode", "default": "quality", "type": str}
            }
        },
        'tui_config': {
            'checkbox_options': [
                ("从剪贴板读取", "clipboard", "-c"),
            ],
            'input_options': [
                ("汉明距离阈值", "hamming_threshold", "-ht", "16", "输入数字(默认16)"),
                ("前N张数量", "front_n", "-fn", "3", "输入数字(默认3)"),
                ("后N张数量", "back_n", "-bn", "5", "输入数字(默认5)"),
                ("解压范围", "extract_range", "-er", "0:3", "格式: start:end"),
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
                        "back_n": "0",
                        "duplicate_filter_mode": "watermark"
                    }
                },
                "去汉化模式": {
                    "description": "处理前后N张图片并使用哈希去重",
                    "checkbox_options": ["clipboard"],
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

def load_processed_files(paths_file: str) -> Set[str]:
    """
    从路径文件加载已处理的目录记录
    
    Args:
        paths_file: 路径文件
        
    Returns:
        Set[str]: 已处理目录路径的集合
    """
    processed_dirs = set()
    try:
        if not os.path.exists(paths_file):
            logger.warning(f"[#sys_log]路径文件不存在: {paths_file}")
            return processed_dirs
            
        with open(paths_file, 'r', encoding='utf-8') as f:
            processed_dirs = {line.strip() for line in f if line.strip()}
            
        logger.info(f"[#sys_log]从文件加载了 {len(processed_dirs)} 个已处理目录记录")
        return processed_dirs
        
    except Exception as e:
        logger.error(f"[#sys_log]加载处理记录失败: {e}")
        return set() 
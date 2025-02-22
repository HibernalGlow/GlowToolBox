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

logger = logging.getLogger(__name__)

config = {
    'script_name': 'recruit_cover_filter',
    'console_enabled': False,
}
logger, config_info = setup_logger(config)

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

def initialize_textual_logger():
    """初始化日志布局"""
    try:
        TextualLoggerManager.set_layout(TEXTUAL_LAYOUT, config_info['log_file'])
        logger.info("[#update_log]✅ 日志系统初始化完成")
    except Exception as e:
        print(f"❌ 日志系统初始化失败: {e}")

class ExtractMode:
    """解压模式类"""
    ALL = "all"  # 全部解压
    FIRST_N = "first_n"  # 解压前N张
    LAST_N = "last_n"  # 解压后N张
    RANGE = "range"  # 解压指定范围
    
    @staticmethod
    def get_selected_indices(mode: str, total_files: int, params: dict) -> Set[int]:
        """根据解压模式获取选中的文件索引"""
        if mode == ExtractMode.ALL:
            return set(range(total_files))
            
        elif mode == ExtractMode.FIRST_N:
            n = min(params.get('n', 1), total_files)
            return set(range(n))
            
        elif mode == ExtractMode.LAST_N:
            n = min(params.get('n', 1), total_files)
            return set(range(total_files - n, total_files))
            
        elif mode == ExtractMode.RANGE:
            range_str = params.get('range_str', '')
            try:
                start, end = map(int, range_str.split(':'))
                start = max(0, start)
                end = min(total_files, end)
                return set(range(start, end))
            except:
                return set()
                
        return set()

class RecruitCoverFilter:
    """封面图片过滤器"""
    
    def __init__(self, hash_file: str = None, cover_count: int = 3, hamming_threshold: int = 12):
        """初始化过滤器"""
        self.image_filter = ImageFilter(hash_file, cover_count, hamming_threshold)
        
    def process_archive(self, zip_path: str, extract_mode: str = ExtractMode.ALL, extract_params: dict = None) -> bool:
        """处理单个压缩包"""
        logger.info(f"[#file_ops]开始处理压缩包: {zip_path}")
        
        # 列出压缩包内容
        files = ArchiveHandler.list_archive_contents(zip_path)
        if not files:
            logger.info("[#file_ops]未找到图片文件")
            return False
            
        # 获取要解压的文件索引
        extract_params = extract_params or {}
        selected_indices = ExtractMode.get_selected_indices(extract_mode, len(files), extract_params)
        if not selected_indices:
            logger.error("[#file_ops]未选择任何文件进行解压")
            return False
            
        # 解压选定文件
        selected_files = [files[i] for i in selected_indices]
        success, temp_dir = ArchiveHandler.extract_files(zip_path, selected_files)
        if not success:
            return False
            
        try:
            # 获取解压后的图片文件
            image_files = []
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                        image_files.append(os.path.join(root, file))
                        
            # 处理图片
            to_delete, removal_reasons = self.image_filter.process_images(image_files)
            
            if not to_delete:
                logger.info("[#file_ops]没有需要删除的图片")
                shutil.rmtree(temp_dir)
                return False
                
            # 备份要删除的文件
            backup_results = BackupHandler.backup_removed_files(zip_path, to_delete, removal_reasons)
            
            # 删除标记的文件
            delete_results = BackupHandler.remove_files(to_delete)
            
            # 创建新的压缩包
            new_zip = zip_path + '.new'
            if not ArchiveHandler.create_archive(new_zip, temp_dir, delete_source=True):
                return False
                
            # 替换原有压缩包
            if not ArchiveHandler.replace_archive(zip_path, new_zip):
                return False
                
            logger.info(f"[#file_ops]成功处理压缩包: {zip_path}")
            return True
            
        except Exception as e:
            logger.error(f"[#file_ops]处理压缩包失败 {zip_path}: {e}")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return False

class InputHandler:
    """输入处理类"""
    
    @staticmethod
    def normalize_path(path: str) -> str:
        """规范化路径，处理引号和转义字符"""
        path = path.strip('"\'')
        path = path.replace('\\\\', '\\')
        return path

    @staticmethod
    def get_input_paths(args):
        """获取输入路径"""
        paths = []
        
        # 从命令行参数获取路径
        if args.path:
            paths.extend([InputHandler.normalize_path(p) for p in args.path])
            
        # 从剪贴板获取路径
        if args.clipboard or not paths:
            try:
                clipboard_content = pyperclip.paste()
                if clipboard_content:
                    clipboard_paths = [
                        InputHandler.normalize_path(p.strip())
                        for p in clipboard_content.splitlines()
                        if p.strip()
                    ]
                    paths.extend(clipboard_paths)
                    logger.info(f"[#file_ops]从剪贴板读取了 {len(clipboard_paths)} 个路径")
            except Exception as e:
                logger.error(f"[#update_log]从剪贴板读取失败: {e}")
                
        # 如果仍然没有路径，提示用户输入
        if not paths:
            print("请输入要处理的文件夹或压缩包路径（每行一个，输入空行结束）：")
            while True:
                line = input().strip()
                if not line:
                    break
                paths.append(InputHandler.normalize_path(line))
                
        initialize_textual_logger()
        
        # 验证路径是否存在
        valid_paths = []
        for p in paths:
            if os.path.exists(p):
                valid_paths.append(p)
            else:
                logger.warning(f"[#file_ops]路径不存在: {p}")
                
        return valid_paths

class Application:
    """应用程序类"""
    
    def process_directory(self, directory: str, filter_instance: RecruitCoverFilter):
        """处理目录"""
        try:
            if os.path.isfile(directory):
                if directory.lower().endswith('.zip'):
                    filter_instance.process_archive(directory)
            else:
                for root, _, files in os.walk(directory):
                    for file in files:
                        if file.lower().endswith('.zip'):
                            zip_path = os.path.join(root, file)
                            filter_instance.process_archive(zip_path)
        except Exception as e:
            logger.error(f"[#update_log]处理目录失败 {directory}: {e}")

def setup_cli_parser():
    """设置命令行参数解析器"""
    parser = argparse.ArgumentParser(description='招募封面图片过滤工具')
    parser.add_argument('--hash-file', '-hf', type=str,
                      help='哈希文件路径（可选，默认使用全局配置）')
    parser.add_argument('--cover-count', '-cc', type=int, default=3,
                      help='处理的封面图片数量 (默认: 3)')
    parser.add_argument('--hamming-threshold', '-ht', type=int, default=12,
                      help='汉明距离阈值 (默认: 12)')
    parser.add_argument('--clipboard', '-c', action='store_true',
                      help='从剪贴板读取路径')
    parser.add_argument('--extract-mode', '-em', type=str, 
                      choices=[ExtractMode.ALL, ExtractMode.FIRST_N, ExtractMode.LAST_N, ExtractMode.RANGE],
                      default=ExtractMode.ALL, help='解压模式 (默认: all)')
    parser.add_argument('--extract-n', '-en', type=int,
                      help='解压数量 (用于 first_n 和 last_n 模式)')
    parser.add_argument('--extract-range', '-er', type=str,
                      help='解压范围 (用于 range 模式，格式: start:end)')
    parser.add_argument('path', nargs='*', help='要处理的文件或目录路径')
    return parser

def run_application(args):
    """运行应用程序"""
    try:
        paths = InputHandler.get_input_paths(args)
        
        if not paths:
            logger.error("[#update_log]未提供任何有效路径")
            return False
            
        filter_instance = RecruitCoverFilter(
            hash_file=args.hash_file,
            cover_count=args.cover_count,
            hamming_threshold=args.hamming_threshold
        )
        
        # 准备解压参数
        extract_params = {}
        if args.extract_mode in [ExtractMode.FIRST_N, ExtractMode.LAST_N]:
            extract_params['n'] = args.extract_n
        elif args.extract_mode == ExtractMode.RANGE:
            extract_params['range_str'] = args.extract_range
            
        app = Application()
        for path in paths:
            app.process_directory(path, filter_instance)
            
        logger.info("[#update_log]处理完成")
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
                    "base_args": ["-cc", "-ht"],
                    "default_params": {
                        "cc": "3",
                        "ht": "12"
                    }
                },
                "2": {
                    "name": "前N张模式",
                    "base_args": ["-cc", "-ht", "-em", "first_n", "-en"],
                    "default_params": {
                        "cc": "3",
                        "ht": "12",
                        "en": "3"
                    }
                },
                "3": {
                    "name": "后N张模式",
                    "base_args": ["-cc", "-ht", "-em", "last_n", "-en"],
                    "default_params": {
                        "cc": "3",
                        "ht": "12",
                        "en": "3"
                    }
                },
                "4": {
                    "name": "范围模式",
                    "base_args": ["-cc", "-ht", "-em", "range", "-er"],
                    "default_params": {
                        "cc": "3",
                        "ht": "12",
                        "er": "0:3"
                    }
                }
            },
            'param_options': {
                "cc": {"name": "处理图片数量", "arg": "-cc", "default": "3", "type": int},
                "ht": {"name": "汉明距离阈值", "arg": "-ht", "default": "12", "type": int},
                "en": {"name": "解压数量", "arg": "-en", "default": "3", "type": int},
                "er": {"name": "解压范围", "arg": "-er", "default": "0:3", "type": str},
                "c": {"name": "从剪贴板读取", "arg": "-c", "is_flag": True}
            }
        },
        'tui_config': {
            'checkbox_options': [
                ("从剪贴板读取", "clipboard", "-c"),
            ],
            'input_options': [
                ("处理图片数量", "cover_count", "-cc", "3", "输入数字(默认3)"),
                ("汉明距离阈值", "hamming_threshold", "-ht", "12", "输入数字(默认12)"),
                ("解压数量", "extract_n", "-en", "3", "输入数字(默认3)"),
                ("解压范围", "extract_range", "-er", "0:3", "格式: start:end"),
                ("哈希文件路径", "hash_file", "-hf", "", "输入哈希文件路径(可选)"),
            ],
            'preset_configs': {
                "去水印模式": {
                    "description": "仅处理水印和重复",
                    "checkbox_options": ["clipboard"],
                    "input_values": {
                        "cover_count": "3",
                        "hamming_threshold": "12"
                    }
                },
                "前N张模式": {
                    "description": "处理前N张图片",
                    "checkbox_options": ["clipboard"],
                    "input_values": {
                        "cover_count": "3",
                        "hamming_threshold": "12",
                        "extract_n": "3"
                    },
                    "extra_args": ["-em", "first_n"]
                },
                "后N张模式": {
                    "description": "处理后N张图片",
                    "checkbox_options": ["clipboard"],
                    "input_values": {
                        "cover_count": "3",
                        "hamming_threshold": "12",
                        "extract_n": "3"
                    },
                    "extra_args": ["-em", "last_n"]
                },
                "范围模式": {
                    "description": "处理指定范围的图片",
                    "checkbox_options": ["clipboard"],
                    "input_values": {
                        "cover_count": "3",
                        "hamming_threshold": "12",
                        "extract_range": "0:3"
                    },
                    "extra_args": ["-em", "range"]
                }
            }
        }
    }

if __name__ == '__main__':
    mode_manager = create_mode_manager(
        config=get_mode_config(),
        cli_parser_setup=setup_cli_parser,
        application_runner=run_application
    )
    
    if len(sys.argv) > 1:
        success = mode_manager.run_cli()
    else:
        success = mode_manager.run_tui()
    
    if not success:
        sys.exit(1) 
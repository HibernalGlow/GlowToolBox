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

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from nodes.pics.calculate_hash_custom import ImageHashCalculator, PathURIGenerator
from nodes.pics.watermark_detector import WatermarkDetector

logger = logging.getLogger(__name__)

config = {
    'script_name': 'recruit_cover_filter',
    'console_enabled': False,
    'default_hash_file': os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                     'data', 'image_hashes.json')
}
logger, config_info = setup_logger(config)

# 初始化 TextualLoggerManager
HAS_TUI = True
USE_DEBUGGER = True

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
        """
        根据解压模式获取选中的文件索引
        
        Args:
            mode: 解压模式
            total_files: 总文件数
            params: 参数字典，包含 n 或 range_str
            
        Returns:
            Set[int]: 选中的文件索引集合
        """
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
        """
        初始化过滤器
        
        Args:
            hash_file: 哈希文件路径，如果为None则使用默认路径
            cover_count: 处理的封面图片数量
            hamming_threshold: 汉明距离阈值
        """
        self.hash_file = hash_file or config['default_hash_file']
        self.cover_count = cover_count
        self.hamming_threshold = hamming_threshold
        self.hash_cache = self._load_hash_file()
        self.watermark_detector = WatermarkDetector()
        
    def _load_hash_file(self) -> Dict:
        """加载哈希文件"""
        try:
            if os.path.exists(self.hash_file):
                with open(self.hash_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"[#file_ops]成功加载哈希文件: {self.hash_file}")
                return data.get('hashes', {})  # 适配新的哈希文件格式
            else:
                logger.error(f"[#file_ops]哈希文件不存在: {self.hash_file}")
                return {}
        except Exception as e:
            logger.error(f"[#file_ops]加载哈希文件失败: {e}")
            return {}
            
    def _get_image_hash(self, image_path: str) -> str:
        """获取图片哈希值，优先从缓存读取"""
        image_uri = PathURIGenerator.generate(image_path)
        
        # 从缓存中查找
        if image_uri in self.hash_cache:
            hash_data = self.hash_cache[image_uri]
            return hash_data.get('hash') if isinstance(hash_data, dict) else hash_data
            
        # 计算新的哈希值
        try:
            hash_value = ImageHashCalculator.calculate_phash(image_path)
            if hash_value:
                self.hash_cache[image_uri] = {'hash': hash_value}
                return hash_value
        except Exception as e:
            logger.error(f"[#file_ops]计算图片哈希值失败 {image_path}: {e}")
            
        return None
        
    def _find_similar_images(self, image_files: List[str]) -> List[List[str]]:
        """查找相似的图片组"""
        similar_groups = []
        processed = set()
        
        for i, img1 in enumerate(image_files):
            if img1 in processed:
                continue
                
            hash1 = self._get_image_hash(img1)
            if not hash1:
                continue
                
            current_group = [img1]
            
            for j, img2 in enumerate(image_files[i+1:], i+1):
                if img2 in processed:
                    continue
                    
                hash2 = self._get_image_hash(img2)
                if not hash2:
                    continue
                    
                # 计算汉明距离
                distance = ImageHashCalculator.calculate_hamming_distance(hash1, hash2)
                if distance <= self.hamming_threshold:
                    current_group.append(img2)
                    logger.info(f"[#file_ops]找到相似图片: {os.path.basename(img2)} (距离: {distance})")
                    
            if len(current_group) > 1:
                similar_groups.append(current_group)
                processed.update(current_group)
                logger.info(f"[#file_ops]找到相似图片组: {len(current_group)}张")
                
        return similar_groups
        
    def process_images(self, image_files: List[str]) -> Tuple[Set[str], Dict[str, List[str]]]:
        """
        处理图片列表，返回要删除的图片和删除原因
        
        Args:
            image_files: 图片文件路径列表
            
        Returns:
            Tuple[Set[str], Dict[str, List[str]]]: (要删除的文件集合, 删除原因字典)
        """
        # 排序并只取前N张
        sorted_files = sorted(image_files)
        cover_files = sorted_files[:self.cover_count]
        
        if not cover_files:
            return set(), {}
            
        logger.info(f"[#file_ops]处理前{self.cover_count}张图片")
        
        # 查找相似图片组
        similar_groups = self._find_similar_images(cover_files)
        
        # 处理每组相似图片
        to_delete = set()
        removal_reasons = {}
        
        for group in similar_groups:
            # 检测每张图片的水印
            watermark_results = {}
            for img_path in group:
                has_watermark, texts = self.watermark_detector.detect_watermark(img_path)
                watermark_results[img_path] = (has_watermark, texts)
                logger.info(f"[#ocr_results]图片 {os.path.basename(img_path)} OCR结果: {texts}")
            
            # 找出无水印的图片
            clean_images = [img for img, (has_mark, _) in watermark_results.items() 
                          if not has_mark]
            
            if clean_images:
                # 如果有无水印版本，删除其他版本
                keep_image = clean_images[0]
                logger.info(f"[#file_ops]保留无水印图片: {os.path.basename(keep_image)}")
                for img in group:
                    if img != keep_image:
                        to_delete.add(img)
                        removal_reasons[img] = {
                            'reason': 'recruit_cover',
                            'watermark_texts': watermark_results[img][1]
                        }
                        logger.info(f"[#file_ops]标记删除有水印图片: {os.path.basename(img)}")
            else:
                # 如果都有水印，保留第一个
                keep_image = group[0]
                logger.info(f"[#file_ops]保留第一张图片: {os.path.basename(keep_image)}")
                for img in group[1:]:
                    to_delete.add(img)
                    removal_reasons[img] = {
                        'reason': 'recruit_cover',
                        'watermark_texts': watermark_results[img][1]
                    }
                    logger.info(f"[#file_ops]标记删除重复图片: {os.path.basename(img)}")
        
        return to_delete, removal_reasons

    def process_archive(self, zip_path: str, extract_mode: str = ExtractMode.ALL, extract_params: dict = None) -> bool:
        """处理单个压缩包"""
        temp_dir = None
        try:
            logger.info(f"[#file_ops]开始处理压缩包: {zip_path}")
            
            # 创建临时目录
            temp_dir = os.path.join(os.path.dirname(zip_path), f'temp_{int(time.time())}')
            os.makedirs(temp_dir, exist_ok=True)
            
            # 获取压缩包内容
            cmd = ['7z', 'l', '-slt', zip_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"[#file_ops]读取压缩包内容失败: {result.stderr}")
                return False
                
            # 解析文件列表
            files = []
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line.startswith('Path = '):
                    file_path = line[7:]
                    if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                        files.append(file_path)
                        
            if not files:
                logger.info("[#file_ops]未找到图片文件")
                shutil.rmtree(temp_dir)
                return False
                
            # 获取要解压的文件索引
            extract_params = extract_params or {}
            selected_indices = ExtractMode.get_selected_indices(extract_mode, len(files), extract_params)
            
            if not selected_indices:
                logger.error("[#file_ops]未选择任何文件进行解压")
                shutil.rmtree(temp_dir)
                return False
                
            # 创建文件列表
            list_file = os.path.join(temp_dir, '@files.txt')
            selected_files = [files[i] for i in selected_indices]
            with open(list_file, 'w', encoding='utf-8') as f:
                for file in selected_files:
                    f.write(file + '\n')
                    
            # 解压选定文件
            cmd = ['7z', 'x', zip_path, f'-o{temp_dir}', f'@{list_file}', '-y']
            result = subprocess.run(cmd, capture_output=True, text=True)
            os.remove(list_file)
            
            if result.returncode != 0:
                logger.error(f"[#file_ops]解压失败: {result.stderr}")
                shutil.rmtree(temp_dir)
                return False
                
            # 处理解压后的图片
            image_files = []
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                        image_files.append(os.path.join(root, file))
                        
            # 处理图片
            to_delete, removal_reasons = self.process_images(image_files)
            
            if not to_delete:
                logger.info("[#file_ops]没有需要删除的图片")
                shutil.rmtree(temp_dir)
                return False
                
            # 备份要删除的文件
            BackupHandler.backup_removed_files(zip_path, to_delete, removal_reasons)
            
            # 删除标记的文件
            for file_path in to_delete:
                try:
                    os.remove(file_path)
                    reason = removal_reasons[file_path]
                    logger.info(f"[#file_ops]删除文件: {os.path.basename(file_path)}")
                    logger.info(f"[#ocr_results]删除原因: {reason}")
                except Exception as e:
                    logger.error(f"[#file_ops]删除文件失败 {file_path}: {e}")
                    
            # 创建新的压缩包
            new_zip = zip_path + '.new'
            cmd = ['7z', 'a', new_zip, os.path.join(temp_dir, '*')]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"[#file_ops]创建新压缩包失败: {result.stderr}")
                shutil.rmtree(temp_dir)
                return False
                
            # 备份原文件并替换
            backup_path = zip_path + '.bak'
            shutil.copy2(zip_path, backup_path)
            os.replace(new_zip, zip_path)
            
            # 清理临时文件
            shutil.rmtree(temp_dir)
            
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
    def parse_arguments():
        """解析命令行参数"""
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
        return parser.parse_args()

    @staticmethod
    def normalize_path(path: str) -> str:
        """规范化路径，处理引号和转义字符"""
        # 移除首尾的引号
        path = path.strip('"\'')
        # 处理转义字符
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
        if args.clipboard or not paths:  # 如果没有命令行参数，也尝试从剪贴板读取
            try:
                clipboard_content = pyperclip.paste()
                if clipboard_content:
                    # 处理剪贴板内容，支持多行路径
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
                
        # 验证路径是否存在
        valid_paths = []
        for p in paths:
            if os.path.exists(p):
                valid_paths.append(p)
            else:
                logger.warning(f"[#file_ops]路径不存在: {p}")
                
        return valid_paths

class BackupHandler:
    """处理备份和删除文件的类"""
    
    @staticmethod
    def backup_removed_files(zip_path: str, removed_files: Set[str], removal_reasons: Dict[str, Dict]):
        """
        将删除的文件备份到trash文件夹中，按删除原因分类
        
        Args:
            zip_path: 原始压缩包路径
            removed_files: 被删除的文件集合
            removal_reasons: 文件删除原因的字典
        """
        try:
            if not removed_files:
                return
                
            zip_name = os.path.splitext(os.path.basename(zip_path))[0]
            trash_dir = os.path.join(os.path.dirname(zip_path), f'{zip_name}.trash')
            
            # 按删除原因分类
            for file_path in removed_files:
                try:
                    reason = removal_reasons.get(file_path, {}).get('reason', 'unknown')
                    subdir = os.path.join(trash_dir, reason)
                    os.makedirs(subdir, exist_ok=True)
                    
                    # 复制文件到对应子目录
                    dest_path = os.path.join(subdir, os.path.basename(file_path))
                    shutil.copy2(file_path, dest_path)
                    logger.info(f"[#file_ops]已备份到 {reason}: {os.path.basename(file_path)}")
                    
                except Exception as e:
                    logger.error(f"[#file_ops]备份文件失败 {file_path}: {e}")
                    continue
                    
            logger.info(f"[#file_ops]已备份删除的文件到: {trash_dir}")
            
        except Exception as e:
            logger.error(f"[#file_ops]备份删除文件时出错: {e}")

class DebuggerHandler:
    """调试模式处理类"""
    
    LAST_CONFIG_FILE = "recruit_cover_filter_last_debug_config.json"
    
    @staticmethod
    def save_last_config(mode_choice, final_args):
        """保存最后一次使用的配置"""
        try:
            config = {
                "mode": mode_choice,
                "args": final_args
            }
            with open(DebuggerHandler.LAST_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[#update_log]保存配置失败: {e}")

    @staticmethod
    def load_last_config():
        """加载上次使用的配置"""
        try:
            if os.path.exists(DebuggerHandler.LAST_CONFIG_FILE):
                with open(DebuggerHandler.LAST_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"[#update_log]加载配置失败: {e}")
        return None

    @staticmethod
    def get_debugger_options():
        """交互式调试模式菜单"""
        # 基础模式选项
        base_modes = {
            "1": {
                "name": "去水印模式",
                "base_args": ["-cc", "-ht"],
                "default_params": {
                    "cc": "3",  # cover_count
                    "ht": "12"  # hamming_threshold
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
        }
        
        # 可配置参数选项
        param_options = {
            "cc": {"name": "处理图片数量", "arg": "-cc", "default": "3", "type": int},
            "ht": {"name": "汉明距离阈值", "arg": "-ht", "default": "12", "type": int},
            "en": {"name": "解压数量", "arg": "-en", "default": "3", "type": int},
            "er": {"name": "解压范围", "arg": "-er", "default": "0:3", "type": str},
            "c": {"name": "从剪贴板读取", "arg": "-c", "is_flag": True}
        }

        # 加载上次配置
        last_config = DebuggerHandler.load_last_config()
        
        while True:
            print("\n=== 调试模式选项 ===")
            print("\n基础模式:")
            for key, mode in base_modes.items():
                print(f"{key}. {mode['name']}")
            
            if last_config:
                print("\n上次配置:")
                print(f"模式: {base_modes[last_config['mode']]['name']}")
                print("参数:", " ".join(last_config['args']))
                print("\n选项:")
                print("L. 使用上次配置")
                print("N. 使用新配置")
                choice = input("\n请选择 (L/N 或直接选择模式 1-4): ").strip().upper()
                
                if choice == 'L':
                    return last_config['args']
                elif choice == 'N':
                    pass
                elif not choice:
                    return []
                elif choice in base_modes:
                    mode_choice = choice
                else:
                    print("❌ 无效的选择，请重试")
                    continue
            else:
                mode_choice = input("\n请选择基础模式(1-4): ").strip()
                if not mode_choice:
                    return []
                if mode_choice not in base_modes:
                    print("❌ 无效的模式选择，请重试")
                    continue
            
            selected_mode = base_modes[mode_choice]
            final_args = []
            
            # 添加基础参数和默认值
            for arg in selected_mode["base_args"]:
                if arg.startswith('-'):
                    param_key = arg.lstrip('-').replace('-', '_')
                    if param_key in selected_mode.get("default_params", {}):
                        final_args.extend([arg, selected_mode["default_params"][param_key]])
                    else:
                        final_args.append(arg)
                else:
                    final_args.append(arg)
            
            # 显示当前配置
            print("\n当前配置:")
            for i in range(0, len(final_args), 2):
                if i + 1 < len(final_args):
                    print(f"  {final_args[i]} = {final_args[i+1]}")
                else:
                    print(f"  {final_args[i]}")
            
            # 询问是否需要修改参数
            while True:
                print("\n可选操作:")
                print("1. 修改参数")
                print("2. 添加参数")
                print("3. 开始执行")
                print("4. 重新选择模式")
                print("0. 退出程序")
                
                op_choice = input("\n请选择操作(0-4): ").strip()
                
                if op_choice == "0":
                    return []
                elif op_choice == "1":
                    # 显示当前所有参数
                    print("\n当前参数:")
                    for i in range(0, len(final_args), 2):
                        if i + 1 < len(final_args):
                            print(f"{i//2 + 1}. {final_args[i]} = {final_args[i+1]}")
                        else:
                            print(f"{i//2 + 1}. {final_args[i]}")
                            
                    param_idx = input("请选择要修改的参数序号: ").strip()
                    try:
                        idx = (int(param_idx) - 1) * 2
                        if 0 <= idx < len(final_args):
                            new_value = input(f"请输入新的值: ").strip()
                            if idx + 1 < len(final_args):
                                final_args[idx + 1] = new_value
                    except ValueError:
                        print("❌ 无效的输入")
                        
                elif op_choice == "2":
                    # 显示可添加的参数
                    print("\n可添加的参数:")
                    for key, param in param_options.items():
                        if param.get("is_flag"):
                            print(f"  {key}. {param['name']} (开关参数)")
                        else:
                            print(f"  {key}. {param['name']} (默认值: {param['default']})")
                    
                    param_key = input("请输入要添加的参数代号: ").strip()
                    if param_key in param_options:
                        param = param_options[param_key]
                        if param.get("is_flag"):
                            if param["arg"] not in final_args:
                                final_args.append(param["arg"])
                        else:
                            value = input(f"请输入{param['name']}的值 (默认: {param['default']}): ").strip() or param['default']
                            if param["arg"] not in final_args:
                                final_args.extend([param["arg"], value])
                            
                elif op_choice == "3":
                    print("\n最终参数:", " ".join(final_args))
                    DebuggerHandler.save_last_config(mode_choice, final_args)
                    return final_args
                elif op_choice == "4":
                    break
                else:
                    print("❌ 无效的选择")
            
        return []

class ModeManager:
    """模式管理器，统一管理不同的运行模式"""
    
    def __init__(self, config: dict = None):
        """
        初始化模式管理器
        
        Args:
            config: 配置字典，包含:
                - use_debugger: 是否启用调试模式
                - use_tui: 是否启用TUI模式
                - debug_config: 调试模式配置
                - tui_config: TUI模式配置
                - cli_config: 命令行模式配置
        """
        self.config = config or {
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
                            "extract_n": "3",
                            "extract_mode": "first_n"
                        }
                    },
                    "后N张模式": {
                        "description": "处理后N张图片",
                        "checkbox_options": ["clipboard"],
                        "input_values": {
                            "cover_count": "3",
                            "hamming_threshold": "12",
                            "extract_n": "3",
                            "extract_mode": "last_n"
                        }
                    },
                    "范围模式": {
                        "description": "处理指定范围的图片",
                        "checkbox_options": ["clipboard"],
                        "input_values": {
                            "cover_count": "3",
                            "hamming_threshold": "12",
                            "extract_range": "0:3",
                            "extract_mode": "range"
                        }
                    }
                }
            }
        }
        
    def _setup_cli_parser(self):
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
        
    def _run_tui_mode(self):
        """运行TUI模式"""
        def on_run(params: dict):
            """TUI回调函数"""
            args = []
            
            # 添加选中的选项
            for arg, enabled in params['options'].items():
                if enabled:
                    args.append(arg)
            
            # 添加输入值
            for arg, value in params['inputs'].items():
                if value:
                    args.extend([arg, value])
            
            # 如果选择了预设，添加对应的extract_mode
            if params.get('preset'):
                preset_name = params['preset']
                if preset_name == "前N张模式":
                    args.extend(['-em', 'first_n'])
                elif preset_name == "后N张模式":
                    args.extend(['-em', 'last_n'])
                elif preset_name == "范围模式":
                    args.extend(['-em', 'range'])
            
            # 运行命令行模式
            return self._run_cli_mode(args)
        
        # 创建TUI应用
        app = create_config_app(
            program=sys.argv[0],
            checkbox_options=self.config['tui_config']['checkbox_options'],
            input_options=self.config['tui_config']['input_options'],
            title="招募封面图片过滤工具",
            preset_configs=self.config['tui_config']['preset_configs'],
            on_run=on_run
        )
        
        # 运行TUI应用
        app.run()
        return True
        
    def _run_debug_mode(self):
        """运行调试模式"""
        debugger = DebuggerHandler()
        debugger.base_modes = self.config['debug_config']['base_modes']
        
        selected_options = debugger.get_debugger_options()
        if selected_options:
            return self._run_cli_mode(selected_options)
        return False
        
    def _run_cli_mode(self, cli_args=None):
        """运行命令行模式"""
        parser = self._setup_cli_parser()
        args = parser.parse_args(cli_args)
        return self._run_application(args)
        
    def _run_application(self, args):
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
            
    def run(self, cli_args=None):
        """
        运行程序
        
        Args:
            cli_args: 命令行参数列表，如果为None则从sys.argv获取
            
        Returns:
            bool: 是否成功执行
        """
        try:
            # 根据不同模式运行
            if cli_args:
                return self._run_cli_mode(cli_args)
            elif self.config['use_tui']:
                return self._run_tui_mode()
            elif self.config['use_debugger']:
                return self._run_debug_mode()
            else:
                return self._run_cli_mode()
                
        except Exception as e:
            logger.error(f"[#update_log]运行失败: {e}")
            return False

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
            'last_config_file': 'recruit_cover_filter_last_debug_config.json'
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
    # 创建模式管理器
    mode_manager = create_mode_manager(
        config=get_mode_config(),
        cli_parser_setup=setup_cli_parser,
        application_runner=run_application
    )
    
    # 根据参数选择运行模式
    if len(sys.argv) > 1:
        # 有命令行参数时运行命令行模式
        success = mode_manager.run_cli()
    else:
        # 无参数时运行TUI模式
        success = mode_manager.run_tui()
    
    if not success:
        sys.exit(1) 
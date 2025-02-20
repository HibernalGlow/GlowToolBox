import argparse
import os
import pyperclip
import logging
from ..config.settings import Settings
from ..utils.path_utils import PathUtils

class InputHandler:
    """输入处理类"""
    @staticmethod
    def parse_arguments(args=None):
        parser = argparse.ArgumentParser(description='图片压缩包去重工具')
        # 添加排除路径参数
        parser.add_argument('--exclude-paths', '-ep',
                          nargs='*',
                          default=[],
                          help='要排除的路径关键词列表')
        feature_group = parser.add_argument_group('功能开关')
        feature_group.add_argument('--remove-small', '-rs', action='store_true', help='启用小图过滤')
        feature_group.add_argument('--remove-grayscale', '-rg', action='store_true', help='启用黑白图过滤')
        feature_group.add_argument('--remove-duplicates', '-rd', action='store_true', help='启用重复图片过滤')
        feature_group.add_argument('--merge-archives', '-ma', action='store_true', help='合并同一文件夹下的多个压缩包进行处理')
        feature_group.add_argument('--no-trash', '-nt', action='store_true', help='不保留trash文件夹，直接删除到回收站')
        feature_group.add_argument('--hash-file', '-hf', type=str, help='指定哈希文件路径,用于跨压缩包去重')
        feature_group.add_argument('--self-redup', '-sr', action='store_true', help='启用自身去重复(当使用哈希文件时默认不启用)')
        feature_group.add_argument('path', nargs='*', help='要处理的文件或目录路径')
        small_group = parser.add_argument_group('小图过滤参数')
        small_group.add_argument('--min-size', '-ms', type=int, default=631, help='最小图片尺寸（宽度和高度），默认为631')
        duplicate_group = parser.add_argument_group('重复图片过滤参数')
        duplicate_group.add_argument('--hamming_distance', '-hd', type=int, default=0, help='内部去重的汉明距离阈值，数值越大判定越宽松，默认为2')
        duplicate_group.add_argument('--ref_hamming_distance', '-rhd', type=int, default=12, help='与外部参考文件比较的汉明距离阈值，默认为12')
        
        parser.add_argument('--clipboard', '-c', action='store_true', help='从剪贴板读取路径')
        parser.add_argument('--bak-mode', '-bm', choices=['recycle', 'delete', 'keep'], default='keep', help='bak文件处理模式：recycle=移到回收站（默认），delete=直接删除，keep=保留')
        parser.add_argument('--max-workers', '-mw', type=int, default=4, help='最大线程数，默认为4')

        return parser.parse_args(args)  # 添加参数传递


    @staticmethod
    def prepare_params(args):
        """
        统一准备参数字典
        
        Args:
            args: 命令行参数对象
            
        Returns:
            dict: 包含所有处理参数的字典
        """
        return {
            'min_size': args.min_size,
            'hamming_distance': args.hamming_distance,  # 这里使用连字符形式的参数名
            'ref_hamming_distance': args.ref_hamming_distance,  # 这里使用连字符形式的参数名
            'filter_height_enabled': args.remove_small,
            'remove_grayscale': args.remove_grayscale,
            'ignore_processed_log': Settings.ignore_processed_log,
            'add_processed_log_enabled': Settings.add_processed_log_enabled,
            'max_workers': args.max_workers,
            'bak_mode': args.bak_mode,
            'remove_duplicates': args.remove_duplicates,
            'hash_file': args.hash_file,
            'self_redup': args.self_redup,
            'exclude_paths': args.exclude_paths if args.exclude_paths else []
        }

    @staticmethod
    def get_input_paths(args):
        """获取输入路径"""
        directories = []
        
        # 首先检查命令行参数中的路径
        if args.path:
            directories.extend(args.path)
            
        # 如果没有路径且启用了剪贴板，则从剪贴板读取
        if not directories and args.clipboard:
            directories = InputHandler.get_paths_from_clipboard()
            
        # 如果仍然没有路径，则使用Rich Logger的输入功能
        if not directories:
            try:
                print("请输入要处理的文件夹或压缩包路径（每行一个，输入空行结束）：")
                while True:
                    line = input().strip()
                    if not line:
                        break
                    path = line.strip().strip('"').strip("'")
                    if os.path.exists(path):
                        directories.append(path)
                        # print(f"✅ 已添加有效路径: {path}")
                    else:
                        print(f"❌ 路径不存在: {path}")
                
            except Exception as e:
                print(f"获取路径失败: {e}")
                
        return directories

    @staticmethod
    def get_paths_from_clipboard():
        """从剪贴板读取多行路径"""
        try:
            clipboard_content = pyperclip.paste()
            if not clipboard_content:
                return []
            paths = [path.strip().strip('"') for path in clipboard_content.splitlines() if path.strip()]
            valid_paths = [path for path in paths if os.path.exists(path)]
            if valid_paths:
                logging.info( f'从剪贴板读取到 {len(valid_paths)} 个有效路径')
            else:
                logging.info( '剪贴板中没有有效路径')
            return valid_paths
        except ImportError:
            logging.info( '未安装 pyperclip 模块，无法读取剪贴板')
            return []
        except Exception as e:
            logging.info( f'读取剪贴板时出错: {e}')
            return []

    @staticmethod
    def validate_args(args):
        """验证参数是否有效"""
        if not any([args.remove_small, args.remove_grayscale, args.remove_duplicates]):
            logging.info( '警告: 未启用任何过滤功能，将不会对图片进行处理')
        return True


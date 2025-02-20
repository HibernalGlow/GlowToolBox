import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.handler.input_handler import InputHandler
from src.core.process_manager import ProcessManager
from src.config.settings import Settings
import logging
from tui.config import create_config_app

class Application:
    """
    类描述
    """
    def main(self):
        """主函数"""
        try:
            # 添加父目录到Python路径
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            
            # 检查是否有命令行参数
            if len(sys.argv) > 1:
                # 命令行模式处理
                args = InputHandler.parse_arguments()
                if not InputHandler.validate_args(args):
                    sys.exit(1)
                self._process_with_args(args)
                return

            # TUI模式处理
            if not Settings.HAS_TUI:
                print("无法导入TUI配置模块,将使用命令行模式")
                args = InputHandler.parse_arguments()
                if not InputHandler.validate_args(args):
                    sys.exit(1)
                self._process_with_args(args)
                return

            # 创建配置选项和预设
            checkbox_options, input_options, preset_configs = self._create_ui_config()

            # 创建配置界面
            app = create_config_app(
                program=os.path.abspath(__file__),
                checkbox_options=checkbox_options,
                input_options=input_options,
                title="图片压缩包去重工具",
                preset_configs=preset_configs,
                on_run=False  # 新增回调函数
            )
            
            # 运行配置界面
            app.run()

        except Exception as e:
            logging.error(f"❌ 处理过程中发生错误: {e}")
            print(f"错误信息: {e}")
            sys.exit(1)

    def _process_with_args(self, args):
        """统一处理参数执行"""
        directories = InputHandler.get_input_paths(args)
        if not directories:
            print('未提供任何输入路径')
            return
        # initialize_logger()
        ProcessManager.print_config(args, ProcessManager.get_max_workers())
        if args.remove_duplicates:
            
            global global_hashes
        if args.merge_archives:
            ProcessManager.process_merged_archives(directories, args)
        else:
            ProcessManager.process_normal_archives(directories, args)

    def _handle_tui_run(self, params: dict):
        """TUI模式回调处理"""
        # 转换参数为命令行格式
        args_list = []
        
        # 添加选项参数
        for arg, enabled in params['options'].items():
            if enabled:
                args_list.append(arg)
        
        # 添加输入参数
        for arg, value in params['inputs'].items():
            if value:  # 只添加有值的参数
                args_list.extend([arg, value])
        
        # 添加路径参数
        if params.get('paths'):
            args_list.extend(params['paths'])
        
        # 解析参数
        args = InputHandler.parse_arguments(args_list)
        if not InputHandler.validate_args(args):
            sys.exit(1)
        
        # 统一执行处理
        self._process_with_args(args)

    def _create_ui_config(self):
        """创建TUI配置选项和预设"""
        checkbox_options = [
            ("小图过滤", "remove_small", "--remove-small"),
            ("黑白图过滤", "remove_grayscale", "--remove-grayscale"), 
            ("重复图片过滤", "remove_duplicates", "--remove-duplicates"),
            ("合并压缩包处理", "merge_archives", "--merge-archives"),
            ("自身去重复", "self_redup", "--self-redup"),
        ]

        input_options = [
            ("最小图片尺寸", "min_size", "--min-size", "631", "输入数字(默认631)"),
            ("汉明距离", "hamming_distance", "--hamming_distance", "12", "输入汉明距离的数字"),
            ("内部去重的汉明距离阈值", "ref_hamming_distance", "--ref-hamming_distance", "12", "输入内部去重的汉明距离阈值"),
            ("哈希文件路径", "hash_file", "--hash-file", "", "输入哈希文件路径(可选)"),
        ]

        preset_configs = {
            "去小图模式": {
                "description": "仅去除小尺寸图片",
                "checkbox_options": ["remove_small",  "clipboard"],
                "input_values": {
                    "min_size": "631"
                }
            },
            "去重复模式": {
                "description": "仅去除重复图片",
                "checkbox_options": ["remove_duplicates", "clipboard"],
                "input_values": {
                    "hamming_distance": "12"
                }
            },
            "去黑白模式": {
                "description": "仅去除黑白/白图",
                "checkbox_options": ["remove_grayscale", "clipboard"],
            },
            "合并处理模式": {
                "description": "合并压缩包处理(去重+去小图+去黑白)",
                "checkbox_options": ["merge_archives", "remove_small", "remove_duplicates", "remove_grayscale", "clipboard"],
                "input_values": {
                    "min_size": "631",
                    "hamming_distance": "12"

                }
            }
        }

        return checkbox_options, input_options, preset_configs


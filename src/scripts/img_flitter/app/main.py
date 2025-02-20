import sys
import os
from core.archive_processor import ArchiveProcessor
from config.settings import Settings
from services.logging_service import LoggingService
from utils.path_utils import PathUtils
import logging
from handler.input_handler import InputHandler
from core.process_manager import ProcessManager
from config.settings import Settings
from handler.debugger_handler import DebuggerHandler
from core import Application

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # 获取到comic_img_flitter目录
sys.path.insert(0, _PROJECT_ROOT)

def main():
    """主入口函数"""
    settings = Settings()
    LoggingService.initialize()
    processor = ArchiveProcessor(settings)
    processor.process()
    if Settings.USE_DEBUGGER:
        selected_options = DebuggerHandler.get_debugger_options()
        if selected_options:
            # 移除多余的--no-tui参数
            args = InputHandler.parse_arguments(selected_options)  # 删除+ ['--no-tui']
            Application()._process_with_args(args)
        else:
            print("未选择任何功能，程序退出。")
            sys.exit(0)
    else:
        Application().main()
if __name__ == "__main__":
    main() 
from src.core.archive_processor import ArchiveProcessor
from src.config.settings import Settings
from src.services.logging_service import LoggingService
from src.utils.path_utils import PathUtils
import logging
from src.handler.input_handler import InputHandler
from src.core.process_manager import ProcessManager
from src.config.settings import Settings
from src.handler.debugger_handler import DebuggerHandler
from src.core import Application
import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), '1ehv'))

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
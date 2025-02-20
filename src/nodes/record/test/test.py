from nodes.record.logger_config import setup_logger
import os
import logging
from nodes.tui.textual_logger import TextualLoggerManager
from nodes.tui.textual_preset import create_config_app


def demo_logger():
    """日志配置演示函数
    实际存储路径由以下顺序决定：
    1. 如果传入log_path参数则使用
    2. 否则使用.env中的LOG_PATH配置
    3. 最后使用默认的logs目录
    """
    test_config = {
        'script_name': 'logger_demo',
        'console_enabled': True,
        'formatter': '%(asctime)s - %(levelname)s - %(message)s'
    }
    
    # 初始化日志
    logger = setup_logger(test_config)
    
    # 生成测试日志（在DEBUG日志中显示实际路径）
    logger.debug(f"[#update_log] 日志存储路径：{os.path.abspath(logger.handlers[0].baseFilename)}")
    logger.info("[#update_log] 这是一条INFO级别日志")
    logger.warning("[#update_log] 这是一条WARNING级别日志")
    logger.error("[#update_log] 这是一条ERROR级别日志")

def tui_preset_test():
    """测试TUI配置界面的日志记录"""
    def run_callback(params):
        """配置完成后的回调函数"""
        # 初始化日志配置
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('tui_test.log'),
                logging.StreamHandler()
            ]
        )
        logging.info("配置参数: %s", params)
        logging.debug("测试DEBUG级别日志")
        logging.warning("测试WARNING级别日志")

    # 创建演示用配置界面
    checkbox_options = [
        ("测试选项1", "test1", "--test1"),
        ("测试选项2", "test2", "--test2")
    ]
    
    input_options = [
        ("输入参数", "input1", "--input", "", "请输入内容")
    ]

    app = create_config_app(
        program="demo.py",
        checkbox_options=checkbox_options,
        input_options=input_options,
        title="日志记录测试界面",
        # on_run=run_callback  # 使用回调函数
    )
    app.run()

if __name__ == "__main__":
    demo_logger()
    tui_preset_test()
    print("所有测试完成，请检查日志文件")
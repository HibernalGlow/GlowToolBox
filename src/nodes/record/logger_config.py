import logging
from datetime import datetime
from pathlib import Path
import os
import dotenv

# 定义工作目录
WORKING_DIR = r"D:\1VSCODE\GlowToolBox"

# 检查并切换工作目录
if Path.cwd() != Path(WORKING_DIR):
    try:
        os.chdir(WORKING_DIR)
        print(f"已切换到工作目录：{WORKING_DIR}")
    except Exception as e:
        print(f"目录切换失败：{e}")
        raise SystemExit("无法切换到指定工作目录，日志系统无法初始化")

dotenv.load_dotenv()
# 默认配置
DEFAULT_CONFIG = {
    # 基本配置
    'script_name': None,                         # 脚本名称
    'console_enabled': True,                     # 是否启用控制台输出
    
    # 路径和格式配置
    'log_path': os.getenv('LOG_PATH', 'logs'),  # 这里实现优先级
    'date_format': '%Y%m%d',                     # 日期格式
    'time_format': '%H',                         # 时间格式
    'file_format': '%M%S',                       # 文件名格式
    'encoding': 'utf-8',                         # 文件编码
    'formatter': '%(asctime)s - %(levelname)s - %(message)s',  # 修改后的格式
    
    # 日志级别配置
    'file_level': logging.DEBUG,                 # 文件日志级别
    'console_level': logging.INFO,               # 控制台日志级别
    
    # 第三方日志配置
    'disabled_loggers': {                        # 禁用的第三方日志
        'PIL': logging.WARNING,
        'urllib3': logging.WARNING,
        'fsspec': logging.WARNING,
        'PIL': logging.WARNING, 
        'urllib3': logging.WARNING,
        'requests': logging.WARNING,
        'chardet': logging.WARNING,
        'vipshome': logging.WARNING,
        'pyvips': logging.WARNING
    }
}

def setup_logger(config=None):
    """设置日志记录器
    
    Args:
        config: 配置字典，会覆盖默认配置
    
    Returns:
        tuple: (logging.Logger, str) - 配置好的日志记录器和日志文件路径
    """
    # 合并配置
    cfg = DEFAULT_CONFIG.copy()
    if config:
        cfg.update(config)
        
    # 检查必要参数
    if not cfg['script_name']:
        raise ValueError("必须提供script_name")

    # 获取logger实例
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # 清除所有已存在的handler
    logger.handlers.clear()

    # 确保日志目录存在
    os.makedirs(cfg['log_path'], exist_ok=True)

    # 创建日志目录（调整目录结构）
    current_time = datetime.now()
    log_dir = os.path.join(
        cfg['log_path'],
        cfg['script_name'],
        current_time.strftime(cfg['date_format']),
        current_time.strftime(cfg['time_format']),
    )
    os.makedirs(log_dir, exist_ok=True)

    # 创建文件处理器（添加文件模式参数）
    log_file = os.path.join(log_dir, f"{current_time.strftime(cfg['file_format'])}.log")
    file_handler = logging.FileHandler(log_file, encoding=cfg['encoding'])
    file_handler.setLevel(cfg['file_level'])
    
    # 设置格式器
    formatter = logging.Formatter(cfg['formatter'])
    file_handler.setFormatter(formatter)
    
    # 添加文件处理器
    logger.addHandler(file_handler)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)  # 确保控制台也使用配置的格式
    console_handler.setLevel(cfg['console_level'])
    if cfg['console_enabled']:
        logger.addHandler(console_handler)

    # 禁用第三方库的日志
    for logger_name, level in cfg['disabled_loggers'].items():
        logging.getLogger(logger_name).setLevel(level)

    return logger, log_file

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
    logger, log_file = setup_logger(test_config)
    
    # 生成测试日志（在DEBUG日志中显示实际路径）
    logger.debug(f"当前日志存储路径：{os.path.abspath(log_file)}")
    logger.info("这是一条INFO级别日志")
    logger.warning("这是一条WARNING级别日志")
    logger.error("这是一条ERROR级别日志")

if __name__ == "__main__":
    demo_logger()
    # 获取实际使用的日志路径
    used_path = os.getenv('LOG_PATH', 'logs')
    print(f"测试日志生成完成，请检查 {used_path}/logger_demo 目录")
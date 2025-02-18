import logging
from datetime import datetime
from pathlib import Path
import os

class LoggingService:
    """日志服务类"""
    
    _initialized = False
    _logger = None
    
    @classmethod
    def initialize(cls):
        """初始化日志系统"""
        if cls._initialized:
            return
            
        # 配置日志格式
        script_name = os.path.basename(__file__).replace('.py', '')
        logspath = r"D:/1VSCODE/1ehv/logs"
        LOG_BASE_DIR = Path(logspath + f"/{script_name}")
        DATE_STR = datetime.now().strftime("%Y%m%d")
        HOUR_STR = datetime.now().strftime("%H")
        LOG_DIR = LOG_BASE_DIR / DATE_STR / HOUR_STR
        LOG_FILE = LOG_DIR / f"{datetime.now().strftime('%M%S')}.log"

        # 创建日志目录
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # 配置日志格式
        LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
        formatter = logging.Formatter(LOG_FORMAT)

        # 文件处理器
        file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)

        # 主日志器配置
        cls._logger = logging.getLogger()
        cls._logger.setLevel(logging.DEBUG)
        cls._logger.addHandler(file_handler)
        
        # 禁用第三方库的日志
        logging.getLogger("PIL").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        
        cls._initialized = True

    @classmethod
    def info(cls, message):
        """记录INFO级别日志"""
        if not cls._initialized:
            cls.initialize()
        cls._logger.info(message)

    @classmethod
    def error(cls, message):
        """记录ERROR级别日志"""
        if not cls._initialized:
            cls.initialize()
        cls._logger.error(message)

    @classmethod
    def debug(cls, message):
        """记录DEBUG级别日志"""
        if not cls._initialized:
            cls.initialize()
        cls._logger.debug(message)
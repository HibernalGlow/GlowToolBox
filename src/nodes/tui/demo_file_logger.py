import logging
import os
import random
import time
import threading
from datetime import datetime

# 设置日志文件路径
LOG_FILE = r"D:\1VSCODE\GlowToolBox\src\nodes\tui\tests\test.log"

def write_demo_logs():
    """写入演示日志到文件"""
    # 配置日志记录器
    file_logger = logging.getLogger('demo')
    file_logger.setLevel(logging.INFO)
    
    # 添加文件处理器
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(message)s'))
    file_logger.addHandler(file_handler)
    
    # 预定义一些演示消息
    system_msgs = [
        "内存使用: {}MB",
        "磁盘空间: {}GB可用",
        "网络流量: {}MB/s"
    ]
    
    error_msgs = [
        "严重错误: 服务{}无响应",
        "数据库连接失败: {}",
        "内存溢出: 进程{}"
    ]
    
    info_msgs = [
        "用户{}登录成功",
        "处理任务{}: 完成",
        "更新检查: 版本{}可用"
    ]
    
    # 进度条任务
    progress_tasks = {
        "system": [
            ("系统更新", "普通百分比"),
            ("内存清理", "带括号分数")
        ],
        "error": [
            ("错误检查", "普通百分比"),
            ("日志分析", "带括号分数")
        ],
        "info": [
            ("数据同步", "普通百分比"),
            ("配置更新", "带括号分数")
        ]
    }
    
    # 记录活动进度条
    active_progress = {
        "system": {},
        "error": {},
        "info": {}
    }
    
    try:
        while True:
            # 系统消息
            msg = random.choice(system_msgs)
            value = random.randint(1, 100)
            file_logger.info(f"[#system]{msg.format(value)}")
            
            # 错误消息
            if random.random() < 0.1:
                msg = random.choice(error_msgs)
                value = random.randint(1, 5)
                file_logger.error(f"[#error]{msg.format(value)}")
            
            # 信息消息
            msg = random.choice(info_msgs)
            value = random.randint(1000, 9999)
            file_logger.info(f"[#info]{msg.format(value)}")
            
            # 更新进度条
            for panel in ["system", "error", "info"]:
                # 随机启动新进度条
                if len(active_progress[panel]) < 1 and random.random() < 0.1:
                    available_tasks = [t for t, _ in progress_tasks[panel] if t not in active_progress[panel]]
                    if available_tasks:
                        task = random.choice(available_tasks)
                        format_type = next(fmt for t, fmt in progress_tasks[panel] if t == task)
                        active_progress[panel][task] = {"progress": 0, "format": format_type}
                        
                        if format_type == "普通百分比":
                            file_logger.info(f"[@{panel}]{task} 0%")
                        else:
                            file_logger.info(f"[@{panel}]{task} (0/100) 0%")
                
                # 更新现有进度条
                for task in list(active_progress[panel].keys()):
                    task_info = active_progress[panel][task]
                    progress = task_info["progress"]
                    format_type = task_info["format"]
                    progress += random.randint(1, 5)
                    
                    if progress >= 100:
                        if format_type == "普通百分比":
                            file_logger.info(f"[@{panel}]{task} 100%")
                        else:
                            file_logger.info(f"[@{panel}]{task} (100/100) 100%")
                        del active_progress[panel][task]
                    else:
                        task_info["progress"] = progress
                        if format_type == "普通百分比":
                            file_logger.info(f"[@{panel}]{task} {progress}%")
                        else:
                            file_logger.info(f"[@{panel}]{task} ({progress}/100) {progress}%")
            
            time.sleep(random.uniform(0.1, 0.3))
            
    except KeyboardInterrupt:
        pass
    finally:
        file_handler.close()

if __name__ == "__main__":
    from nodes.tui.textual_logger import TextualLoggerManager
    
    # 确保日志文件存在
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    
    # 设置布局并指定日志文件
    TextualLoggerManager.set_layout({
        "system": {"title": "🖥️ 系统状态", "style": "lightgreen", "ratio": 2},
        "error": {"title": "❌ 错误检查", "style": "lightpink", "ratio": 2},
        "info": {"title": "ℹ️ 信息日志", "style": "lightblue", "ratio": 3},
    }, log_file=LOG_FILE)
    
    # 在新线程中运行日志写入
    log_thread = threading.Thread(target=write_demo_logs)
    log_thread.daemon = True
    log_thread.start()
    
    # 保持程序运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass 
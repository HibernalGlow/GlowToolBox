import time
import logging
import random
from concurrent.futures import ThreadPoolExecutor
from nodes.tui.textual_logger import TextualLoggerManager
from nodes.record.logger_config import setup_logger

# 初始化日志
config = {
    'script_name': 'textual_logger_test',
    'console_enabled': False
}
logger = setup_logger(config)

# 配置日志布局并等待初始化
TextualLoggerManager.set_layout({
    "system": {"title": "🖥️ 系统状态", "style": "lightgreen", "ratio": 2},
    "error": {"title": "❌ 错误检查", "style": "lightred", "ratio": 2},
    "info": {"title": "ℹ️ 信息日志", "style": "lightblue", "ratio": 2},
    "progress": {"title": "📊 进度", "style": "yellow", "ratio": 2},
    "debug": {"title": "🔍 调试", "style": "magenta", "ratio": 3},
})

# 等待界面初始化
time.sleep(1)

def test_basic_logging():
    """测试基本日志功能"""
    logger.info("[#info]测试普通日志")
    logger.warning("[#info]测试警告日志")
    logger.error("[#error]测试错误日志")
    time.sleep(1)

def test_progress_bars():
    """测试进度条功能"""
    # 测试不同格式的进度条
    formats = [
        ("简单进度", "[@progress]任务1 {}%"),
        ("带分数进度", "[@progress]任务2 ({}/{}) {}%"),
        ("带方括号", "[@progress]任务3 [{}/100] {}%")
    ]
    
    for name, fmt in formats:
        for i in range(0, 101, 10):
            if "分数" in name:
                logger.info(fmt.format(i, 100, i))
            elif "方括号" in name:
                logger.info(fmt.format(i, i))
            else:
                logger.info(fmt.format(i))
            time.sleep(0.1)

def test_concurrent_logging():
    """测试并发日志"""
    def log_worker(worker_id):
        for i in range(10):
            logger.info(f"[#debug]工作线程 {worker_id} - 消息 {i}")
            if random.random() < 0.2:
                logger.warning(f"[#debug]工作线程 {worker_id} - 警告 {i}")
            time.sleep(random.uniform(0.05, 0.2))

    with ThreadPoolExecutor(max_workers=5) as executor:
        for i in range(5):
            executor.submit(log_worker, i)

def test_long_messages():
    """测试长消息处理"""
    # 测试长路径
    long_path = "/very/long/path/" * 10 + "file.txt"
    logger.info(f"[#system]处理文件: {long_path}")
    
    # 测试长消息
    long_msg = "这是一段非常长的消息，" * 10
    logger.info(f"[#info]{long_msg}")
    
    # 测试多行消息
    multiline = """[#debug]多行消息测试:
    第一行
    第二行
    第三行"""
    logger.info(multiline)

def test_mixed_updates():
    """测试混合更新"""
    def update_task(name, total):
        for i in range(total):
            # 进度条更新
            logger.info(f"[@progress]{name} {i/total*100:.1f}%")
            # 同时输出日志
            if random.random() < 0.3:
                logger.info(f"[#info]{name} 处理步骤 {i+1}")
            time.sleep(0.1)

    with ThreadPoolExecutor() as executor:
        tasks = [
            ("任务A", 20),
            ("任务B", 15),
            ("任务C", 10)
        ]
        for name, total in tasks:
            executor.submit(update_task, name, total)

def run_all_tests():
    """运行所有测试"""
    tests = [
        ("基本日志测试", test_basic_logging),
        ("进度条测试", test_progress_bars),
        ("并发日志测试", test_concurrent_logging),
        ("长消息测试", test_long_messages),
        ("混合更新测试", test_mixed_updates)
    ]
    
    for name, test_func in tests:
        logger.info(f"[#system]开始 {name}")
        test_func()
        logger.info(f"[#system]完成 {name}")
        time.sleep(1)

if __name__ == "__main__":
    try:
        # 确保界面完全准备好
        logger.info("[#system]正在初始化测试环境...")
        time.sleep(0.5)  # 额外等待确保界面就绪
        
        run_all_tests()
    except KeyboardInterrupt:
        logger.warning("[#system]测试被用户中断")
    except Exception as e:
        logger.error(f"[#error]测试出错: {str(e)}")
    finally:
        logger.info("[#system]测试结束")
        # 保持窗口显示一段时间
        time.sleep(5)
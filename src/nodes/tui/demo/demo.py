import time
import logging
from nodes.tui.textual_logger import TextualLoggerManager
TextualLoggerManager.set_layout({
    "system": {"title": "🖥️ 系统状态", "style": "lightgreen", "ratio": 2},
    "error": {"title": "❌ 错误检查", "style": "lightpink", "ratio": 2},
    "info": {"title": "ℹ️ 信息日志", "style": "lightblue", "ratio": 3},
})
from nodes.logs.logger_config import setup_logger
# 使用标准logging发送日志
config = {
    'script_name': 'textual_logger',
    'console_enabled': False
}
logger = setup_logger(config)
def demo_logs():
        """演示日志功能"""
        import random
        from concurrent.futures import ThreadPoolExecutor

        # 等待应用初始化完成
        time.sleep(1)

        # 创建线程池（20个线程）
        executor = ThreadPoolExecutor(max_workers=20)

        def stress_test(panel_name: str):
            """并发压力测试"""
            for i in range(100):
                # 生成随机长路径
                long_path = f"[{panel_name}] 处理路径: /{'非常长的/'*8}漫画/{'子目录/'*6}第{i:04d}话/[作者] 作品名{'v'*i}.zip"
                logger.info(long_path)
                
                # 随机添加换行
                if random.random() < 0.2:
                    multiline_msg = f"[{panel_name}] 多行日志:\n  第一行内容\n  第二行内容{i}"
                    logger.info(multiline_msg)
                
                time.sleep(random.uniform(0.001, 0.01))

        # 添加长路径测试用例
        long_path_cases = [
            "[#file_ops] 跳过黑名单文件: [Armadillo (練慈、大慈)]/1. 同人志/[2024.01] [PIXIV FANBOX] 便利屋編 (ブルーアーカイブ) [葱鱼个人汉化].zip",
            "[#system] 监控路径: D:/漫画收藏/作者名（包含特殊字符!@#$%^&*()）/2024年作品/第123话 特别篇/最终版本/compressed.zip"
        ]

        # 提交并发测试任务
        for case in long_path_cases:
            executor.submit(logger.info, case)
        
        # 对每个面板进行压力测试
        for panel in ["system", "error", "info", "file_ops"]:
            executor.submit(stress_test, f"#{panel}")
            executor.submit(stress_test, f"@{panel}")

        # 保持程序运行

# 配置日志布局
def demo_progress_bars():
    """演示进度条功能"""
    # 演示百分比格式进度条（包含小数点）
    for i in range(0, 1001, 10):
        percentage = i / 10.0
        logging.info(f"[#progress_panel=]处理任务A {percentage:.3f}%")
        time.sleep(0.2)
    
    # 演示分数格式进度条
    total = 5
    for i in range(1, total + 1):
        logging.info(f"[#progress_panel=]处理任务B({i}/{total})")
        time.sleep(0.5)

def demo_line_updates():
    """演示行内更新和折行功能"""
    # 演示相同前缀的行内更新
    logging.info("[#update_panel]正在处理文件 开始扫描...")
    time.sleep(1)
    logging.info("[#update_panel]正在处理文件 扫描完成，开始分析...")
    time.sleep(1)
    logging.info("[#update_panel]正在处理文件 分析完成，开始优化...")
    time.sleep(1)
    logging.info("[#update_panel]正在处理文件 处理完成！")
    
    # 演示连续内容的折行
    logging.info("[#update_panel]第一行内容")
    time.sleep(0.5)
    logging.info("[#update_panel]  第二行内容（注意前面的缩进）")
    time.sleep(0.5)
    logging.info("[#update_panel]    第三行内容（更多缩进）")
    
    # 演示长文本折行（最多折两行）
    long_text = "这是一段非常长的文本，用来演示文本折行功能。当文本超过面板宽度时，会自动折行，但最多只折两行，超出部分用省略号表示。这段文本肯定会超出两行。"
    logging.info(f"[#update_panel]{long_text}")

def demo_mixed_updates():
    """演示混合进度条和普通日志更新"""
    import random
    tasks = {
        "system": [
            ("系统扫描", 10),
            ("内存优化", 5),
            ("磁盘整理", 8)
        ],
        "error": [
            ("错误检查", 3),
            ("日志分析", 4)
        ],
        "info": [
            ("数据同步", 6),
            ("配置更新", 7)
        ]
    }
    
    def update_task(panel, task_name, duration):
        """模拟带进度条的任务"""
        for i in range(101):
            # 随机插入普通日志
            if random.random() < 0.3:
                logger.info(f"[#{panel}] 后台处理: {task_name} - 步骤{i}")
            # 更新进度条
            logger.info(f"[@{panel}]{task_name} {i}%")
            time.sleep(duration * 0.01)
        # 完成后持续输出普通日志
        for _ in range(3):
            logger.info(f"[#{panel}] {task_name} 已完成，正在清理...")
            time.sleep(0.5)

    # 使用线程池模拟并行任务
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor() as executor:
        for panel in tasks:
            for task_name, duration in tasks[panel]:
                executor.submit(update_task, panel, task_name, duration)
                
        # 同时发送普通日志
        for _ in range(50):
            panel = random.choice(["system", "error", "info"])
            logger.info(f"[#{panel}] 随机日志: {random.randint(1000,9999)}")
            time.sleep(0.1)

if __name__ == "__main__":
    # 更新演示入口
    demo_logs()
    demo_progress_bars()
    demo_line_updates()
    demo_mixed_updates()  # 添加混合测试
    
    # 延长演示时间
    time.sleep(15) 
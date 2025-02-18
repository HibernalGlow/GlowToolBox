import time
import logging
from textual_logger import TextualLoggerManager

# 配置日志布局
TEXTUAL_LAYOUT = {
    "progress_panel": {
        "ratio": 1,
        "title": "🔄 进度演示",
        "style": "cyan"
    },
    "update_panel": {
        "ratio": 1,
        "title": "📝 更新演示",
        "style": "green"
    }
}

# 初始化日志管理器
TextualLoggerManager.set_layout(TEXTUAL_LAYOUT)

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

if __name__ == "__main__":
    # 运行演示
    demo_progress_bars()
    demo_line_updates()
    
    # 保持程序运行一段时间以查看效果
    time.sleep(5) 
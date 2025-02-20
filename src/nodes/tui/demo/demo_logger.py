from nodes.tui.textual_logger import TextualLoggerManager
import logging
import time
import random
import os
from pathlib import Path
from nodes.record.logger_config import setup_logger
# 初始化日志
config = {
   'script_name': 'textual_logger_test',
    'console_enabled': False
}
logger = setup_logger(config)

# 初始化布局配置
LAYOUT_CONFIG = {
    "status": {
        "ratio": 1,
        "title": "🏭 总体进度",
        "style": "lightblue"
    },
    "progress": {
        "ratio": 1,
        "title": "🔄 当前进度",
        "style": "lightgreen"
    },
    "performance": {
        "ratio": 1,
        "title": "⚡ 性能配置",
        "style": "lightyellow"
    },
    "image_convert": {
        "ratio": 2,
        "title": "🖼️ 图片转换",
        "style": "lightsalmon"
    },   
    "archive_ops": {
        "ratio": 2,
        "title": "📦 压缩包处理",
        "style": "lightpink"
    },
    "file_ops": {
        "ratio": 2,
        "title": "📂 文件操作",
        "style": "lightcyan"
    },
}

def simulate_archive_processing():
    """模拟压缩包处理过程"""
    # 模拟处理多个压缩包
    archives = [
        "example1.zip",
        "example2.zip",
        "example3.zip",
        "very_long_archive_name_with_some_chinese_characters_汉化组_修正版.zip"
    ]
    
    total_archives = len(archives)
    for idx, archive in enumerate(archives, 1):
        # 更新总体进度
        progress = (idx / total_archives) * 100
        logger.info(f"[@status]处理进度 ({idx}/{total_archives}) {progress:.1f}%")
        
        # 模拟压缩包处理
        logger.info(f"[#archive_ops]🔄 开始处理: {archive}")
        
        # 模拟检查压缩包内容
        time.sleep(0.5)
        image_count = random.randint(10, 30)
        logger.info(f"[#archive_ops]📝 开始处理压缩包: {archive}")
        logger.info(f"[#archive_ops]发现 {image_count} 个图片文件")
        
        # 模拟性能配置
        thread_count = random.randint(2, 8)
        batch_size = random.randint(4, 16)
        logger.info(f"[#performance]当前线程数: {thread_count}, 当前批处理大小: {batch_size}")
        
        # 模拟图片处理
        for i in range(image_count):
            # 更新当前进度
            img_progress = (i + 1) / image_count * 100
            logger.info(f"[@progress]当前进度: {i+1}/{image_count} {img_progress:.1f}%")
            
            # 模拟单张图片处理
            img_name = f"image_{i+1:03d}.jpg"
            original_size = random.randint(1000, 5000)
            new_size = original_size * random.uniform(0.3, 0.8)
            reduction = original_size - new_size
            ratio = (reduction / original_size) * 100
            
            logger.info(f"[#image_convert]✅ {img_name} ({original_size:.0f}KB -> {new_size:.0f}KB, 减少{reduction:.0f}KB, 压缩率{ratio:.1f}%)")
            
            # 模拟文件操作
            if random.random() < 0.1:  # 10%概率显示文件操作
                long_path = f"D:/very/long/path/to/some/directory/structure/that/contains/many/levels/{img_name}"
                logger.info(f"[#file_ops]处理文件: {long_path}")
            
            time.sleep(0.1)  # 模拟处理时间
            
        # 模拟压缩包完成处理
        total_original = sum([random.randint(1000, 5000) for _ in range(image_count)])
        total_converted = total_original * random.uniform(0.3, 0.8)
        total_reduction = total_original - total_converted
        total_ratio = (total_reduction / total_original) * 100
        
        summary = (
            f"✨ 处理完成 "
            f"📊 总文件数: {image_count} "
            f"⏱️ 总耗时: {random.uniform(5, 15):.1f}秒 "
            f"📦 总大小: {total_original/1024:.1f}MB -> {total_converted/1024:.1f}MB "
            f"📈 压缩率: {total_ratio:.1f}%"
        )
        logger.info(f"[#archive_ops]{summary}")
        
        time.sleep(1)  # 模拟压缩包间隔

def main():
    # 初始化日志系统
    TextualLoggerManager.set_layout(LAYOUT_CONFIG)
    
    # 等待日志系统初始化
    time.sleep(1)
    
    try:
        # 开始模拟处理
        simulate_archive_processing()
        
        # 保持程序运行一段时间以显示最终结果
        time.sleep(5)
        
    except KeyboardInterrupt:
        logger.info("[#status]程序被用户中断")
    except Exception as e:
        logger.error(f"[#status]程序出错: {str(e)}")

if __name__ == "__main__":
    main()
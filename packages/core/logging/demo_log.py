import time
import random
import psutil
from datetime import datetime
from rich.text import Text
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.rich_logger import log_panel, set_layout, RichLoggerManager, RichLoggerContext,get_multiline_input

def demo_conversion_logs():
    """演示完整的图片转换日志流程（无限随机版）"""
    try:
        # 0. 初始化系统信息
        sys_info = Text()
        sys_info.append("🖥️ 系统信息: ", style="cyan")
        sys_info.append(f"CPU核心 {os.cpu_count()} | ", style="bright_black")
        sys_info.append(f"内存 {psutil.virtual_memory().total//1024//1024}MB | ", style="bright_black")
        sys_info.append(f"Python {sys.version.split()[0]}", style="bright_black")
        log_panel("performance", sys_info)

        # 1. 初始化日志（带版本信息）
        init_log = Text()
        init_log.append("🔄 图片转换引擎 v2.4.1 初始化...\n", style="bold")
        init_log.append("▔"*40, style="bright_black")
        log_panel("process", init_log)
        log_panel("update", "📅 任务开始时间: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        # 2. 显示转换参数（带动态配置）
        params_text = Text()
        params_text.append("⚙️ 转换参数:\n", style="bold cyan")
        params_text.append("  目标格式: ", style="cyan")
        params_text.append("AVIF\n", style="bold cyan")
        params_text.append("  质量: ", style="cyan")
        params_text.append(f"90 (动态范围 85-95)\n", style="yellow")
        params_text.append("  速度: ", style="cyan")
        params_text.append("7 (平衡模式)\n", style="magenta")
        params_text.append("└─ 高级设置: ", style="cyan")
        params_text.append("色度保留 | 元数据清理", style="bright_black")
        log_panel("process", params_text)

        # 3. 无限循环处理
        completed = 0
        warnings = 0
        errors = 0
        file_num = 0
        
        while True:
            file_num += 1
            time.sleep(random.uniform(0.3, 1.0))  # 随机延迟，模拟处理时间
            
            # 生成日志条目
            log = Text()
            log.append(f"📄 文件 {file_num:02d}: ", style="cyan")
            
            # 随机文件名和扩展名
            ext = random.choice(['.jpg', '.png', '.webp', '.gif', '.bmp'])
            filename = random.choice([
                f"photo_{file_num:03d}",
                f"image_{random.randint(1000, 9999)}",
                f"pic_{datetime.now().strftime('%H%M%S')}",
                f"artwork_{random.randint(100, 999)}",
                f"snapshot_{file_num:04d}"
            ])
            log.append(f"{filename}{ext}", style="yellow")
            log.append(" → ", style="white")
            log.append(f"output_{file_num:03d}.avif ", style="green")
            
            # 随机生成结果
            result_type = random.choices(
                ['success', 'warning', 'error'],
                weights=[0.85, 0.1, 0.05]
            )[0]
            
            if result_type == 'warning':
                warn_type = random.choice([
                    "ICC配置缺失",
                    "非sRGB色彩空间",
                    "EXIF信息异常",
                    "分辨率超过4K",
                    "元数据不完整",
                    "色彩深度异常",
                    "压缩比过高"
                ])
                log.append(f"[⚠️ {warn_type}]", style="yellow")
                warnings += 1
            elif result_type == 'error':
                err_type = random.choice([
                    ("文件头损坏", "0xC0000034"),
                    ("权限不足", "0x80070005"),
                    ("内存不足", "0x8007000E"),
                    ("不支持的格式", "0x80070057"),
                    ("文件被占用", "0x80070020"),
                    ("磁盘空间不足", "0x80070070")
                ])
                log.append(f"[❌ {err_type[0]} (代码 {err_type[1]})]", style="red")
                errors += 1
            else:
                orig_size = random.randint(800, 5000)
                new_size = orig_size * random.uniform(0.3, 0.7)
                reduction = orig_size - new_size
                log.append(f"[{orig_size}KB → {new_size:.0f}KB | -{reduction:.0f}KB]", style="bright_black")
                completed += 1
            
            log_panel("process", log)
            
            # 更新统计
            stats = Text()
            log_panel("current_stats",f"📊 实时统计:\n", style="bold")
            log_panel("current_stats",f"  总数: ", style="cyan")
            log_panel("current_stats",f"{completed + errors + warnings} ", style="blue")
            log_panel("current_stats",f"文件\n", style="bright_black")
            log_panel("current_stats",f"  ✅ 成功: ", style="green")
            log_panel("current_stats",f"{completed}\n", style="bold green")
            log_panel("current_stats",f"  ⚠️ 警告: ", style="yellow")
            log_panel("current_stats",f"{warnings}\n", style="bold yellow")
            log_panel("current_stats",f"└─ ❌ 失败: ", style="red")
            log_panel("current_stats",f"{errors}", style="bold red")
            log_panel("current_stats", stats)
            
            # 更新性能监控
            perf = Text()
            log_panel("performance","⚡ 资源使用:\n", style="bold")
            log_panel("performance",f"  CPU: ", style="cyan")
            cpu_usage = random.randint(30, 95)
            log_panel("performance",f"{cpu_usage}%", style="green" if cpu_usage < 80 else "red")
            log_panel("performance",f"\n  内存: ", style="cyan")
            mem_usage = random.randint(1200, 3500)
            log_panel("performance",f"{mem_usage}MB", style="green" if mem_usage < 2500 else "yellow")
            log_panel("performance",f"\n└─ 线程: ", style="cyan")
            threads = random.randint(4, 16)
            log_panel("performance",f"{threads}", style="green")
            log_panel("performance", perf)
            
            # 随机系统消息
            if random.random() < 0.1:  # 10%概率显示系统消息
                sys_msg = random.choice([
                    "🔄 正在优化缓存...",
                    "📦 清理临时文件...",
                    "💾 同步元数据...",
                    "🔍 扫描新文件...",
                    "⚡ 性能自动调优...",
                    "🛠️ 更新转换参数...",
                    "📊 重新计算统计...",
                    "🔒 验证文件完整性..."
                ])
                log_panel("update", Text(sys_msg, style="cyan"))

    except KeyboardInterrupt:
        interrupt_log = Text()
        interrupt_log.append("⏹️ 用户中断操作! ", style="yellow bold")
        interrupt_log.append("正在保存进度...", style="bright_black")
        log_panel("update", interrupt_log)
        time.sleep(1)
    finally:
        cleanup_log = Text()
        cleanup_log.append("🗑️ 清理流程:\n", style="bold")
        cleanup_log.append("  删除临时文件...", style="bright_black")
        log_panel("update", cleanup_log)
        time.sleep(0.5)
        cleanup_log.append("\n  移除缓存数据...", style="bright_black")
        log_panel("update", cleanup_log)
        time.sleep(0.5)
        cleanup_log.append("\n└─ 备份日志文件...", style="bright_black")
        log_panel("update", cleanup_log)
        time.sleep(1)
        log_panel("update", Text("✅ 所有清理操作已完成", style="green"))

if __name__ == "__main__":
    demo_conversion_logs()

from loguru import logger  # 使用loguru替代logging
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.theme import Theme
from rich.text import Text
from rich.layout import Layout
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TaskProgressColumn,
)
from rich.live import Live
from rich.panel import Panel
from rich import box
from collections import deque
import threading
import time
import random
import re
import difflib
import sys



def setup_logging(log_dir="D:/1VSCODE/1ehv/logs", log_filename=None):
    """配置日志系统"""
    # 移除默认的sink
    logger.remove()
    
    # 创建日志目录结构
    log_dir = Path(log_dir)
    log_dir.mkdir(exist_ok=True)
    
    # 获取当前日期
    current_date = datetime.now().strftime('%Y%m%d')
    
    # 如果没有指定日志文件名，则使用调用脚本的名字
    if log_filename is None:
        script_name = Path(sys.argv[0]).stem
        script_dir = log_dir / script_name
        script_dir.mkdir(exist_ok=True)
        
        date_dir = script_dir / current_date
        date_dir.mkdir(exist_ok=True)
        
        log_filename = f"{datetime.now().strftime('%H%M%S')}.log"
        log_file = date_dir / log_filename
    else:
        script_name = Path(log_filename).stem.split('_')[0]
        script_dir = log_dir / script_name
        script_dir.mkdir(exist_ok=True)
        date_dir = script_dir / current_date
        date_dir.mkdir(exist_ok=True)
        log_file = date_dir / log_filename

    # 添加文件日志
    logger.add(
        str(log_file),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        encoding='utf-8'
    )
    
    return logger

# 自定义主题
custom_theme = Theme({
    "info": "green",
    "warning": "yellow",
    "error": "red",
    "critical": "red bold",
    "success": "green",
    "processing": "cyan",
    "file": "blue",
    "path": "magenta",
    "number": "yellow",
    "size": "cyan",
    "mode": "magenta",
    "result": "green",
})

# 创建全局console实例
console = Console(
        theme=custom_theme,
        force_terminal=True,  # 强制终端模式
        color_system="auto",           # 自动检测颜色支持
        width=None,                    # 自动检测宽度
        height=None,                   # 自动检测高度
        legacy_windows=True,          # 现代Windows终端支持
        safe_box=True                  # 使用安全的框字符
    )

# 添加全局处理器示例
_global_handler = None

# 添加全局自动管理
_handler = None
_initialized = False

def ensure_handler():
    """确保handler已初始化"""
    global _handler, _initialized
    if not _initialized:
        _handler = RichLoggerManager.get_handler()
        _initialized = True
        # 注册程序退出时的清理函数
        import atexit
        atexit.register(cleanup_handler)
    return _handler

def cleanup_handler():
    """清理handler"""
    global _handler, _initialized
    if _initialized:
        RichLoggerManager.close_handler()
        _handler = None
        _initialized = False

def _format_message_with_wrapping(message: str, max_line_length: int = 80) -> str:
    """
    格式化消息文本,添加自动换行
    
    Args:
        message: 原始消息文本
        max_line_length: 每行最大长度
        
    Returns:
        str: 格式化后的消息文本
    """
    # 如果消息已经包含换行符,保持原有的换行
    if "\n" in message:
        lines = message.split("\n")
        formatted_lines = []
        for line in lines:
            if len(line) > max_line_length:
                formatted_lines.extend(_wrap_line(line, max_line_length))
            else:
                formatted_lines.append(line)
        return "\n".join(formatted_lines)
    
    # 如果消息长度未超过限制,直接返回
    if len(message) <= max_line_length:
        return message
        
    return "\n".join(_wrap_line(message, max_line_length))

def _wrap_line(line: str, max_length: int) -> list:
    """
    将单行文本按最大长度分割成多行
    
    Args:
        line: 需要分割的文本行
        max_length: 每行最大长度
        
    Returns:
        list: 分割后的文本行列表
    """
    words = line.split()
    lines = []
    current_line = []
    current_length = 0
    
    for word in words:
        # 检查添加这个词是否会超过最大长度
        if current_length + len(word) + (1 if current_line else 0) <= max_length:
            current_line.append(word)
            current_length += len(word) + (1 if current_line else 0)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_length = len(word)
    
    if current_line:
        lines.append(" ".join(current_line))
    
    return lines

def log_panel(panel_name, message, layout_config=None):
    """
    向指定面板记录日志
    
    Args:
        panel_name: 面板名称
        message: 日志消息
        layout_config: 可选的布局配置
    """
    try:
        handler = RichLoggerManager.get_handler(layout_config)
        if handler:
            # 使用handler的预处理方法处理消息
            if isinstance(message, str):
                # messages = handler._preprocess_message(message)
                formatted_message = message
                # formatted_message = "\n".join(messages)
            else:
                formatted_message = str(message)
            handler.update_panel(panel_name, formatted_message)
    except Exception as e:
        handler.update_panel(panel_name, formatted_message)
        # print(f"Error logging to panel: {e}")

def set_layout(layout_config):
    """
    设置全局布局配置
    
    Args:
        layout_config: 布局配置字典
    """
    RichLoggerManager.set_layout(layout_config)

class LogManager:
    """日志管理器，用于控制日志显示和刷新"""
    def __init__(self, max_main_logs=15, max_status_logs=8, refresh_interval=0.2):
        self.max_main_logs = max_main_logs
        self.max_status_logs = max_status_logs
        self.refresh_interval = refresh_interval
        self.last_refresh = time.time()
        self.pending_main_logs = []
        self.pending_status_logs = []
        self.log_lock = threading.Lock()

    def should_refresh(self):
        """检查是否应该刷新显示"""
        current_time = time.time()
        return current_time - self.last_refresh >= self.refresh_interval

    def add_main_log(self, handler, message):
        """添加主要操作日志"""
        with self.log_lock:
            self.pending_main_logs.append(message)
            if self.should_refresh():
                self._flush_logs(handler)

    def add_status_log(self, handler, message):
        """添加状态变化日志"""
        with self.log_lock:
            self.pending_status_logs.append(message)
            if self.should_refresh():
                self._flush_logs(handler)

    def _flush_logs(self, handler):
        """将待处理的日志刷新到显示"""
        # 增加刷新条件判断
        if not self.pending_main_logs and not self.pending_status_logs:
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # 处理主日志
        for msg in self.pending_main_logs:
            handler.main_log_lines.append(f"[{timestamp}] {msg}")
            while len(handler.main_log_lines) > self.max_main_logs:
                handler.main_log_lines.popleft()
        self.pending_main_logs.clear()
        
        # 处理状态日志
        for msg in self.pending_status_logs:
            handler.status_log_lines.append(f"[{timestamp}] {msg}")
            while len(handler.status_log_lines) > self.max_status_logs:
                handler.status_log_lines.popleft()
        self.pending_status_logs.clear()
        
        # 优化后的显示更新
        if time.time() - self.last_refresh >= self.refresh_interval:
            handler.update_display()
            self.last_refresh = time.time()

class StaticRichHandler:
    """静态Panel布局处理器"""
    def __init__(self, layout_config=None, style_config=None):
        self.layout = Layout()
        self.console = console  # 使用全局console实例
        self.panels = {}
        
        # 设置日志系统
        self.logger = setup_logging()
        
        # 默认布局配置
        self.layout_config = layout_config or {
            "main": {"size": 3, "title": "主面板"},
            "status": {"size": 3, "title": "状态"},
            "log": {"size": 6, "title": "日志"}
        }
        
        # 默认样式配置
        self.style_config = style_config or {
            "border_style": "blue",
            "title_style": "white",
            "padding": (0, 1),
            "panel_styles": {}  # 添加面板样式配置
        }
        
        self._setup_layout()
        self.live = Live(
            self.layout,
            console=self.console,
            refresh_per_second=15,
            vertical_overflow="visible"
        )
    
    def _setup_layout(self):
        """设置固定布局"""
        layouts = []
        for name, config in self.layout_config.items():
            self.panels[name] = {
                "title": config["title"],
                "content": Text(""),
            }
            
            # 同时支持size和ratio配置
            if "ratio" in config:
                self.panels[name]["ratio"] = config["ratio"]
                layouts.append(Layout(name=name, ratio=config["ratio"]))
            else:
                self.panels[name]["size"] = config.get("size", 4)  # 默认size为1
                layouts.append(Layout(name=name, size=config.get("size", 1)))
            
        self.layout.split(*layouts)
    
    def update_panel(self, name: str, content, append: bool = False):
        """更新panel内容"""
        if name not in self.panels:
            return
            
        if append and isinstance(content, (str, Text)):
            old_content = self.panels[name]["content"]
            if isinstance(old_content, Text):
                old_content.append("\n" + str(content))
            else:
                self.panels[name]["content"] = Text(str(old_content) + "\n" + str(content))
        else:
            # 如果是Progress对象，直接保存
            if isinstance(content, Progress):
                self.panels[name]["content"] = content
            else:
                # 根据auto_wrap决定是否进行预处理
                if self.auto_wrap and isinstance(content, str):
                    messages = self._preprocess_message(content)
                    content = "\n".join(messages)
                self.panels[name]["content"] = content if isinstance(content, Text) else Text(str(content))
        
        # 记录到日志文件
        if not isinstance(content, Progress):
            self.logger.info(f"[PANEL:{name}] {str(content)}")
            
        self._update_display()
    
    def _update_display(self):
        """更新显示"""
        for name, config in self.panels.items():
            try:
                # 获取面板内容
                content = config["content"]
                
                # 如果内容是Progress对象，需要特殊处理
                if isinstance(content, Progress):
                    # 创建一个临时的控制台来捕获进度条的渲染输出
                    temp_console = Console(force_terminal=True, width=self.console.width - 4)
                    with temp_console.capture() as capture:
                        with content:
                            content.refresh()
                    # 使用捕获的输出作为面板内容
                    content = Text.from_ansi(capture.get())
                elif not isinstance(content, Text):
                    content = Text(str(content))
                
                # 获取标题样式
                title_style = self.style_config.get("title_style", "white")
                title = f"[{title_style}]{config['title']}[/]"
                
                # 获取面板特定样式
                panel_style = self.style_config.get("panel_styles", {}).get(name)
                border_style = panel_style or self.style_config.get("border_style", "blue")
                
                # 更新面板
                self.layout[name].update(
                    Panel(
                        content,
                        title=title,
                        border_style=border_style,
                        box=box.ROUNDED,
                        padding=self.style_config.get("padding", (0, 1))
                    )
                )
            except Exception as e:
                # 使用update面板显示错误，而不是print
                if "update" in self.panels:
                    self.panels["update"]["content"] = Text(f"❌ 更新面板 {name} 时出错: {str(e)}", style="red")
                
    def update_display(self):
        """更新显示内容的公共接口"""
        self._update_display()

    def __enter__(self):
        self.live.__enter__()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.live.__exit__(exc_type, exc_val, exc_tb)

class RichProgressHandler(StaticRichHandler):
    """富文本进度和日志框架管理器"""
    def __init__(self, 
                 layout_config=None, 
                 progress_format=None,
                 max_main_logs=15,
                 max_status_logs=8,
                 refresh_interval=0.2,
                 style_config=None,
                 log_dir="D:/1VSCODE/1ehv/logs"):
        """
        初始化富文本进度和日志框架管理器
        
        Args:
            layout_config: 布局配置
            progress_format: 进度条格式
            max_main_logs: 主日志最大行数
            max_status_logs: 状态日志最大行数
            refresh_interval: 刷新间隔
            style_config: 样式配置
            log_dir: 日志目录
        """
        # 默认布局配置
        default_config = {
            "current_stats": {"size": 2, "title": "📊 总体进度", "style": "blue"},
            "current_progress": {"size": 2, "title": "🔄 当前进度", "style": "green"},
            "performance": {"size": 2, "title": "⚡ 性能配置", "style": "yellow"},
            "process": {"size": 3, "title": "📝 处理日志", "style": "cyan"},
            "update": {"size": 3, "title": "ℹ️ 更新日志", "style": "magenta"}
        }
        
        # 使用自定义配置或默认配置
        self.layout_config = layout_config or default_config
        
        # 默认样式配置
        default_style = {
            "border_style": "blue",
            "title_style": "white bold",
            "padding": (0, 1),
            "panel_styles": {}  # 面板样式配置
        }
        
        # 合并自定义样式配置
        self.style_config = {**default_style, **(style_config or {})}
        
        # 设置日志系统
        self.logger = setup_logging(log_dir=log_dir)
        
        # 初始化布局
        self.layout = Layout()
        self.console = console
        self.panels = {}
        
        # 计算实际可用宽度（考虑边框和填充）
        self.content_width = self.console.width - 8
        
        # 使用默认或自定义进度条格式
        self._setup_progress(progress_format)
        
        # 初始化日志队列
        self.process_log_lines = deque(maxlen=1)
        self.update_log_lines = deque(maxlen=100)
        self.status_log_lines = deque(maxlen=1)
        
        # 初始化统计信息
        self.stats = {
            "total": 0,
            "processed": 0,
            "success": 0,
            "warning": 0,
            "error": 0,
            "updated": 0,
        }
        
        # 创建日志管理器
        self.log_manager = LogManager(
            max_main_logs=max_main_logs,
            max_status_logs=max_status_logs,
            refresh_interval=refresh_interval
        )
        
        # 设置布局
        self._setup_layout()
        
        # 初始化 Live 显示
        self.live = Live(
            self.layout,
            console=self.console,
            refresh_per_second=15,
            vertical_overflow="visible"
        )

    def _setup_layout(self):
        """设置布局"""
        layouts = []
        
        # 处理每个面板配置
        for name, config in self.layout_config.items():
            # 创建面板配置
            self.panels[name] = {
                "title": config.get("title", name),
                "content": Text(""),
                "style": config.get("style", "blue")
            }
            
            # 创建布局配置
            if "ratio" in config:
                layouts.append(Layout(name=name, ratio=config["ratio"]))
            else:
                layouts.append(Layout(name=name, size=config.get("size", 1)))
        
        # 应用布局
        if layouts:
            self.layout.split(*layouts)

    def update_panel(self, name: str, content, append: bool = False):
        """更新面板内容"""
        # 如果面板不存在，动态添加
        if name not in self.panels:
            self.layout_config[name] = {
                "size": 5,  # 默认大小
                "title": name.title(),  # 将名称首字母大写作为标题
                "style": "blue"  # 默认样式
            }
            self._setup_layout()  # 重新设置布局
        
        if name in self.panels:
            if append and isinstance(content, (str, Text)):
                old_content = self.panels[name]["content"]
                if isinstance(old_content, Text):
                    old_content.append("\n" + str(content))
                else:
                    self.panels[name]["content"] = Text(str(old_content) + "\n" + str(content))
            else:
                self.panels[name]["content"] = content if isinstance(content, Text) else Text(str(content))
            
            # 记录到日志文件
            if not isinstance(content, Progress):
                self.logger.info(f"[PANEL:{name}] {str(content)}")
            
            self._update_display()

    def _update_display(self):
        """更新显示"""
        for name, config in self.panels.items():
            try:
                content = config["content"]
                
                # 处理进度条内容
                if isinstance(content, Progress):
                    temp_console = Console(force_terminal=True, width=self.console.width - 4)
                    with temp_console.capture() as capture:
                        with content:
                            content.refresh()
                    content = Text.from_ansi(capture.get())
                elif not isinstance(content, Text):
                    content = Text(str(content))
                
                # 获取面板样式
                panel_style = self.panels[name].get("style", "blue")
                
                # 更新面板
                self.layout[name].update(
                    Panel(
                        content,
                        title=f"[white bold]{self.panels[name]['title']}[/]",
                        border_style=panel_style,
                        box=box.ROUNDED,
                        padding=self.style_config.get("padding", (0, 1))
                    )
                )
            except Exception as e:
                # 使用update面板显示错误，而不是print
                if "update" in self.panels:
                    self.panels["update"]["content"] = Text(f"❌ 更新面板 {name} 时出错: {str(e)}", style="red")
                
    def _setup_progress(self, format_config=None):
        """设置进度条格式"""
        default_format = [
            SpinnerColumn(spinner_name="dots2", style="blue"),
            TextColumn("[cyan]{task.description}"),
            BarColumn(
                bar_width=None,
                style="blue",
                complete_style="green",
                finished_style="green bold"
            ),
            TextColumn("[cyan]{task.percentage:>3.0f}%"),
            TextColumn("[magenta]{task.completed}/{task.total}"),
            TimeRemainingColumn()
        ]
        
        format_config = format_config or default_format
        self.progress = Progress(
            *format_config,
            expand=True,
            transient=False
        )

    def create_progress_task(self, total, description):
        """创建新的进度任务"""
        if total is not None:
            self.set_total(total)
        return self.progress.add_task(description, total=total)

    def set_total(self, total):
        """设置总数并重置统计"""
        self.stats["total"] = total
        self.stats["processed"] = 0
        self.stats["success"] = 0
        self.stats["warning"] = 0
        self.stats["error"] = 0
        self.stats["updated"] = 0
        self._update_stats_panel()
        self._update_display()

    def _update_stats_panel(self):
        """更新统计信息面板"""
        progress_percentage = (self.stats["processed"] / self.stats["total"] * 100) if self.stats["total"] > 0 else 0
        stats_text = Text()
        stats_text.append("总进度: ", style="bright_white")
        stats_text.append(f"{progress_percentage:.1f}%", style="cyan bold")
        stats_text.append(" | 总数: ", style="bright_white")
        stats_text.append(str(self.stats["total"]), style="yellow")
        stats_text.append(" | 已处理: ", style="bright_white")
        stats_text.append(str(self.stats["processed"]), style="blue")
        stats_text.append(" | 成功: ", style="bright_white")
        stats_text.append(str(self.stats["success"]), style="green bold")
        stats_text.append(" | 更新: ", style="bright_white")
        stats_text.append(str(self.stats["updated"]), style="cyan bold")
        stats_text.append(" | 警告: ", style="bright_white")
        stats_text.append(str(self.stats["warning"]), style="yellow bold")
        stats_text.append(" | 错误: ", style="bright_white")
        stats_text.append(str(self.stats["error"]), style="red bold")
        
        # self.update_panel("current_stats", stats_text)

    def update_display(self):
        """更新显示内容"""
        # 更新统计信息
        self._update_stats_panel()
        
        # 更新进度条区域 - 使用文字形式显示进度
        progress_text = Text()
        has_active_tasks = False
        
        for task in self.progress.tasks:
            if not task.finished:
                has_active_tasks = True
                # 计算进度
                percentage = (task.completed / task.total * 100) if task.total > 0 else 0
                width = 50  # 固定进度条宽度
                completed_width = int(width * (task.completed / task.total)) if task.total > 0 else 0
                
                # 构建进度条
                progress_text.append(f"{task.description}: ", style="cyan")
                progress_text.append("[", style="blue")
                progress_text.append("=" * completed_width, style="green")
                progress_text.append(" " * (width - completed_width))
                progress_text.append("] ", style="blue")
                progress_text.append(f"{percentage:>6.2f}% ", style="cyan")  # 添加两位小数的百分比
                progress_text.append(f"({task.completed}/{task.total})", style="yellow")  # 添加完成数/总数
                progress_text.append("\n")
        
        if not has_active_tasks:
            progress_text = Text("无活动任务", style="yellow")
        
        self.update_panel("current_progress", progress_text)
        
        # 更新处理状态
        combined_logs = list(self.status_log_lines) + list(self.process_log_lines)
        if combined_logs:
            process_log_content = Text(combined_logs[-1])
        else:
            process_log_content = Text("")
        self.update_panel("process", process_log_content)
        
        # 更新日志区域
        update_log_text = Text()
        for i, log in enumerate(self.update_log_lines):
            if i > 0:
                update_log_text.append("\n")
            update_log_text.append(log)
        self.update_panel("update", update_log_text)

    def add_log(self, message, log_type="process"):
        """根据消息类型添加日志到相应区域"""
        # 先添加时间戳
        timestamp = datetime.now().strftime("%H:%M:%S")
        message = f"[{timestamp}] {message}"
        
        # 处理消息样式
        if any(marker in message for marker in ["\033[9m", "\033[29m", "\033[1m", "\033[22m"]):
            text = Text()
            parts = message.split("\033")
            for part in parts:
                if part.startswith("[9m"):  # 删除线样式
                    content = part[3:].split("\033")[0]
                    text.append(content, style="red strike")
                elif part.startswith("[1m"):  # 粗体样式
                    content = part[3:].split("\033")[0]
                    text.append(content, style="green bold")
                elif not any(x in part for x in ["[29m", "[22m"]):  # 普通文本
                    text.append(part)
            formatted_message = text
        else:
            formatted_message = Text(message)
        
        # 根据消息类型分类
        if "✅" in str(message):
            self.process_log_lines.clear()
            self.process_log_lines.append(formatted_message)
            self.stats["success"] += 1
        elif "❌" in str(message) or log_type == "error":
            self.stats["error"] += 1
            self.update_log_lines.append(formatted_message)
        elif "⚠️" in str(message) or log_type == "warning":
            self.stats["warning"] += 1
            self.update_log_lines.append(formatted_message)
        else:
            self.update_log_lines.append(formatted_message)
            
        if log_type != "system":
            self.stats["processed"] += 1
        
        self.update_display()

    def _preprocess_message(self, message):
        """预处理所有日志消息 - 已弃用，使用Rich的内置功能"""
        if not isinstance(message, str):
            message = str(message)
        return [message]

    def add_success_log(self, message):
        """添加成功日志"""
        self.update_panel("update", f"✅ {message}")

    def add_error_log(self, message):
        """添加错误日志"""
        self.update_panel("update", f"❌ {message}")

    def add_warning_log(self, message):
        """添加警告日志"""
        self.update_panel("update", f"⚠️ {message}")

    def add_update_log(self, message):
        """添加更新日志"""
        self.update_panel("update", message)

    def add_status_log(self, message):
        """添加状态日志"""
        self.update_panel("process", f"🔄 {message}")

class DynamicRichHandler:
    """动态Panel布局处理器"""
    def __init__(self):
        self.layout = Layout()
        self.panels = {}
        self.console = console  # 使用全局console实例
        
        # 设置日志系统
        self.logger = setup_logging()
        
        self.live = Live(
            self.layout,
            console=self.console,
            refresh_per_second=10,
            vertical_overflow="visible"
        )
    
    def add_panel(self, name: str, title: str = None, ratio: int = 1):
        """添加新panel"""
        self.panels[name] = {
            "title": title or name,
            "content": Text(""),
            "ratio": ratio,
            "style": "blue",  # 默认样式
            "input_buffer": "",
            "input_history": []
        }
        self._rebuild_layout()
    
    def update_panel(self, name: str, content, append: bool = False, style: str = None):
        """更新panel内容
        
        Args:
            name: 面板名称
            content: 要显示的内容
            append: 是否追加内容
            style: 内容样式
        """
        if name not in self.panels:
            return
            
        # 处理样式
        if style:
            self.panels[name]["style"] = style
            
        # 创建带样式的Text对象
        if isinstance(content, str):
            content = Text(content, style=style or self.panels[name]["style"])
        elif isinstance(content, Text) and style:
            content.style = style
            
        if append and isinstance(content, (str, Text)):
            old_content = self.panels[name]["content"]
            if isinstance(old_content, Text):
                old_content.append("\n" + str(content))
            else:
                self.panels[name]["content"] = Text(str(old_content) + "\n" + str(content))
        else:
            self.panels[name]["content"] = content
        
        # 记录到日志文件
        if not isinstance(content, Progress):
            self.logger.info(f"[PANEL:{name}] {str(content)}")
            
        self._update_display()
    
    def handle_input(self, input_panel: str, callback=None):
        """处理输入面板的输入"""
        if input_panel not in self.panels:
            return False
            
        try:
            import msvcrt
            if msvcrt.kbhit():
                char = msvcrt.getwch()
                
                # 处理回车键
                if char == '\r':
                    input_text = self.panels[input_panel]["input_buffer"]
                    # 如果当前输入为空，结束输入
                    if not input_text.strip():
                        if callback:
                            return callback("")
                    else:
                        # 有输入内容时，添加到历史记录
                        self.panels[input_panel]["input_history"].append(input_text)
                        self.panels[input_panel]["input_buffer"] = ""
                        
                        # 更新显示
                        history = self.panels[input_panel]["input_history"]
                        content = Text("\n".join(history) + "\n> ", style=self.panels[input_panel]["style"])
                        self.update_panel(input_panel, content)
                        
                        # 调用回调函数
                        if callback:
                            return callback(input_text)
                
                # 处理退格键
                elif char == '\b':
                    if self.panels[input_panel]["input_buffer"]:
                        self.panels[input_panel]["input_buffer"] = self.panels[input_panel]["input_buffer"][:-1]
                        # 更新显示
                        history = self.panels[input_panel]["input_history"]
                        current = self.panels[input_panel]["input_buffer"]
                        content = Text("\n".join(history) + f"\n> {current}", style=self.panels[input_panel]["style"])
                        self.update_panel(input_panel, content)
                
                # 处理其他字符
                else:
                    self.panels[input_panel]["input_buffer"] += char
                    # 更新显示
                    history = self.panels[input_panel]["input_history"]
                    current = self.panels[input_panel]["input_buffer"]
                    content = Text("\n".join(history) + f"\n> {current}", style=self.panels[input_panel]["style"])
                    self.update_panel(input_panel, content)
                
            return True
        except Exception as e:
            self.update_panel("status", f"❌ 输入处理错误: {str(e)}", style="red")
            return False
    
    def _rebuild_layout(self):
        """重建布局"""
        if not self.panels:
            return
            
        layouts = []
        for name, config in self.panels.items():
            layouts.append(Layout(name=name, ratio=config["ratio"]))
            
        self.layout.split(*layouts)
        self._update_display()
    
    def _update_display(self):
        """更新显示"""
        for name, config in self.panels.items():
            try:
                # 获取标题样式
                title = f"[white bold]{config['title']}[/]"
                
                self.layout[name].update(
                    Panel(
                        config["content"],
                        title=title,
                        border_style=config.get("style", "blue"),
                        box=box.ROUNDED,
                        padding=(0, 1)
                    )
                )
            except Exception as e:
                if "update" in self.panels:
                    self.panels["update"]["content"] = Text(f"❌ 更新面板 {name} 时出错: {str(e)}", style="red")
    
    def __enter__(self):
        """进入上下文管理器"""
        self.live.__enter__()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器"""
        self.live.__exit__(exc_type, exc_val, exc_tb)
        
    def start(self):
        """启动显示"""
        self.live.__enter__()
        
    def stop(self):
        """停止显示"""
        self.live.__exit__(None, None, None)

def setup_dynamic_handler():
    """初始化动态Panel处理器"""
    handler = DynamicRichHandler()
    handler.add_panel("main", "主面板", ratio=1)
    handler.add_panel("status", "状态", ratio=1)
    handler.add_panel("log", "日志", ratio=2)
    return handler

def setup_static_handler(layout_config=None):
    """初始化静态Panel处理器"""
    return StaticRichHandler(layout_config)

def setup_progress_handler():
    """初始化进度处理器"""
    return RichProgressHandler()

# 修改RichLoggerManager类
class RichLoggerManager:
    _instance = None
    _handler = None
    _default_layout = {
        "current_stats": {"size": 2, "title": "📊 总体进度", "style": "blue"},
        "current_progress": {"size": 2, "title": "🔄 当前进度", "style": "green"},
        "performance": {"size": 2, "title": "⚡ 性能配置", "style": "yellow"},
        "process": {"size": 3, "title": "📝 处理日志", "style": "cyan"},
        "update": {"size": 3, "title": "ℹ️ 更新日志", "style": "magenta"}
    }
    _current_layout = None

    @classmethod
    def set_layout(cls, layout_config):
        """设置自定义布局"""
        cls._current_layout = layout_config
        if cls._handler is not None:
            # 先关闭旧的handler
            cls.close_handler()
        # 创建新的handler
        cls._handler = RichProgressHandler(layout_config=layout_config)
        try:
            cls._handler.__enter__()
        except Exception as e:
            # print(f"Error initializing handler: {e}")
            cls._handler = None
            raise

    @classmethod
    def get_handler(cls, layout_config=None):
        """获取处理器实例"""
        if cls._handler is None:
            # 使用优先级：传入的布局 > 已设置的自定义布局 > 默认布局
            final_layout = layout_config or cls._current_layout or cls._default_layout
            cls._handler = RichProgressHandler(layout_config=final_layout)
            try:
                cls._handler.__enter__()
            except Exception as e:
                # print(f"Error initializing handler: {e}")
                cls._handler = None
                raise
        return cls._handler

    @classmethod
    def close_handler(cls):
        """关闭处理器"""
        if cls._handler is not None:
            try:
                cls._handler.__exit__(None, None, None)
            except Exception:
                pass
            finally:
                cls._handler = None
                # 不要清除 _current_layout，保持布局配置
                # cls._current_layout = None

# 添加装饰器用于自动获取handler
def with_handler(func):
    def wrapper(*args, **kwargs):
        handler = RichLoggerManager.get_handler()
        return func(handler, *args, **kwargs)
    return wrapper

# 添加便捷的全局函数
@with_handler
def add_log(handler, message, log_type="process"):
    """添加日志的便捷函数"""
    handler.add_log(message, log_type)

@with_handler
def add_success_log(handler, message):
    """添加成功日志的便捷函数"""
    handler.add_success_log(message)

@with_handler
def add_error_log(handler, message):
    """添加错误日志的便捷函数"""
    handler.add_error_log(message)

@with_handler
def add_warning_log(handler, message):
    """添加警告日志的便捷函数"""
    handler.add_warning_log(message)

@with_handler
def add_status_log(handler, message):
    """添加状态日志的便捷函数"""
    handler.add_status_log(message)

@with_handler
def create_progress_task(handler, total, description):
    """创建进度任务的便捷函数"""
    return handler.create_progress_task(total, description)

# 修改现有的get_demo_handler和close_demo_handler函数
def get_demo_handler():
    """获取全局演示处理器"""
    return RichLoggerManager.get_handler()

def close_demo_handler():
    """关闭全局演示处理器"""
    RichLoggerManager.close_handler()

# 修改demo函数展示新的用法
def demo_standard_usage():
    """演示标准用法"""
    print("日志将被保存在 D:/1VSCODE/1ehv/logs/rich_logger_demo/ 目录下")
    
    # 创建自定义布局配置
    custom_layout = {
        "test_panel": {"ratio": 2, "title": "🔍 测试面板", "style": "cyan"},
        "custom_stats": {"ratio": 2, "title": "📊 自定义统计", "style": "yellow"},
        "main_log": {"ratio": 3, "title": "📝 主要日志", "style": "green"},
        "debug_log": {"ratio": 3, "title": "🐛 调试日志", "style": "blue"}
    }
    
    # 设置自定义布局
    set_layout(custom_layout)
    
    # 使用 log_panel 更新各个面板
    log_panel("test_panel", "这是测试面板的内容")
    log_panel("custom_stats", "这是自定义统计面板的内容")
    log_panel("main_log", "这是主要日志面板的内容")
    log_panel("debug_log", "这是调试日志面板的内容")
    
    # 测试动态添加新面板
    log_panel("dynamic_panel", "这是动态创建的新面板")
    
    # 测试更新已存在的面板
    time.sleep(1)
    log_panel("test_panel", "更新测试面板的内容")
    
    # 测试追加内容
    time.sleep(1)
    log_panel("main_log", "追加新的日志内容1")
    time.sleep(1)
    log_panel("main_log", "追加新的日志内容2")
    
    # 测试不同类型的日志
    time.sleep(1)
    log_panel("debug_log", "✅ 成功信息")
    time.sleep(1)
    log_panel("debug_log", "❌ 错误信息")
    time.sleep(1)
    log_panel("debug_log", "⚠️ 警告信息")
    
    # 等待一段时间以便观察结果
    time.sleep(3)

class RichLoggerContext:
    """
    Rich Logger的上下文管理器，用于自动管理handler的生命周期
    
    Example:
        with RichLoggerContext():
            update_panel_log("process_log", "正在处理...")
            update_panel_log("update_log", "✅ 完成")
    """
    def __enter__(self):
        return RichLoggerManager.get_handler()
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        RichLoggerManager.close_handler()

def demo_dynamic_input():
    """演示动态输入面板"""
    handler = DynamicRichHandler()
    
    # 添加面板
    handler.add_panel("input", "📝 输入", ratio=2)
    handler.add_panel("output", "📤 输出", ratio=2)
    handler.add_panel("status", "ℹ️ 状态", ratio=1)
    
    # 初始化输入面板
    handler.update_panel("input", "> ", style="bold cyan")
    handler.update_panel("status", "✨ 系统就绪，请输入内容 (输入'exit'退出)", style="green")
    
    def handle_input(text):
        if text.lower() == 'exit':
            handler.update_panel("status", "👋 正在退出...", style="yellow")
            return False
        handler.update_panel("output", f"📥 收到输入: {text}", style="green")
        handler.update_panel("status", "✅ 输入已处理", style="green")
        return True
    
    with handler:
        try:
            while True:
                if not handler.handle_input("input", handle_input):
                    break
                time.sleep(0.01)  # 避免CPU占用过高
        except KeyboardInterrupt:
            handler.update_panel("status", "⚠️ 用户中断", style="yellow")
        finally:
            time.sleep(1)  # 让用户看到最后的状态

def get_multiline_input(prompt="请输入内容（输入空行结束）:", title="📝 输入"):
    """获取多行输入
    
    Args:
        prompt: 输入提示
        title: 面板标题
        
    Returns:
        list: 输入的行列表
    """
    handler = DynamicRichHandler()
    
    # 添加面板
    handler.add_panel("input", title, ratio=3)
    handler.add_panel("status", "ℹ️ 状态", ratio=1)
    
    # 初始化状态
    input_lines = []
    finished = False
    cursor_visible = True
    last_cursor_time = time.time()
    cursor_blink_interval = 0.5  # 光标闪烁间隔（秒）
    
    def update_input_display():
        # 构建显示内容
        content = Text()
        content.append(f"{prompt}\n\n", style="cyan")
        
        # 显示已输入的行
        for i, line in enumerate(input_lines, 1):
            content.append(f"[{i}] ", style="bright_black")
            content.append(f"{line}\n", style="white")
        
        # 显示当前行提示
        content.append(f"[{len(input_lines) + 1}] ", style="bright_black")
        current_input = handler.panels["input"].get("input_buffer", "")
        content.append(current_input)
        
        # 添加闪烁光标
        if cursor_visible:
            content.append("▌", style="white")
        else:
            content.append(" ")
            
        # 添加下一行提示
        content.append("\n\n直接按回车结束输入", style="bright_black")
        
        handler.update_panel("input", content)
    
    def handle_input(text):
        nonlocal finished
        current_input = handler.panels["input"].get("input_buffer", "")
        
        # 如果当前输入为空且按下回车，结束输入
        if not current_input and text == "":
            finished = True
            handler.update_panel("status", "👋 输入完成", style="yellow")
            return False
            
        # 如果有输入内容，添加到历史记录
        if text:
            input_lines.append(text)
            handler.update_panel("status", f"✅ 已输入 {len(input_lines)} 行", style="green")
        return True
    
    with handler:
        try:
            while not finished:
                # 处理光标闪烁
                current_time = time.time()
                if current_time - last_cursor_time >= cursor_blink_interval:
                    cursor_visible = not cursor_visible
                    last_cursor_time = current_time
                    update_input_display()
                
                # 处理输入
                if not handler.handle_input("input", handle_input):
                    if not finished:  # 如果不是因为空行退出
                        break
                
                # 更新显示
                update_input_display()
                time.sleep(0.01)  # 避免CPU占用过高
                
        except KeyboardInterrupt:
            handler.update_panel("status", "⚠️ 用户中断", style="yellow")
        finally:
            time.sleep(0.5)  # 让用户看到最后的状态
            
    return input_lines

def demo_multiline_input():
    """演示多行输入功能"""
    print("演示多行输入功能:")
    
    # 测试基本输入
    print("\n1. 基本输入测试")
    lines = get_multiline_input(
        prompt="请输入测试内容（每行一个，输入空行结束）:",
        title="📝 基本输入测试"
    )
    print(f"收到输入: {lines}")
    
    # 测试带提示的输入

    
def refresh_rate_test():
    """专门测试不同刷新率参数的组合效果"""
    test_cases = [
        {"interval": 0.1, "live_rate": 15},  # 高频组合
        {"interval": 0.2, "live_rate": 12},  # 平衡组合
        {"interval": 0.3, "live_rate": 10},  # 低频组合
        {"interval": 0.15, "live_rate": 15}, # 自定义组合
    ]

    for case in test_cases:
        # 使用上下文管理器确保资源清理
        with RichLoggerContext():
            handler = RichLoggerManager.get_handler()
            
            # 显示当前测试参数
            log_panel("current_stats", 
                Text.from_markup(
                    f"[bold]正在测试参数组合:[/]\n"
                    f"🔄 刷新间隔: [cyan]{case['interval']}s[/]\n"
                    f"📈 Live刷新率: [green]{case['live_rate']}Hz[/]"
                )
            )
            
            # 修改核心参数（需要临时访问受保护属性）
            handler.log_manager.refresh_interval = case['interval']
            handler.live.refresh_per_second = case['live_rate']
            
            # 创建模拟进度条
            total_files = random.randint(5, 15)
            task_id = handler.create_progress_task(total_files, "模拟文件处理")
            
            # 运行测试循环
            start_time = time.time()
            while time.time() - start_time < 10:  # 每个组合测试10秒
                # 更新进度条
                handler.progress.update(task_id, advance=0.1)
                
                # 生成随机日志
                log_type = random.choice(["process", "success", "error", "warning"])
                msg = f"模拟日志 {datetime.now().strftime('%H:%M:%S')}"
                
                if log_type == "success":
                    handler.add_success_log(f"✅ {msg}")
                elif log_type == "error":
                    handler.add_error_log(f"❌ {msg}")
                elif log_type == "warning":
                    handler.add_warning_log(f"⚠️ {msg}")
                else:
                    handler.add_log(f"ℹ️ {msg}")
                
                # 随机休眠模拟真实操作
                time.sleep(random.uniform(0.05, 0.2))
                
                # 每3秒更新统计面板
                if int(time.time() - start_time) % 3 == 0:
                    log_panel(
                        "current_stats",
                        Text.from_markup(
                            f"[bold]当前参数组合:[/]\n"
                            f"🕒 运行时间: [yellow]{int(time.time() - start_time)}s[/]\n"
                            f"📊 处理进度: [cyan]{handler.progress.tasks[0].completed:.1f}[/]/[green]{total_files}[/]"
                        )
                    )

            # 清理当前测试
            handler.progress.stop()
            RichLoggerManager.close_handler()
            time.sleep(1)  # 间隔避免闪烁

if __name__ == "__main__":
    # 运行多行输入演示
    # demo_multiline_input()
    # demo_standard_usage()
    # 运行测试
    refresh_rate_test()

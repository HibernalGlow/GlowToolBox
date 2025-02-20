"""
使用说明:
1. 导入和初始化:
   ```python
   from tui.textual_logger import TextualLoggerManager
   注意插入时机，不要干扰输入
   # 定义布局配置
   TEXTUAL_LAYOUT = {
       "current_stats": {  # 面板名称，用于日志定位
           "ratio": 2,     # 面板高度比例
           "title": "📊 总体进度",  # 面板标题
           "style": "yellow"  # 面板样式颜色
       },
       "current_progress": {
           "ratio": 2,
           "title": "🔄 当前进度",
           "style": "cyan"
       },
       # ... 更多面板
   }
   
   # 初始化布局
   TextualLoggerManager.set_layout(TEXTUAL_LAYOUT)
   ```

2. 日志输出格式:
   - 普通日志: logging.info("消息内容")
   - 定向面板: logging.info("[#面板名]消息内容")
尽可能在一行输出完所有信息

3. 常用面板设置:
   - current_stats: 总体统计信息
   - current_progress: 当前处理进度
   - process_log: 处理过程日志
   - update_log: 更新状态日志

4. 样式颜色选项:
   - 基础色系:
     * yellow: 黄色
     * cyan: 青色
     * magenta: 品红
     * blue: 蓝色
     * green: 绿色
     * red: 红色
   - 浅色系扩展:
     * lightblue: 浅蓝
     * lightgreen: 浅绿
     * lightcyan: 浅青
     * lightmagenta: 浅品红
     * lightyellow: 浅黄
   - 灰色系:
     * white: 白
     * light_gray: 浅灰
     * dark_gray: 深灰
   - 自定义颜色: 可以直接使用CSS颜色名称或十六进制值，如 "#a8c8ff"
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, Label, Footer, TabbedContent, TabPane, Collapsible, Header
from textual.reactive import reactive
from textual import log, work
from typing import Dict, Optional, List
import threading
import time
from datetime import datetime
import logging
import asyncio
import os
import sys
import signal
import psutil
import re
from dataclasses import dataclass, field

@dataclass
class CPUInfo:
    usage: float = 0.0  # 仅保留CPU使用率

@dataclass
class DiskIOInfo:
    read_speed: float = 0.0  # 读取速度 (MB/s)
    write_speed: float = 0.0  # 写入速度 (MB/s)
    read_bytes: int = 0  # 总读取字节数
    write_bytes: int = 0  # 总写入字节数

@dataclass
class SystemStatus:
    cpu: CPUInfo = field(default_factory=CPUInfo)
    memory_usage: float = 0.0
    disk_io: DiskIOInfo = field(default_factory=DiskIOInfo)
    last_update: datetime = field(default_factory=datetime.now)

class TextualLoggerManager:
    """Textual日志管理器，支持动态面板和日志劫持"""
    
    _instance = None
    _app = None
    _default_layout = {
        "current_stats": {"ratio": 2, "title": "📊 总体进度", "style": "yellow"},
        "current_progress": {"ratio": 2, "title": "🔄 当前进度", "style": "cyan"},
        "performance": {"ratio": 2, "title": "⚡ 性能配置", "style": "green"},
        "process": {"ratio": 3, "title": "📝 处理日志", "style": "magenta"},
        "update": {"ratio": 2, "title": "ℹ️ 更新日志", "style": "blue"}
    }
    
    @classmethod
    def set_layout(cls, layout_config=None):
        """设置日志布局并启动应用
        
        Args:
            layout_config: 布局配置字典，格式如下：
            {
                "panel_name": {
                    "size": int,  # 面板大小
                    "title": str,  # 面板标题
                    "style": str   # 面板样式
                }
            }
        """
        # 使用默认布局或自定义布局
        final_layout = layout_config or cls._default_layout
        
        # 创建应用实例
        if cls._app is None:
            cls._app = TextualLogger(final_layout)
            
            # 配置根日志记录器
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.DEBUG)  # 改为使用调用方的日志级别

            # 仅移除Textual自己的处理器（如果存在）
            for handler in root_logger.handlers[:]:
                if isinstance(handler, TextualLogHandler):
                    root_logger.removeHandler(handler)

            # 添加Textual处理器（保留调用方已有的处理器）
            textual_handler = TextualLogHandler(cls._app)
            textual_handler.setFormatter(logging.Formatter('%(message)s'))
            textual_handler.setLevel(logging.INFO)  # 设置适当级别
            root_logger.addHandler(textual_handler)
            
            # 异步运行应用
            async def run_app():
                await cls._app.run_async()
            
            # 在新线程中运行应用
            import threading
            app_thread = threading.Thread(target=lambda: asyncio.run(run_app()))
            app_thread.daemon = True
            app_thread.start()
            
            # 等待应用初始化完成
            time.sleep(0.5)
            
        return cls._app

class TextualLogHandler(logging.Handler):
    """Textual日志处理器，用于劫持日志输出"""
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.path_regex = re.compile(r'([A-Za-z]:\\[^\s]+|/([^\s/]+/){2,}[^\s/]+)')  # 匹配Windows和Unix路径
        
    def _truncate_path(self, path: str, max_length: int = 35) -> str:
        """路径截断处理（保证最后一个层级完整）"""
        if len(path) <= max_length:
            return path
            
        # 分解路径为组成部分
        sep = '/' if '/' in path else '\\'
        parts = path.split(sep)
        drive = parts[0] + sep if sep == '\\' and ':' in parts[0] else ''  # 保留Windows驱动器
        
        # 分离最后一个层级（文件/文件夹）
        if len(parts) < 2:
            return path[:max_length]  # 无法分割时直接截断
            
        last_part = parts[-1]
        remaining_length = max_length - len(last_part) - 4  # 保留空间给...和分隔符
        
        if remaining_length <= 0:
            # 空间不足时强制显示最后部分
            return f"...{sep}{last_part}"[-max_length:]
            
        # 构建前缀部分
        prefix = sep.join(parts[:-1])
        if len(prefix) > remaining_length:
            # 需要截断前缀部分
            prefix_parts = []
            current_len = 0
            for part in parts[:-1]:
                if current_len + len(part) + 1 <= remaining_length:
                    prefix_parts.append(part)
                    current_len += len(part) + 1
                else:
                    break
            if prefix_parts:
                return f"{sep.join(prefix_parts)}...{sep}{last_part}"
            return f"...{sep}{last_part}"
            
        return f"{prefix}{sep}{last_part}"

    def emit(self, record):
        """处理日志记录"""
        try:
            msg = self.format(record)
            
            # 路径截断处理
            msg = self.path_regex.sub(
                lambda m: self._truncate_path(m.group()), 
                msg
            )
            
            # 修正分组索引错误
            progress_match = re.match(r'^\[@(\w+)\](.*)$', msg)  # 简化正则
            normal_match = re.match(r'^\[#(\w+)\](.*)$', msg)    # 简化正则
            
            if progress_match:
                panel_name = progress_match.group(1)
                content = progress_match.group(2).strip()  # 直接取第二个分组
                self.app.update_panel(panel_name, content)
                
            elif normal_match:
                panel_name = normal_match.group(1)
                content = normal_match.group(2).strip()  # 直接取第二个分组
                if record.levelno >= logging.ERROR:
                    content = f"❌ {content}"
                elif record.levelno >= logging.WARNING:
                    content = f"⚠️ {content}"
                self.app.update_panel(panel_name, content)
                
            else:
                if record.levelno >= logging.ERROR:
                    self.app.update_panel("update", f"❌ {msg}")
                elif record.levelno >= logging.WARNING:
                    self.app.update_panel("update", f"⚠️ {msg}")
                else:
                    self.app.update_panel("update", msg)
                
        except Exception:
            self.handleError(record)

    def _handle_progress_message(self, panel_name: str, content: str):
        """专用进度条处理（无图标添加）"""
        self.app.update_panel(panel_name, content)

    def _handle_normal_message(self, panel_name: str, content: str, record: logging.LogRecord):
        """普通消息处理（添加状态图标）"""
        if record.levelno >= logging.ERROR:
            content = f"❌ {content}"
        elif record.levelno >= logging.WARNING:
            content = f"⚠️ {content}"
        self.app.update_panel(panel_name, content)

    def _handle_default_message(self, msg: str, record: logging.LogRecord):
        """处理未指定面板的消息"""
        if record.levelno >= logging.ERROR:
            self.app.update_panel("update", f"❌ {msg}")
        elif record.levelno >= logging.WARNING:
            self.app.update_panel("update", f"⚠️ {msg}")
        else:
            self.app.update_panel("update", msg)

class LogPanel(Static):
    """自定义日志面板组件，支持固定行数显示和进度条"""
    
    content = reactive(list)
    
    def __init__(self, name: str, title: str, style: str = "white", ratio: int = 1, **kwargs):
        super().__init__(**kwargs)
        self.panel_name = name
        self.title = title
        self.base_style = style
        self.ratio = ratio
        self.content = []
        self.max_lines = 100  # 设置最大缓存行数
        self._cached_size = None
        self._cached_visible_lines = None
        self._cached_panel_height = None
        self.progress_bars = {}  # 存储进度条信息 {msg: (percentage, position, is_completed)}
        self.progress_positions = {}  # 存储进度条位置 {position: msg}
        self.next_progress_position = 0  # 下一个进度条位置

    def _create_progress_bar(self, width: int, percentage: float, fraction: str = None, fraction_format: str = None) -> str:
        """创建带简单ASCII进度条的文本显示"""
        bar_width = max(10, width - 20)
        filled = int(round(bar_width * percentage / 100))
        
        # 根据完成状态使用不同字符
        if percentage >= 100:
            progress_bar = "█" * bar_width + " ✅"  # 完成时显示对勾
        else:
            progress_bar = "█" * filled + "░" * (bar_width - filled)
        
        # 组合内容
        if fraction_format:
            return f"{progress_bar} {fraction_format} {percentage:.1f}%"
        return f"{progress_bar} {percentage:.1f}%"

    def append(self, text: str) -> None:
        """追加内容并保持在最大行数限制内"""
        # 检查是否是进度条更新
        if self._is_progress_message(text):
            self._handle_progress_message(text)
        else:
            self._handle_normal_message(text)
            
        # 更新显示
        self._update_display()
        
        # 无论是否有进度条，都确保面板定期刷新
        if not hasattr(self, '_refresh_timer'):
            self._refresh_timer = self.set_interval(0.1, self._periodic_refresh)
            
        self.scroll_end()

    def _periodic_refresh(self) -> None:
        """定期刷新面板内容"""
        self._update_display()
        self.refresh()

    def on_unmount(self) -> None:
        """组件卸载时清理定时器"""
        if hasattr(self, '_refresh_timer'):
            self._refresh_timer.stop()

    def _is_progress_message(self, text: str) -> bool:
        """检查是否为进度条消息"""
        # 定义正则表达式组件
        PREFIX_PATTERN = r'([^%]*?(?=\s*(?:\[|\(|\d+(?:\.\d+)?%|\s*$)))'
        BRACKETED_FRACTION = r'(?:(\(|\[)(\d+/\d+)[\)\]])'
        PLAIN_FRACTION = r'(\d+/\d+)'
        FRACTION_PART = fr'\s*(?:{BRACKETED_FRACTION}|\s*{PLAIN_FRACTION})?'
        PERCENTAGE = r'(\d+(?:\.\d+)?)%'
        FRACTION_PERCENTAGE = r'\((\d+)/(\d+)\)'
        PERCENTAGE_PART = fr'\s*(?:{PERCENTAGE}|{FRACTION_PERCENTAGE})$'
        
        PROGRESS_PATTERN = fr'{PREFIX_PATTERN}{FRACTION_PART}{PERCENTAGE_PART}'
        return bool(re.match(PROGRESS_PATTERN, text))

    def _handle_progress_message(self, text: str) -> None:
        """处理进度条消息"""
        progress_info = self._parse_progress_info(text)
        if not progress_info:
            return
            
        msg_prefix, percentage, fraction, fraction_format = progress_info
        self._update_progress_bars(msg_prefix, percentage, fraction, fraction_format)

    def _parse_progress_info(self, text: str) -> Optional[tuple]:
        """解析进度条信息"""
        # 使用与_is_progress_message相同的正则表达式
        PREFIX_PATTERN = r'([^%]*?(?=\s*(?:\[|\(|\d+(?:\.\d+)?%|\s*$)))'
        BRACKETED_FRACTION = r'(?:(\(|\[)(\d+/\d+)[\)\]])'
        PLAIN_FRACTION = r'(\d+/\d+)'
        FRACTION_PART = fr'\s*(?:{BRACKETED_FRACTION}|\s*{PLAIN_FRACTION})?'
        PERCENTAGE = r'(\d+(?:\.\d+)?)%'
        FRACTION_PERCENTAGE = r'\((\d+)/(\d+)\)'
        PERCENTAGE_PART = fr'\s*(?:{PERCENTAGE}|{FRACTION_PERCENTAGE})$'
        
        PROGRESS_PATTERN = fr'{PREFIX_PATTERN}{FRACTION_PART}{PERCENTAGE_PART}'
        
        match = re.match(PROGRESS_PATTERN, text)
        if not match:
            return None
            
        msg_prefix = match.group(1).strip()
        percentage = None
        fraction = None
        fraction_format = None
        
        if match.group(2):  # 有括号
            bracket = match.group(2)
            fraction_display = match.group(3)
            fraction_format = f"{bracket}{fraction_display}{')'if bracket=='('else']'}"
        elif match.group(4):  # 无括号的分数
            fraction_display = match.group(4)
            fraction_format = fraction_display
        
        if match.group(5):  # 百分比格式
            percentage = float(match.group(5))
        else:  # 分数格式
            current = int(match.group(6))
            total = int(match.group(7))
            percentage = current * 100.0 / total
            fraction = f"{current}/{total}"
            
        return msg_prefix, percentage, fraction, fraction_format

    def _update_progress_bars(self, msg_prefix: str, percentage: float, 
                            fraction: Optional[str], fraction_format: Optional[str]) -> None:
        """更新进度条信息"""
        if msg_prefix in self.progress_bars:
            position = self.progress_bars[msg_prefix][1]
        else:
            position = self._get_available_position()
            
        is_completed = percentage >= 100
        self.progress_bars[msg_prefix] = (percentage, position, is_completed, fraction, fraction_format)
        self.progress_positions[position] = msg_prefix

    def _get_available_position(self) -> int:
        """获取可用的进度条位置"""
        # 首先检查是否有已完成的进度条位置
        for pos, msg in list(self.progress_positions.items()):
            if msg in self.progress_bars and self.progress_bars[msg][2]:
                del self.progress_bars[msg]
                del self.progress_positions[pos]
                return pos
                
        # 如果没有已完成的位置，检查是否需要替换最旧的位置
        if self.progress_positions:
            oldest_position = min(self.progress_positions.keys())
            oldest_msg = self.progress_positions[oldest_position]
            del self.progress_bars[oldest_msg]
            del self.progress_positions[oldest_position]
            return oldest_position
            
        # 如果没有任何位置，创建新位置
        position = self.next_progress_position
        self.next_progress_position += 1
        return position

    def _handle_normal_message(self, text: str) -> None:
        """处理普通消息"""
        cleaned_msg = re.sub(r'^(\S+\s+)', '', text)
        start_part = cleaned_msg[:4]

        if self.content and len(start_part) >= 4:
            last_msg = self.content[-1]
            last_cleaned = re.sub(r'^(\S+\s+)', '', last_msg)
            last_start = last_cleaned[:4]

            if start_part == last_start:
                self.content[-1] = text  # 合并相似消息
            else:
                self.content.append(text)
        else:
            self.content.append(text)

        # 保持内容在最大行数限制内
        if len(self.content) > self.max_lines:
            self.content = self.content[-self.max_lines:]

    def _update_display(self) -> None:
        """更新显示内容"""
        # 更新面板尺寸缓存
        self._update_size_cache()
        
        # 准备显示内容
        display_content = []
        
        # 添加进度条
        display_content.extend(self._get_progress_bar_content())
        
        # 添加普通消息
        display_content.extend(self._get_normal_message_content())
        
        # 更新渲染
        self.update_render("\n".join(display_content))

    def _update_size_cache(self) -> None:
        """更新尺寸缓存"""
        current_size = self.app.console.size if self.app else None
        if current_size != self._cached_size:
            self._cached_size = current_size
            self._cached_panel_height = self._calculate_panel_height()
            self._cached_visible_lines = self._cached_panel_height - 2 if self._cached_panel_height > 2 else 1

    def _get_progress_bar_content(self) -> List[str]:
        """获取进度条显示内容"""
        content = []
        console_width = self.app.console.width if self.app else 80
        
        for pos in sorted(self.progress_positions.keys()):
            msg_prefix = self.progress_positions[pos]
            if msg_prefix in self.progress_bars:
                percentage, _, _, fraction, fraction_format = self.progress_bars[msg_prefix]
                progress_bar = self._create_progress_bar(
                    console_width - len(msg_prefix) - 4,
                    percentage,
                    fraction,
                    fraction_format
                )
                content.append(f"{msg_prefix}{progress_bar}")
        return content

    def _get_normal_message_content(self) -> List[str]:
        """获取普通消息显示内容"""
        content = []
        remaining_lines = max(0, (self._cached_visible_lines or 1) - len(self.progress_positions))
        
        if remaining_lines > 0:
            messages = list(reversed(self.content[-remaining_lines:]))
            for msg in messages:
                if self.app and self.app.console.width > 4:
                    content.append(f"- {msg}")
                else:
                    content.append(f"- {msg}")
                    
        return list(reversed(content))  # 恢复正确顺序

    def _calculate_panel_height(self) -> int:
        """计算面板应占用的高度"""
        if not self.app:
            return 3
            
        # 获取终端高度和面板数量（使用console的尺寸）
        terminal_height = self.app.console.size.height  # 修改为使用console的尺寸
        panels = list(self.app.query(LogPanel))
        
        # 计算可用高度（考虑标题栏和底部栏）
        available_height = terminal_height - 2  # 只减去Header和Footer
        
        # 计算所有面板的ratio总和
        total_ratio = sum(panel.ratio for panel in panels)
        
        # 计算每个ratio单位对应的高度（保留小数）
        unit_height = available_height / total_ratio
        
        # 对于除最后一个面板外的所有面板，向下取整
        is_last_panel = panels[-1] == self
        if not is_last_panel:
            base_lines = 3 # 最小显示行数
            panel_height = max(base_lines, int(unit_height * self.ratio))
            self._cached_visible_lines = panel_height - 2  # 增加可见行数
        else:
            # 最后一个面板获取剩余所有空间
            used_height = sum(max(3, int(unit_height * p.ratio)) for p in panels[:-1])
            panel_height = max(3, available_height - used_height)
        
        return panel_height
        
    def update_render(self, content: str) -> None:
        """普通文本渲染"""
        self.styles.border = ("heavy", self.base_style)
        self.styles.color = self.base_style  # 设置面板文本颜色
        self.border_title = f"{self.title}"
        self.border_subtitle = f"{self.panel_name}"
        super().update(content)

    def on_mount(self) -> None:
        """当组件被挂载时调用"""
        # 设置定时刷新，用于进度条动画
        self.set_interval(0.1, self.refresh)

class SystemStatusFooter(Footer):
    """自定义底部状态栏"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status = SystemStatus()
        self._last_io_time = time.time()
        
    def on_mount(self) -> None:
        self.set_interval(2, self.update_status)
        
    def update_status(self) -> None:
        """更新系统状态信息"""
        try:
            import psutil
            
            # 仅更新CPU使用率和内存
            self.status.cpu.usage = psutil.cpu_percent()
            self.status.memory_usage = psutil.virtual_memory().percent
            
            # 磁盘IO
            current_time = time.time()
            disk_io = psutil.disk_io_counters()
            if disk_io:
                time_diff = current_time - self._last_io_time
                if time_diff > 0:
                    read_speed = (disk_io.read_bytes - self.status.disk_io.read_bytes) / time_diff / 1024 / 1024
                    write_speed = (disk_io.write_bytes - self.status.disk_io.write_bytes) / time_diff / 1024 / 1024
                    
                    self.status.disk_io = DiskIOInfo(
                        read_speed=read_speed,
                        write_speed=write_speed,
                        read_bytes=disk_io.read_bytes,
                        write_bytes=disk_io.write_bytes
                    )
                
                self._last_io_time = current_time
                
        except ImportError:
            self.status = SystemStatus()
            
        self.status.last_update = datetime.now()
        self.refresh()
        
    def render(self) -> str:
        """简化后的状态显示"""
        status = (
            f"CPU: {self.status.cpu.usage:.1f}% | "
            f"内存: {self.status.memory_usage:.1f}% | "
            f"IO: R:{self.status.disk_io.read_speed:.1f}MB/s W:{self.status.disk_io.write_speed:.1f}MB/s"
        )
        return status

class TextualLogger(App):
    """Textual日志应用"""
    
    CSS = """
    #main-container {
        layout: vertical;
        width: 100%;
        height: 100%;
        background: $surface;
        padding: 0;
    }
    
    LogPanel {
        width: 100%;
        min-height: 3;
        height: auto;
        background: $surface;
        padding: 0 1;
        margin: 0;
        overflow: hidden;
    }
    
    LogPanel:focus {
        border: double $accent;
    }
    
    Static {
        width: 100%;
        height: auto;
        overflow: hidden;
    }
    
    Header {
        height: 1;
        padding: 0;
        margin: 0;
        background: $surface;
        color: $text;
    }
    
    Footer {
        height: 1;
        padding: 0;
        margin: 0;
        background: $surface;
        color: $text;
    }
    
    /* 调整底部栏样式 */
    SystemStatusFooter {
        width: 100%;
        content-align: center middle;
        padding: 0 1;
        background: $surface;
        color: $text;
    }
    """
    
    BINDINGS = [
        ("d", "toggle_dark", "主题"),  # 简化快捷键提示
        ("q", "quit", "退出")
    ]
    
    def __init__(self, layout_config: Dict):
        super().__init__()
        self.layout_config = layout_config
        self.panels: Dict[str, LogPanel] = {}
        self._pending_updates = []
        # 设置默认主题为tokyo-night
        self.theme = "tokyo-night"
        # 获取调用脚本的名称
        import sys
        self.script_name = os.path.basename(sys.argv[0])
        self.start_time = datetime.now()
        
    def compose(self) -> ComposeResult:
        """初始化界面布局"""
        yield Header(show_clock=True)
        with Container(id="main-container"):
            for name, config in self.layout_config.items():
                panel = LogPanel(
                    name=name,
                    title=config.get("title", name),
                    style=config.get("style", "white"),
                    ratio=config.get("ratio", 1),
                    id=f"panel-{name}"
                )
                self.panels[name] = panel
                yield panel
        yield SystemStatusFooter()  # 使用自定义底部栏
    
    def action_focus_next(self) -> None:
        """焦点移到下一个面板"""
        current = self.focused
        panels = list(self.query(LogPanel))
        if current in panels:
            idx = panels.index(current)
            next_idx = (idx + 1) % len(panels)
            panels[next_idx].focus()
    
    def action_focus_previous(self) -> None:
        """焦点移到上一个面板"""
        current = self.focused
        panels = list(self.query(LogPanel))
        if current in panels:
            idx = panels.index(current)
            prev_idx = (idx - 1) % len(panels)
            panels[prev_idx].focus()
    
    def action_toggle_dark(self) -> None:
        """切换暗色/亮色主题"""
        if self.theme == "textual-light":
            self.theme = "textual-dark"
        else:
            self.theme = "textual-light"
    
    def on_mount(self) -> None:
        """初始化"""
        self.title = self.script_name  # 设置初始标题为脚本名称
        self.set_interval(1, self.update_timer)  # 添加定时器更新
        
        # 处理待处理的更新
        for name, content in self._pending_updates:
            self._do_update(name, content)
        self._pending_updates.clear()
        
        # 默认聚焦第一个面板
        first_panel = next(iter(self.panels.values()), None)
        if first_panel:
            first_panel.focus()
    
    def create_panel(self, name: str, config: Dict) -> None:
        """动态创建新面板"""
        if name not in self.panels:
            panel = LogPanel(
                name=name,
                title=config.get("title", name),
                style=config.get("style", "white"),
                ratio=config.get("ratio", 1),  # 使用ratio代替size
                id=f"panel-{name}"
            )
            self.panels[name] = panel
            # 获取主容器并添加新面板
            main_container = self.query_one("#main-container")
            main_container.mount(panel)
            # 通知用户
            self.notify(f"已创建新面板: {name}")
            return panel
        return self.panels[name]

    def update_panel(self, name: str, content: str) -> None:
        """更新或创建面板内容"""
        if not self.is_mounted:
            self._pending_updates.append((name, content))
            return
            
        # 如果面板不存在，创建新面板
        if name not in self.panels:
            self.create_panel(name, {
                "title": name,
                "style": "cyan",  # 新面板默认使用青色
                "ratio": 1  # 默认ratio为1
            })
        
        self._do_update(name, content)
    
    def _do_update(self, name: str, content: str) -> None:
        """执行实际的更新操作"""
        try:
            if name in self.panels:
                self.panels[name].append(content)
                self.panels[name].scroll_end()
        except Exception as e:
            print(f"Error updating panel: {e}")

    def update_timer(self) -> None:
        """更新运行时间显示"""
        elapsed = datetime.now() - self.start_time
        hours, remainder = divmod(elapsed.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
        self.title = f"{self.script_name} [{time_str}]"  # 在标题中添加计时器

if __name__ == "__main__":
    # 演示使用方法
    TextualLoggerManager.set_layout({
        "system": {"title": "🖥️ 系统状态", "style": "lightgreen", "ratio": 2},
        "error": {"title": "❌ 错误检查", "style": "lightpink", "ratio": 2},
        "info": {"title": "ℹ️ 信息日志", "style": "lightblue", "ratio": 3},
    })
    
    # 使用标准logging发送日志
    logger = logging.getLogger()
    
    def demo_logs():
        """演示日志功能"""
        import random
        
        # 等待应用初始化完成
        time.sleep(1)
        
        # 预定义一些演示消息
        system_msgs = [
            # "CPU使用率: {}%",
            "内存使用: {}MB",
            "磁盘空间: {}GB可用"
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
        
        # 进度条测试消息
        progress_tasks = {
            "system": [
                ("系统更新", "普通百分比"),
                ("内存清理", "带括号分数"),
                ("磁盘扫描", "带方括号分数"),
                ("", "普通百分比")  # 测试空任务名
            ],
            "error": [
                ("错误检查", "普通百分比"),
                ("日志分析", "带括号分数"),
                ("问题诊断", "带方括号分数"),
                ("", "带括号分数")  # 测试空任务名
            ],
            "info": [
                ("数据同步", "普通百分比"),
                ("配置更新", "带括号分数"),
                ("缓存优化", "带方括号分数"),
                ("", "带方括号分数")  # 测试空任务名
                
            ]
        }
        
        # 记录每个面板的活动进度条
        active_progress = {
            "system": {},
            "error": {},
            "info": {}
        }
        
        # # 首先测试简单进度条
        # logger.info("[@system]50%")
        # logger.info("[@error](1/2) 50%")
        # logger.info("[@info][1/2] 50%")
        # time.sleep(2)  # 暂停2秒查看效果
        
        while True:
            long_path = "/this/is/a/very/long/path/to/some/file/in/the/system/directory/structure.zip" * 3
            logger.info(f"[#system]访问路径：{long_path}")

            # 系统面板消息
            msg = random.choice(system_msgs)
            value = random.randint(1, 100)
            logger.info(f"[#system]{msg.format(value)}")
            
            # 错误面板消息
            if random.random() < 0.1:  # 10%概率产生错误
                msg = random.choice(error_msgs)
                value = random.randint(1, 5)
                logger.error(f"[#error]{msg.format(value)}")
            
            # 信息面板消息
            msg = random.choice(info_msgs)
            value = random.randint(1000, 9999)
            logger.info(f"[#info]{msg.format(value)}")
            
            # 为每个面板更新进度条
            for panel in [ "error"]:
                # 随机启动新进度条
                if len(active_progress[panel]) < 2 and random.random() < 0.1:  # 10%概率启动新进度条
                    available_tasks = [t for t, _ in progress_tasks[panel] if t not in active_progress[panel]]
                    if available_tasks:
                        task = random.choice(available_tasks)
                        # 获取任务对应的显示格式
                        format_type = next(fmt for t, fmt in progress_tasks[panel] if t == task)
                        active_progress[panel][task] = {"progress": 0, "format": format_type}
                        
                        # 根据格式类型显示初始进度
                        if format_type == "普通百分比":
                            logger.info(f"[@{panel}]{task} 0%")
                        elif format_type == "带括号分数":
                            logger.info(f"[@{panel}]{task} (0/100) 0%")
                        else:  # 带方括号分数
                            logger.info(f"[@{panel}]{task} [0/100] 0%")
                
                # 更新现有进度条
                for task in list(active_progress[panel].keys()):
                    task_info = active_progress[panel][task]
                    progress = task_info["progress"]
                    format_type = task_info["format"]
                    progress += random.randint(1, 5)  # 随机增加进度
                    
                    if progress >= 100:
                        # 完成的进度条保持显示
                        if format_type == "普通百分比":
                            logger.info(f"[@{panel}]{task} 100%")
                        elif format_type == "带括号分数":
                            logger.info(f"[@{panel}]{task} (100/100) 100%")
                        else:  # 带方括号分数
                            logger.info(f"[@{panel}]{task} [100/100] 100%")
                        del active_progress[panel][task]
                    else:
                        # 更新进度
                        task_info["progress"] = progress
                        if format_type == "普通百分比":
                            logger.info(f"[@{panel}]{task} {progress}%")
                        elif format_type == "带括号分数":
                            logger.info(f"[@{panel}]{task} ({progress}/100) {progress}%")
                        else:  # 带方括号分数
                            logger.info(f"[@{panel}]{task} [{progress}/100] {progress}%")
            
            # 控制发送频率
            time.sleep(random.uniform(0.01, 0.02))  # 随机延迟0.3-1.0秒
    
    # 在新线程中运行演示
    demo_thread = threading.Thread(target=demo_logs)
    demo_thread.daemon = True
    demo_thread.start()
    
    # 保持程序运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
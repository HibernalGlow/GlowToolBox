import sys
import logging
import psutil
import re
from datetime import datetime
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QTimer, QThread
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QTextEdit, QLabel, QProgressBar,
                            QSplitter, QTabWidget)
from PyQt5.QtGui import QColor, QFont, QTextCursor

class LogPanel(QWidget):
    """日志显示面板"""
    MAX_LINES = 200
    STYLE_MAP = {
        'yellow': {'base': '#FFD700', 'bg': '#2B2B2B'},
        'cyan': {'base': '#00FFFF', 'bg': '#1F2B2B'},
        'magenta': {'base': '#FF00FF', 'bg': '#2B1F2B'},
        'blue': {'base': '#2196F3', 'bg': '#1F2B3B'},
        'green': {'base': '#00FF00', 'bg': '#1F2B1F'},
        'red': {'base': '#FF5252', 'bg': '#2B1F1F'}
    }

    def __init__(self, name, title, style='cyan', parent=None):
        super().__init__(parent)
        self.name = name
        self.title = title
        self.style = self.STYLE_MAP.get(style, self.STYLE_MAP['cyan'])
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        # 标题栏
        title_bar = QLabel(self.title)
        title_bar.setStyleSheet(f"""
            background: {self.style['base']};
            color: #202020;
            font: bold 12px 'Segoe UI';
            padding: 4px 8px;
            border-radius: 4px 4px 0 0;
        """)
        layout.addWidget(title_bar)

        # 添加真正的进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                height: 6px;
                background: transparent;
                border: 0px;
            }}
            QProgressBar::chunk {{
                background: {self.style['base']};
                border-radius: 3px;
            }}
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # 内容区域
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setStyleSheet(f"""
            background: {self.style['bg']};
            color: {self.style['base']};
            border: 1px solid {self.style['base']}55;
            border-top: none;
            border-radius: 0 0 4px 4px;
            padding: 6px;
            font: 12px 'Consolas';
        """)
        layout.addWidget(self.text_area)

    def append_log(self, message):
        # 处理进度条更新 (格式示例: "[#panel=50] 正在处理")
        if message.startswith('='):
            try:
                value = int(message[1:].split()[0])
                self.progress_bar.setValue(value)
                self.progress_bar.show()
            except:
                self.progress_area.hide()
            return

        # 普通日志
        cursor = self.text_area.textCursor()
        cursor.movePosition(QTextCursor.End)

        # 保持行数限制
        if self.text_area.document().lineCount() > self.MAX_LINES:
            cursor.select(QTextCursor.Document)
            cursor.removeSelectedText()

        # 自动滚动
        self.text_area.ensureCursorVisible()

class SystemMonitor(QWidget):
    """系统监控状态栏"""
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(2000)

    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 4, 10, 4)
        
        self.cpu_bar = QProgressBar()
        self.mem_bar = QProgressBar()
        self.io_label = QLabel()

        for widget in [self.cpu_bar, self.mem_bar, self.io_label]:
            layout.addWidget(widget)

        self.setLayout(layout)
        self.apply_style()

    def apply_style(self):
        style = """
        QProgressBar {
            height: 16px;
            min-width: 120px;
            max-width: 200px;
            text-align: center;
            border: 1px solid #444;
            border-radius: 8px;
            background: #2B2B2B;
            orientation: horizontal;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #2196F3, stop:1 #03A9F4);
            border-radius: 7px;
        }
        QLabel {
            color: #EEE;
            font: 14px 'Segoe UI';
        }
        """
        self.setStyleSheet(style)

    def update_stats(self):
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        io = psutil.disk_io_counters()

        self.cpu_bar.setValue(int(cpu))
        self.mem_bar.setValue(int(mem))
        self.io_label.setText(
            f"📁 Read: {io.read_bytes//1048576}MB "
            f"Write: {io.write_bytes//1048576}MB"
        )

class LogHandler(QObject, logging.Handler):
    log_received = pyqtSignal(str, str)  # (panel, message)

    def __init__(self):
        super().__init__()
        self.setFormatter(logging.Formatter('%(message)s'))
        self.path_regex = re.compile(r'([A-Za-z]:\\[^\s]+|/([^\s/]+/){2,}[^\s/]+)')

    def emit(self, record):
        msg = self.format(record)
        msg = self.path_regex.sub(lambda m: self.truncate_path(m.group()), msg)
        
        # 新解析规则：支持[#panel=]表示进度条
        if match := re.match(r'\[#(\w+)(=?)](.*)', msg):
            panel, is_progress, message = match.groups()
            if is_progress:
                message = f'={message}'  # 添加进度标识
            self.log_received.emit(panel.strip(), message.strip())
        else:
            self.log_received.emit('default', msg)

    def truncate_path(self, path):
        """路径截断处理"""
        if len(path) <= 35:
            return path
        parts = path.replace('\\', '/').split('/')
        return f"{parts[0]}/.../{'/'.join(parts[-2:])}"

class MainWindow(QMainWindow):
    def __init__(self, layout_config):
        super().__init__()
        self.panels = {}
        self.init_ui(layout_config)
        self.setWindowTitle("PyQt Logger")
        self.resize(1000, 600)
        self.apply_dark_theme()

    def init_ui(self, layout_config):
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # 系统监控
        self.monitor = SystemMonitor()
        main_layout.addWidget(self.monitor)

        # 日志面板容器
        splitter = QSplitter(Qt.Vertical)
        for name, config in layout_config.items():
            panel = LogPanel(
                name=name,
                title=config.get('title', name),
                style=config.get('style', 'cyan')
            )
            self.panels[name] = panel
            splitter.addWidget(panel)
        
        main_layout.addWidget(splitter)

        # 日志处理器
        self.handler = LogHandler()
        self.handler.log_received.connect(self.handle_log)
        logging.getLogger().addHandler(self.handler)

    def apply_dark_theme(self):
        self.setStyleSheet("""
        QMainWindow {
            background: #1E1E1E;
        }
        QSplitter::handle {
            background: #333;
            height: 4px;
        }
        """)

    def handle_log(self, panel_name, message):
        if panel := self.panels.get(panel_name):
            panel.append_log(message)
        else:
            # 默认显示在第一个面板
            next(iter(self.panels.values())).append_log(f"[{panel_name}] {message}")

if __name__ == '__main__':
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    
    # 布局配置
    layout_config = {
        "stats": {"title": "📊 实时统计", "style": "yellow"},
        "progress": {"title": "🔄 处理进度", "style": "cyan"},
        "errors": {"title": "❌ 错误日志", "style": "red"},
        "debug": {"title": "🐞 调试信息", "style": "magenta"}
    }
    
    window = MainWindow(layout_config)
    window.show()
    
    # 测试日志
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    def test_logs():
        import random
        panels = list(layout_config.keys())
        while True:
            panel = random.choice(panels)
            msg = f"测试消息 {datetime.now().strftime('%H:%M:%S')}"
            logger.info(f"[#{panel}] {msg}")
            QThread.msleep(100)
    
    log_thread = QThread()
    log_thread.run = test_logs
    log_thread.start()
    
    sys.exit(app.exec_())
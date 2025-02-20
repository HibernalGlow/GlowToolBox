from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QTextEdit, QProgressBar, QHBoxLayout, QLabel)
from PyQt5.QtCore import Qt, QTimer

class QtRichLogger(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EH Visual Logger")
        self._init_ui()
        self.log_queue = []
        
        # 设置更新定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_display)
        self.timer.start(100)  # 100ms刷新间隔

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # 主布局
        layout = QVBoxLayout()
        main_widget.setLayout(layout)
        
        # 统计面板
        self.stats_panel = QTextEdit()
        self.stats_panel.setReadOnly(True)
        layout.addWidget(self.stats_panel, stretch=1)
        
        # 进度条区域
        self.progress_bars = {}
        progress_layout = QVBoxLayout()
        layout.addLayout(progress_layout)
        
        # 日志面板
        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)
        layout.addWidget(self.log_panel, stretch=2)

    def add_log(self, message):
        self.log_queue.append(message)
        
    def update_display(self):
        # 处理日志更新
        while self.log_queue:
            msg = self.log_queue.pop(0)
            self.log_panel.append(msg)
            self.log_panel.verticalScrollBar().setValue(
                self.log_panel.verticalScrollBar().maximum()
            )

if __name__ == "__main__":
    app = QApplication([])
    window = QtRichLogger()
    window.show()
    app.exec_()
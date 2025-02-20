from textual.app import App, ComposeResult
from textual.containers import ScrollableContainer, Vertical, Horizontal
from textual.widgets import (
    Header, 
    Footer,
    DataTable,
    Button,
    Input,
    Label,
    TabbedContent,
    Tab,
    TabPane,
    OptionList,
)
from textual.widgets.option_list import Option
from textual.binding import Binding
from textual.coordinate import Coordinate
from textual.widgets.data_table import RowKey
import json
import os
from pathlib import Path

class CommandEditor(TabPane):
    """命令编辑页签"""
    
    def __init__(self, cmd: dict = None):
        """初始化
        Args:
            cmd: 要编辑的命令配置，如果是新建则为None
        """
        title = f"编辑 - {cmd['name']}" if cmd else "新建命令"
        super().__init__(title)
        self.cmd = cmd

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(classes="input-row"):
                yield Label("名称:")
                yield Input(
                    id="name", 
                    placeholder="输入命令名称",
                    value=self.cmd["name"] if self.cmd else ""
                )
            with Horizontal(classes="input-row"):
                yield Label("命令:")
                yield Input(
                    id="command", 
                    placeholder="输入命令路径",
                    value=self.cmd["command"] if self.cmd else ""
                )
            with Horizontal(classes="input-row"):
                yield Label("参数:")
                yield Input(
                    id="args", 
                    placeholder="输入命令参数",
                    value=self.cmd["args"] if self.cmd else ""
                )
            with Horizontal(id="buttons"):
                yield Button("保存", id="save", variant="primary")
                yield Button("运行", id="run", variant="primary")
                yield Button("删除", id="delete", variant="error")

class CommandRunner(TabPane):
    """命令运行页签"""
    
    def __init__(self):
        super().__init__("运行")

    def compose(self) -> ComposeResult:
        with Vertical():
            yield DataTable(id="commands-table")
            with Horizontal(id="buttons"):
                yield Button("运行", id="run", variant="primary")

class CommandsTUI(App):
    """可配置的命令集合TUI"""
    
    CSS = """
    Screen {
        align: center middle;
    }

    #main-container {
        width: 95%;
        height: 90%;
        layout: horizontal;
        background: $surface;
        border: round $primary;
    }

    #menu {
        width: 30%;
        height: 100%;
        border-right: solid $primary;
        background: $panel;
    }

    OptionList {
        height: 100%;
        border: none;
        background: transparent;
        padding: 1;
    }

    .option-list--option {
        background: $panel;
        color: $text;
        height: 1;
        margin-bottom: 1;
        padding: 0 1;
    }

    .option-list--option:hover {
        background: $primary;
    }

    .option-list--option.-selected {
        background: $accent;
    }

    #content {
        width: 70%;
        height: 100%;
        padding: 1;
    }

    TabbedContent {
        height: 100%;
    }

    Tab {
        color: $text;
        background: $panel;
        padding: 0 2;
    }

    Tab:hover {
        background: $primary;
    }

    Tab.-active {
        background: $accent;
        color: $text;
    }

    TabPane {
        padding: 1;
    }

    .input-row {
        layout: horizontal;
        height: 3;
        margin-bottom: 1;
        align: left middle;
    }

    .input-row Label {
        width: 20%;
        padding: 0 1;
        content-align: right middle;
    }

    .input-row Input {
        width: 80%;
        background: $surface;
        border: none;
        padding: 0 1;
        color: $text;
    }

    .input-row Input:focus {
        border: round $accent;
    }

    Button {
        margin: 0 1;
        min-width: 16;
        background: $primary;
        color: $text;
        border: none;
    }

    Button:hover {
        background: $primary-lighten-2;
    }

    Button.error {
        background: $error;
    }

    Button.error:hover {
        background: $error-lighten-2;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("d", "toggle_dark", "切换主题"),
        Binding("n", "new_command", "新建命令"),
        Binding("delete", "remove_command", "删除命令"),
        Binding("up", "move_up", "上移"),
        Binding("down", "move_down", "下移"),
        Binding("space", "start_drag", "开始拖动"),
    ]

    def __init__(self):
        super().__init__()
        self.config_file = Path.home() / ".ehv_commands.json"
        self.commands = self.load_commands()
        self.dragging = False
        self.drag_row = None

    def load_commands(self) -> list:
        """加载命令配置"""
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def save_commands(self):
        """保存命令配置"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.commands, f, ensure_ascii=False, indent=2)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Horizontal(id="main-container"):
            # 左侧菜单
            with ScrollableContainer(id="menu"):
                yield OptionList(
                    *[Option(cmd["name"], id=str(i)) for i, cmd in enumerate(self.commands)],
                    id="command-list"
                )

            # 右侧内容区
            with ScrollableContainer(id="content"):
                with TabbedContent(id="tab-content"):
                    yield CommandEditor()
                    yield CommandRunner()

        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """处理命令选择"""
        cmd_idx = int(event.option.id)
        cmd = self.commands[cmd_idx]
        
        # 更新编辑器内容
        editor = self.query_one(CommandEditor)
        editor.query_one("#name").value = cmd["name"]
        editor.query_one("#command").value = cmd["command"]
        editor.query_one("#args").value = cmd["args"]
        editor.cmd = cmd

        # 更新表格选中行
        table = self.query_one("#commands-table")
        table.cursor_row = cmd_idx

    def action_start_drag(self) -> None:
        """开始拖动行"""
        if not self.dragging:
            table = self.query_one("#commands-table")
            if table.cursor_row is not None:
                self.dragging = True
                self.drag_row = table.cursor_row
                row = table.get_row_at(table.cursor_row)
                if row:
                    row.add_class("dragging")

    def on_key_up(self, event) -> None:
        """处理键盘释放事件"""
        if event.key == " " and self.dragging:
            table = self.query_one("#commands-table")
            table.get_row_at(self.drag_row).remove_class("dragging")
            self.dragging = False
            self.drag_row = None

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """处理行选择事件"""
        if self.dragging and event.row_key != self.drag_row:
            self._move_row(self.drag_row, int(event.row_key))
            self.dragging = False
            self.drag_row = None

    def _move_row(self, from_idx: int, to_idx: int) -> None:
        """移动行"""
        if from_idx == to_idx:
            return
            
        cmd = self.commands.pop(from_idx)
        self.commands.insert(to_idx, cmd)
        self.save_commands()
        
        # 刷新表格
        table = self.query_one("#commands-table")
        table.clear()
        table.add_columns("名称", "命令", "参数")
        for cmd in self.commands:
            table.add_row(cmd["name"], cmd["command"], cmd["args"])

    def action_new_command(self) -> None:
        """新建命令"""
        # 添加新的编辑页签
        tabs = self.query_one("#tab-content")
        editor = CommandEditor()
        tabs.add_pane(editor)
        tabs.active = "新建命令"  # 使用页签标题来激活

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """处理按钮事件"""
        if event.button.id == "save":
            self.action_save_command()
        elif event.button.id == "run":
            self.action_run_command()
        elif event.button.id == "delete":
            self.action_remove_command()

    def action_save_command(self) -> None:
        """保存命令"""
        # 获取当前活动的编辑页签
        editor = self.query_one(CommandEditor)
        if not editor:
            return

        name = editor.query_one("#name").value
        command = editor.query_one("#command").value
        args = editor.query_one("#args").value

        if not name or not command:
            return

        # 如果是编辑现有命令
        if editor.cmd:
            idx = self.commands.index(editor.cmd)
            self.commands[idx] = {
                "name": name,
                "command": command,
                "args": args
            }
        # 如果是新建命令
        else:
            self.commands.append({
                "name": name,
                "command": command,
                "args": args
            })

        self.save_commands()

        # 刷新总览表格
        table = self.query_one("#commands-table")
        table.clear()
        table.add_columns("名称", "命令", "参数")
        for cmd in self.commands:
            table.add_row(cmd["name"], cmd["command"], cmd["args"])

        # 关闭当前编辑页签
        tabs = self.query_one(TabbedContent)
        tabs.remove_pane(editor)
        tabs.active = 0  # 切换回总览页签

    def action_run_command(self) -> None:
        """运行选中的命令"""
        table = self.query_one("#commands-table")
        if table.cursor_row is not None:
            row = table.cursor_row
            cmd = self.commands[row]
            command = f"{cmd['command']} {cmd['args']}"
            self.exit()
            os.system(command)

    def action_remove_command(self) -> None:
        """删除选中的命令"""
        table = self.query_one("#commands-table")
        if table.cursor_row is not None:
            row = table.cursor_row
            # 先从数据中删除
            self.commands.pop(row)
            self.save_commands()
            
            # 重新加载表格数据
            table.clear()
            table.add_columns("名称", "命令", "参数")
            for cmd in self.commands:
                table.add_row(cmd["name"], cmd["command"], cmd["args"])

            # 如果是在编辑页签中删除
            editor = self.query_one(CommandEditor)
            if editor and editor.cmd:
                tabs = self.query_one("#tab-content")
                tabs.remove_pane(editor)
                tabs.active = "运行"  # 切换回运行页签

    def action_move_up(self) -> None:
        """上移选中的命令"""
        table = self.query_one("#commands-table")
        if table.cursor_row is not None and table.cursor_row > 0:
            row = table.cursor_row
            self.commands[row], self.commands[row-1] = self.commands[row-1], self.commands[row]
            table.clear()
            table.add_columns("名称", "命令", "参数")
            for cmd in self.commands:
                table.add_row(cmd["name"], cmd["command"], cmd["args"])
            table.cursor_row = row - 1
            self.save_commands()

    def action_move_down(self) -> None:
        """下移选中的命令"""
        table = self.query_one("#commands-table")
        if table.cursor_row is not None and table.cursor_row < len(self.commands) - 1:
            row = table.cursor_row
            self.commands[row], self.commands[row+1] = self.commands[row+1], self.commands[row]
            table.clear()
            table.add_columns("名称", "命令", "参数")
            for cmd in self.commands:
                table.add_row(cmd["name"], cmd["command"], cmd["args"])
            table.cursor_row = row + 1
            self.save_commands()

    def action_toggle_dark(self) -> None:
        """切换暗色/亮色主题"""
        self.theme = "textual-light" if self.theme == "textual-dark" else "textual-dark"

    def on_mount(self) -> None:
        """初始化"""
        self.theme = "textual-light"
        
        # 初始化表格
        table = self.query_one("#commands-table")
        table.add_columns("名称", "命令", "参数")
        for cmd in self.commands:
            table.add_row(cmd["name"], cmd["command"], cmd["args"])

if __name__ == "__main__":
    app = CommandsTUI()
    app.run() 
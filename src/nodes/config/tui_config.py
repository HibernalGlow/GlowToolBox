from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import ScrollableContainer, Container, Horizontal, Grid, VerticalScroll
from textual.widgets import (
    Header, 
    Footer, 
    Button, 
    Input, 
    Label, 
    SelectionList
)
from textual.binding import Binding
from typing import Dict, List, Union, Optional, Any
import subprocess
import sys
import os

class ConfigOption:
    """配置选项基类"""
    def __init__(self, label: str, id: str, arg: str):
        self.label = label
        self.id = id
        self.arg = arg

class CheckboxOption(ConfigOption):
    """复选框选项"""
    def __init__(self, label: str, id: str, arg: str):
        super().__init__(label, id, arg)

class InputOption(ConfigOption):
    """输入框选项"""
    def __init__(self, label: str, id: str, arg: str, default: str = "", placeholder: str = ""):
        super().__init__(label, id, arg)
        self.default = default
        self.placeholder = placeholder

class ConfigTemplate(App[None]):
    """通用配置界面模板"""
    
    CSS = """
    Screen {
        align: center middle;
    }

    #main-container {
        width: 80%;
        height: auto;
        border: round $primary;
        background: $surface;
        padding: 1 2;
        min-width: 50;
        max-width: 120;
    }

    .config-group {
        background: $surface;
        height: auto;
        margin: 1;
        padding: 0;
    }

    .group-title {
        background: $primary;
        color: $text;
        text-style: bold;
        text-align: center;
        width: 100%;
        padding: 0 1;
    }

    SelectionList {
        background: transparent;
        border: none;
        height: auto;
        max-height: 10;
        scrollbar-gutter: stable;
        padding: 0;
        margin: 0;
        box-sizing: border-box;
    }

    SelectionList:focus {
        border: none;
        background: transparent;
    }

    .option-list--option {
        background: $panel;
        color: $text;
        padding: 0 1;
        height: 1;
        margin-bottom: 1;
        border: none;
        box-sizing: border-box;
    }

    .option-list--option:hover {
        background: $primary;
    }

    .option-list--option.-selected {
        background: $accent;
        color: $text;
        border: none;
    }

    .params-container {
        layout: vertical;
        background: transparent;
        padding: 0;
        height: auto;
        margin-top: 1;
    }

    .param-item {
        layout: horizontal;
        height: 3;
        margin-bottom: 1;
        padding: 0;
        border: none;
        background: transparent;
    }

    .param-item:focus-within {
        background: transparent;
        border: none;
    }

    .param-item Label {
        width: 30%;
        content-align: right middle;
        padding: 0 1;
        background: $primary-darken-1;
        color: $text;
    }

    .param-item Input {
        width: 70%;
        background: $panel;
        border: none;
        padding: 0 1;
        height: 100%;
        color: $text;
    }

    .param-item Input:focus {
        background: $surface-lighten-1;
        border: round $accent;
    }

    #buttons-container {
        layout: horizontal;
        align: center middle;
        height: 3;
        margin-top: 1;
        background: $surface;
        padding: 0 1;
    }

    Button {
        margin: 0 1;
        width: 16;
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
        Binding("r", "run", "运行"),
        Binding("d", "toggle_dark", "切换主题"),
    ]

    def __init__(
        self,
        program: str,
        title: str = "配置界面",
        checkbox_options: List[CheckboxOption] = None,
        input_options: List[InputOption] = None,
        extra_args: List[str] = None,
        demo_mode: bool = False
    ):
        super().__init__()
        self.program = program
        self.title = title
        self.checkbox_options = checkbox_options or []
        self.input_options = input_options or []
        self.extra_args = extra_args or []
        self.demo_mode = demo_mode

    def action_toggle_dark(self) -> None:
        """切换暗色/亮色主题"""
        self.theme = "textual-light" if self.theme == "textual-dark" else "textual-dark"

    def compose(self) -> ComposeResult:
        """生成界面"""
        yield Header(show_clock=True)

        with ScrollableContainer(id="main-container"):
            # 功能开关组
            if self.checkbox_options:
                with Container(classes="config-group"):
                    yield Label("功能开关", classes="group-title")
                    yield SelectionList[str](
                        *[(opt.label, opt.id, False) for opt in self.checkbox_options]
                    )

            # 参数设置组
            if self.input_options:
                with Container(classes="config-group"):
                    yield Label("参数设置", classes="group-title")
                    with Container(classes="params-container"):
                        for opt in self.input_options:
                            with Container(classes="param-item"):
                                yield Label(f"{opt.label}:")
                                yield Input(
                                    value=opt.default,
                                    placeholder=opt.placeholder,
                                    id=opt.id
                                )

            # 按钮组
            with Horizontal(id="buttons-container"):
                yield Button("运行", classes="primary", id="run-btn")
                yield Button("退出", classes="error", id="quit-btn")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮事件处理"""
        if event.button.id == "quit-btn":
            self.exit()
        elif event.button.id == "run-btn":
            self.action_run()

    def action_run(self) -> None:
        """收集配置并运行程序"""
        if self.demo_mode:
            print("\n收集到的配置:")
            print("命令:", self.program)
            if self.extra_args:
                print("额外参数:", " ".join(self.extra_args))
            
            print("\n功能开关:")
            selection_list = self.query_one(SelectionList)
            selected_options = selection_list.selected
            for opt in self.checkbox_options:
                is_selected = opt.id in selected_options
                print(f"  {opt.label}: {'开启' if is_selected else '关闭'} ({opt.arg})")
            
            print("\n参数设置:")
            for opt in self.input_options:
                value = self.query_one(f"#{opt.id}").value
                print(f"  {opt.label}: {value or '未设置'} ({opt.arg})")
            
            input("\n按回车键继续...")
            self.exit()
            return

        cmd = [self.program] + self.extra_args

        # 添加选中的功能选项
        selection_list = self.query_one(SelectionList)
        selected_options = selection_list.selected
        for opt in self.checkbox_options:
            if opt.id in selected_options:
                cmd.append(opt.arg)

        # 添加输入框选项
        for opt in self.input_options:
            value = self.query_one(f"#{opt.id}").value
            if value:
                cmd.extend([opt.arg, value])

        # 退出TUI并运行程序
        self.exit()
        
        # 使用subprocess运行命令而不是os.system
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"运行程序时出错: {e}")
        except Exception as e:
            print(f"发生未知错误: {e}")

    def on_mount(self) -> None:
        """初始化"""
        self.title = "配置界面"
        self.theme = "textual-light"  # 使用Textual自带的亮色主题
        self._adjust_layout()

    def on_resize(self) -> None:
        """窗口大小改变时调整布局"""
        self._adjust_layout()

    def _adjust_layout(self) -> None:
        """根据容器宽度调整布局类名"""
        container = self.query_one("#main-container")
        if container:
            width = container.size.width
            # 移除所有布局类
            container.remove_class("-narrow")
            container.remove_class("-wide")
            
            # 根据宽度添加相应的类
            if width < 60:
                container.add_class("-narrow")
            elif width > 100:
                container.add_class("-wide")

def create_config_app(
    program: str,
    checkbox_options: List[tuple] = None,
    input_options: List[tuple] = None,
    title: str = "配置界面",
    extra_args: List[str] = None,
    demo_mode: bool = False
) -> ConfigTemplate:
    """
    创建配置界面的便捷函数
    
    Args:
        program: 要运行的程序路径
        checkbox_options: 复选框选项列表，每项格式为 (label, id, arg)
        input_options: 输入框选项列表，每项格式为 (label, id, arg, default, placeholder)
        title: 界面标题
        extra_args: 额外的命令行参数
        demo_mode: 是否为演示模式
    
    Returns:
        ConfigTemplate: 配置界面实例
    """
    checkbox_opts = []
    if checkbox_options:
        for label, id, arg in checkbox_options:
            checkbox_opts.append(CheckboxOption(label, id, arg))

    input_opts = []
    if input_options:
        for label, id, arg, *rest in input_options:
            default = rest[0] if len(rest) > 0 else ""
            placeholder = rest[1] if len(rest) > 1 else ""
            input_opts.append(InputOption(label, id, arg, default, placeholder))

    return ConfigTemplate(
        program=program,
        title=title,
        checkbox_options=checkbox_opts,
        input_options=input_opts,
        extra_args=extra_args,
        demo_mode=demo_mode
    )

# 使用示例
if __name__ == "__main__":
    # 演示用例
    checkbox_options = [
        ("功能选项1", "feature1", "--feature1"),
        ("功能选项2", "feature2", "--feature2"),
        ("功能选项3", "feature3", "--feature3"),
        ("功能选项4", "feature4", "--feature4"),
    ]

    input_options = [
        ("数字参数", "number", "--number", "100", "输入数字"),
        ("文本参数", "text", "--text", "", "输入文本"),
        ("路径参数", "path", "--path", "", "输入路径"),
        ("选择参数", "choice", "--choice", "A", "A/B/C"),
    ]

    app = create_config_app(
        program="demo_program.py",
        checkbox_options=checkbox_options,
        input_options=input_options,
        title="TUI配置界面演示",
        extra_args=["--demo"],
        demo_mode=True
    )
    app.run() 
from __future__ import annotations
from pathlib import Path
import yaml
from textual.app import App, ComposeResult
from textual.containers import ScrollableContainer, Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Button, Input, Label, Tabs, Tab, TabPane
from textual.binding import Binding
from dataclasses import dataclass
from typing import List, Optional
import subprocess

@dataclass
class Parameter:
    name: str
    type: str
    description: str
    prefix: str
    required: bool
    input_type: Optional[str] = None
    default: Optional[str] = None
    value: Optional[str] = None

@dataclass
class Script:
    name: str
    path: str
    description: str
    params: List[Parameter]

class ScriptManager(App):
    CSS = """
    Screen {
        align: center middle;
    }

    #main-container {
        width: 80%;
        height: 80%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }

    Tabs {
        dock: top;
        width: 100%;
        height: auto;
    }

    TabPane {
        padding: 1;
    }

    #script-content {
        padding: 1;
    }

    .script-description {
        text-align: center;
        padding: 1;
        background: $primary-darken-1;
        color: $text;
        margin-bottom: 1;
    }

    .param-container {
        height: auto;
        margin: 1;
        padding: 1;
        border: round $primary-darken-2;
    }

    .param-item {
        layout: horizontal;
        height: 3;
        margin-bottom: 1;
        padding: 0;
    }

    .param-item Label {
        width: 30%;
        content-align: right middle;
        padding: 0 1;
        background: $primary-darken-1;
    }

    .param-item Input, .param-item Button {
        width: 70%;
        margin: 0;
    }

    #buttons-container {
        layout: horizontal;
        align: center middle;
        height: 3;
        margin-top: 1;
        padding: 0 1;
    }

    Button {
        margin: 0 1;
        min-width: 16;
    }

    Button.error {
        background: $error;
    }
    """

    BINDINGS = [
        ("q", "quit", "退出"),
        ("r", "run_script", "运行脚本"),
        ("d", "toggle_dark", "切换主题"),
    ]

    def __init__(self):
        super().__init__()
        self.scripts = self.load_scripts()
        self.current_script = None if not self.scripts else self.scripts[0]

    def compose(self) -> ComposeResult:
        """创建UI布局"""
        yield Header()
        
        with ScrollableContainer(id="main-container"):
            with Tabs():
                # 先创建所有的Tab标签
                for i, script in enumerate(self.scripts):
                    yield Tab(script.name, id=f"script-tab-{i}")
                
                # 然后为每个脚本创建对应的TabPane
                for i, script in enumerate(self.scripts):
                    with TabPane(id=f"script-pane-{i}"):
                        yield Label(script.description, classes="script-description")
                        with Container(id=f"params-container-{i}"):
                            for param in script.params:
                                with Container(classes="param-container"):
                                    with Container(classes="param-item"):
                                        yield Label(f"{param.description}:")
                                        if param.type == "flag":
                                            yield Button(
                                                "禁用",
                                                id=f"param-{i}-{param.name}"
                                            )
                                        else:
                                            yield Input(
                                                value=param.default or "",
                                                placeholder=f"输入{param.description}",
                                                id=f"param-{i}-{param.name}"
                                            )
            
            # 按钮区域
            with Horizontal(id="buttons-container"):
                yield Button("运行", variant="primary", id="run-btn")
                yield Button("退出", classes="error", id="quit-btn")

        yield Footer()

    def load_scripts(self) -> List[Script]:
        config_path = Path(__file__).parent / "config.yaml"
        with open(config_path, encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        scripts = []
        for script_data in config["scripts"]:
            params = [
                Parameter(**param_data)
                for param_data in script_data["params"]
            ]
            scripts.append(Script(
                name=script_data["name"],
                path=script_data["path"],
                description=script_data["description"],
                params=params
            ))
        return scripts

    def on_mount(self) -> None:
        """初始化界面"""
        self.title = "脚本管理器"
        if self.current_script:
            self.update_script_content(self.current_script)

    def on_tabs_tab_clicked(self, event: Tabs.TabClicked) -> None:
        """处理选项卡切换"""
        self.current_script = self.scripts[int(event.tab.id.split("-")[-1])]

    def update_script_content(self, script: Script) :
        """更新脚本内容显示"""
        # 更新描述
        self.query_one("#script-description").update(script.description)
        
        # 更新参数区域
        params_container = self.query_one("#params-container")
        params_container.remove_children()
        
        for param in script.params:
            with params_container.compose():
                with Container(classes="param-container"):
                    with Container(classes="param-item"):
                        yield Label(f"{param.description}:")
                        if param.type == "flag":
                            yield Button(
                                "禁用",
                                id=f"param-{i}-{param.name}"
                            )
                        else:
                            yield Input(
                                value=param.default or "",
                                placeholder=f"输入{param.description}",
                                id=f"param-{i}-{param.name}"
                            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮事件处理"""
        if event.button.id == "quit-btn":
            self.exit()
        elif event.button.id == "run-btn":
            self.action_run_script()
        elif event.button.id and event.button.id.startswith("param-"):
            # 切换开关型参数状态
            if event.button.label == "启用":
                event.button.label = "禁用"
            else:
                event.button.label = "启用"

    def action_run_script(self) -> None:
        """运行当前脚本"""
        if not self.current_script:
            return

        # 获取当前脚本的索引
        script_index = self.scripts.index(self.current_script)
        
        # 构建命令行参数
        cmd = ["python", self.current_script.path]
        for param in self.current_script.params:
            input_widget = self.query_one(f"#param-{script_index}-{param.name}")
            
            if param.type == "flag":
                if input_widget.label == "启用":
                    cmd.append(param.prefix)
            else:
                value = input_widget.value
                if value:
                    cmd.append(param.prefix)
                    cmd.append(value)

        # 添加测试运行提示
        self.notify(f"即将运行命令: {' '.join(cmd)}")
        
        # 运行脚本
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            if result.returncode == 0:
                self.notify("运行成功!")
                if result.stdout:
                    self.notify(f"输出: {result.stdout[:100]}...")
            else:
                self.notify(f"运行失败: {result.stderr}", severity="error")
        except Exception as e:
            self.notify(f"运行失败: {str(e)}", severity="error")

    def action_toggle_dark(self) -> None:
        """切换暗色/亮色主题"""
        self.dark = not self.dark

if __name__ == "__main__":
    app = ScriptManager()
    app.run()
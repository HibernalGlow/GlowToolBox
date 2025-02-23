from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import ScrollableContainer, Container, Horizontal, Grid, VerticalScroll
from textual.widgets import (
    Header, 
    Footer, 
    Button, 
    Input, 
    Label, 
    SelectionList,
    Select,
    RadioSet
)
from textual.screen import ModalScreen
from textual.binding import Binding
from typing import Dict, List, Union, Optional, Any, Callable
import subprocess
import sys
import os
import pyperclip
import yaml

class ConfigOption:
    """配置选项基类"""
    def __init__(self, label: str, id: str, arg: str):
        self.label = label
        self.id = id
        self.arg = arg

class CheckboxOption(ConfigOption):
    """复选框选项"""
    def __init__(self, label: str, id: str, arg: str, default: bool = False):
        super().__init__(label, id, arg)
        self.default = default

class InputOption(ConfigOption):
    """输入框选项"""
    def __init__(self, label: str, id: str, arg: str, default: str = "", placeholder: str = ""):
        super().__init__(label, id, arg)
        self.default = default
        self.placeholder = placeholder

class PresetConfig:
    """预设配置类"""
    def __init__(
        self,
        name: str,
        description: str,
        checkbox_options: List[str],  # 选中的checkbox id列表
        input_values: Dict[str, str]  # input id和值的字典
    ):
        self.name = name
        self.description = description
        self.checkbox_options = checkbox_options
        self.input_values = input_values

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
        padding: 0;  /* 完全移除上下padding */
        min-width: 50;
        max-width: 120;
    }

    #top-container {
        layout: horizontal;
        height: auto;
        margin-bottom: 0;  
        padding: 0;  /* 新增：移除内边距 */
    }

    #presets-container {
        width: 100%;
        height: auto;
        margin: 0;
        padding: 0;
    }

    #buttons-container {
        width: 100%;
        layout: horizontal;
        align: center middle;
        height: auto;
        padding: 0;
        margin: 0 0 1 0;
    }

    #buttons-container Button {
        width: auto;
        min-width: 10;
        margin: 0 1;
        height: 3;
        content-align: center middle;
        padding: 0;
        background: $primary;
        color: $text;
        border: none;
    }

    #buttons-container #quit-btn {
        margin-bottom: 0;
        background: $error;
    }

    #buttons-container #copy-btn {
        background: $primary-darken-1;
    }

    #buttons-container Button:hover {
        background: $primary-lighten-2;
    }

    #buttons-container #quit-btn:hover {
        background: $error-lighten-2;
    }

    .config-group {
        background: $surface;
        height: auto;
        margin: 0;  /* 减少margin */
        padding: 0;
    }

    .group-title {
        background: $primary;
        color: $text;
        text-style: bold;
        text-align: center;
        width: 100%;
        padding: 0 1;
        margin: 0;  /* 确保没有margin */
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
        margin-bottom: 0;  /* 减少选项之间的间距 */
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
        layout: grid;
        grid-size: 2;
        grid-columns: 1fr 1fr;
        grid-gutter: 0;  
        background: transparent;
        padding: 0;
        height: auto;
        margin-top: 0;  
    }

    .param-item {
        layout: horizontal;
        height: 3;
        padding: 0;
        border: none;
        background: transparent;
        margin: 0;  /* 确保没有margin */
    }

    .param-item Label {
        width: 40%;  # 调整标签宽度
        content-align: right middle;
        padding: 0 1;
        background: $primary-darken-1;
        color: $text;
    }

    .param-item Input {
        width: 60%;  # 调整输入框宽度
        background: $panel;
        border: none;
        padding: 0 1;
        height: 100%;
        color: $text;
    }

    #command-preview {
        height: auto;
        margin: 0;  /* 完全移除上下margin */
        padding: 0;
        background: $surface-darken-2;
        border: solid $primary;
    }

    #command-preview-header {
        layout: horizontal;
        height: auto;
        padding: 0;
    }

    #command-preview-header Label {
        padding: 0 1;
        color: $text;
        text-style: bold;
        width: 1fr;
    }

    #command-preview-header Button {
        width: auto;
        min-width: 8;
        margin: 0 1;
        height: 1;
        background: $primary-darken-1;
    }

    #command-preview Label {
        padding: 0 1;
        color: $text;
        text-style: bold;
    }

    #command-preview #command {
        background: $surface-darken-1;
        color: $accent;
        padding: 0 1;
        border-top: solid $primary;
        overflow-x: scroll;
        width: 100%;
        height: auto;
        min-height: 1;
    }

    #preset-list {
        height: auto;
        margin: 0;  
        padding: 0;  /* 新增：移除内边距 */
        background: transparent;
    }

    #preset-list RadioSet {
        background: transparent;
        height: auto;
        padding: 0;
        margin: 0;  /* 确保没有margin */
    }

    #preset-control-buttons {
        layout: horizontal;
        height: 3;
        margin-top: 1;
    }

    #preset-control-buttons Button {
        margin: 0 1;
        min-width: 16;
    }

    #dialog-grid {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 4;
        padding: 1;
        width: 60;
        height: 16;
        border: thick $background 80%;
        background: $surface;
    }

    #dialog-grid Label {
        text-align: right;
        padding: 1;
    }

    #dialog-grid Input {
        width: 100%;
    }

    #dialog-grid Button {
        margin: 1 1;
        width: 100%;
    }

    #preset-radio {
        width: 100%;
        padding: 0;
        margin: 0;
    }

    #preset-radio > .radio-set-option {
        width: 100%;
        margin: 0;
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
        demo_mode: bool = False,
        presets: List[PresetConfig] = None,
        on_run: Callable[[dict], None] = None  # 新增回调函数参数
    ):
        super().__init__()
        self.program = program
        self.title = title
        self.checkbox_options = checkbox_options or []
        self.input_options = input_options or []
        self.extra_args = extra_args or []
        self.demo_mode = demo_mode
        self.presets = {preset.name: preset for preset in (presets or [])}  # 转换为字典
        self._checkbox_states = {}
        self._input_values = {}
        self.on_run_callback = on_run  # 保存回调函数

    def _load_presets(self) -> dict:
        """加载预设配置"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f).get('presets', {})
        except Exception as e:
            self.notify(f"加载预设配置失败: {e}", severity="error")
            return {}

    def _save_preset(self, name: str, description: str = "") -> None:
        """保存当前配置为预设"""
        try:
            # 收集当前配置
            selection_list = self.query_one(SelectionList)
            selected_options = selection_list.selected
            
            # 创建新预设
            new_preset = PresetConfig(
                name=name,
                description=description,
                checkbox_options=[opt.id for opt in self.checkbox_options 
                                if opt.id in selected_options],
                input_values={opt.id: self.query_one(f"#{opt.id}").value 
                            for opt in self.input_options}
            )

            # 更新预设列表
            self.presets[name] = new_preset
            
            # 刷新预设列表
            preset_list = self.query_one("#preset-list")
            preset_list.remove_children()
            if self.presets:
                preset_list.mount(RadioSet(
                    *[f"{name}\n{preset.description}" 
                      for name, preset in self.presets.items()],
                    id="preset-radio"
                ))
            
            self.notify("预设配置已保存")
            
        except Exception as e:
            self.notify(f"保存预设配置失败: {e}", severity="error")

    def _apply_preset(self, preset_name: str) -> None:
        """应用预设配置"""
        if preset_name not in self.presets:
            return

        preset = self.presets[preset_name]
        
        # 清空所有输入框
        for opt in self.input_options:
            input_widget = self.query_one(f"#{opt.id}", Input)
            if input_widget:
                input_widget.value = ""

        # 只设置预设中指定的值（使用输入框ID作为键）
        for option_id, value in preset.input_values.items():
            input_widget = self.query_one(f"#{option_id}", Input)
            if input_widget:
                input_widget.value = value

        # 清空所有复选框选择
        selection_list = self.query_one(SelectionList)
        selection_list.deselect_all()
        
        # 只选择预设中指定的选项
        for option_id in preset.checkbox_options:
            selection_list.select(option_id)

        self._update_command_preview()
        self.notify(f"已应用预设配置: {preset_name}")

    def action_toggle_dark(self) -> None:
        """切换暗色/亮色主题"""
        self.theme = "textual-light" if self.theme == "nord" else "nord"

    def compose(self) -> ComposeResult:
        """生成界面"""
        yield Header(show_clock=True)

        with ScrollableContainer(id="main-container"):
            # 按钮组 - 水平排列在顶部
            with Container(id="buttons-container"):
                yield Button("运行", classes="primary", id="run-btn")
                yield Button("复制命令", classes="copy", id="copy-btn")
                yield Button("退出", classes="error", id="quit-btn")

            # 顶部容器：预设配置和按钮
            with Container(id="top-container"):
                # 预设配置区域
                with Container(id="presets-container"):
                    with Container(id="preset-list"):
                        # 如果有预设配置，显示RadioSet
                        if self.presets:
                            yield RadioSet(
                                *[f"{name}\n{preset.description}" 
                                  for name, preset in self.presets.items()],
                                id="preset-radio"
                            )

            # 命令预览区域
            with Container(id="command-preview"):
                yield Label("", id="command")

            # 功能开关组
            if self.checkbox_options:
                with Container(classes="config-group"):
                    yield Label("功能开关", classes="group-title")
                    yield SelectionList[str](
                        *[(opt.label, opt.id, opt.default) for opt in self.checkbox_options]
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

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮事件处理"""
        if event.button.id == "quit-btn":
            self.exit()
        elif event.button.id == "run-btn":
            self.action_run()
        elif event.button.id == "copy-btn":
            self.action_copy_command()
        elif event.button.id == "save-preset":
            # 弹出对话框获取预设名称和描述
            class SavePresetDialog(ModalScreen[tuple[str, str]]):
                BINDINGS = [("escape", "cancel", "取消")]
                
                def compose(self) -> ComposeResult:
                    with Grid(id="dialog-grid"):
                        yield Label("预设名称:")
                        yield Input(id="preset-name")
                        yield Label("描述:")
                        yield Input(id="preset-desc")
                        yield Button("保存", variant="primary")
                        yield Button("取消", variant="error")

                def on_button_pressed(self, event: Button.Pressed) -> None:
                    if event.button.label == "保存":
                        name = self.query_one("#preset-name").value
                        desc = self.query_one("#preset-desc").value
                        self.dismiss((name, desc))
                    else:
                        self.dismiss(None)

                def action_cancel(self) -> None:
                    self.dismiss(None)

            async def show_save_dialog() -> None:
                result = await self.push_screen(SavePresetDialog())
                if result:
                    name, desc = result
                    if name:
                        self._save_preset(name, desc)

            self.app.run_worker(show_save_dialog())

        elif event.button.id == "delete-preset":
            # 删除当前选中的预设
            radio_set = self.query_one("#preset-radio", RadioSet)
            if radio_set and radio_set.pressed_index is not None:
                preset_name = list(self.presets.keys())[radio_set.pressed_index]
                try:
                    del self.presets[preset_name]
                    with open(self.config_file, 'w', encoding='utf-8') as f:
                        yaml.dump({'presets': self.presets}, f, allow_unicode=True)
                    
                    # 刷新预设列表
                    preset_list = self.query_one("#preset-list")
                    preset_list.remove_children()
                    if self.presets:
                        preset_list.mount(RadioSet(
                            *[f"{name}\n{preset.description}" 
                              for name, preset in self.presets.items()],
                            id="preset-radio"
                        ))
                    self.notify("预设配置已删除")
                except Exception as e:
                    self.notify(f"删除预设配置失败: {e}", severity="error")
        elif event.button.id.startswith("preset-"):
            # 应用预设配置
            preset_name = event.button.id[7:]  # 去掉"preset-"前缀
            self._apply_preset(preset_name)

    def _update_command_preview(self) -> None:
        """更新命令预览"""
        # 使用简化的python命令前缀
        cmd = ["python"]
        
        # 添加程序路径（去掉多余的引号）
        program_path = self.program.strip('"')
        cmd.append(program_path)

        # 添加选中的功能选项
        selection_list = self.query_one(SelectionList)
        if selection_list:
            selected_options = selection_list.selected
            for opt in self.checkbox_options:
                if opt.id in selected_options:
                    cmd.append(opt.arg)

        # 添加输入框选项
        for opt in self.input_options:
            value = self.query_one(f"#{opt.id}").value
            if value:
                cmd.extend([opt.arg, value])

        # 添加额外参数
        if self.extra_args:
            cmd.extend(self.extra_args)

        # 更新预览
        command_label = self.query_one("#command")
        command_label.update(" ".join(cmd))

    def on_mount(self) -> None:
        """初始化"""
        self.title = "配置界面"
        self.theme = "textual-light"  # 使用Textual自带的亮色主题
        self._adjust_layout()
        self._update_command_preview()
        # 设置定时器，每0.1秒更新一次命令预览
        self.set_interval(0.1, self._update_command_preview)

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

    def on_selection_list_highlighted_changed(self) -> None:
        """当选择列表高亮变化时更新预览"""
        self._update_command_preview()

    def on_selection_list_selection_changed(self) -> None:
        """当选择列表选择变化时更新预览"""
        self._update_command_preview()

    def on_selection_list_selected(self) -> None:
        """当选择列表选择确认时更新预览"""
        self._update_command_preview()

    def on_selection_list_option_selected(self) -> None:
        """当选择列表选项被选中时更新预览"""
        self._update_command_preview()

    def on_selection_list_option_deselected(self) -> None:
        """当选择列表选项被取消选中时更新预览"""
        self._update_command_preview()

    def on_selection_list_option_highlighted(self) -> None:
        """当选择列表选项被高亮时更新预览"""
        self._update_command_preview()

    # 也可以尝试直接监听空格键的按下
    def on_key(self, event) -> None:
        """监听键盘事件"""
        if event.key == "space":
            self._update_command_preview()

    def action_copy_command(self) -> None:
        """复制命令到剪贴板"""
        try:
            command = self.query_one("#command").renderable
            pyperclip.copy(command)
            # 可以添加一个临时提示，表示复制成功
            self.notify("命令已复制到剪贴板", timeout=1)
        except Exception as e:
            self.notify(f"复制失败: {e}", severity="error")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """当选择预设配置时"""
        if event.radio_set.id == "preset-radio":
            preset_name = list(self.presets.keys())[event.index]
            self._apply_preset(preset_name)

    def on_radio_set_clicked(self, event: RadioSet.Clicked) -> None:
        """处理点击事件"""
        if event.radio_set.id == "preset-radio":
            if event.click_count == 2:  # 检查是否是双击
                preset_name = list(self.presets.keys())[event.radio_set.pressed_index]
                self._apply_preset(preset_name)
                self.action_run()

    def action_run(self) -> None:
        """收集配置并执行回调函数"""
        params = self._collect_parameters()
        
        if self.on_run_callback:
            # 先退出界面再执行回调
            self.exit()
            self.on_run_callback(params)  # 此时界面已关闭
        else:
            self._execute_command_line(params)

    def _collect_parameters(self) -> dict:
        """收集所有参数到字典"""
        params = {
            'options': {},
            'inputs': {},
            'preset': None
        }
        
        # 收集复选框状态
        selection_list = self.query_one(SelectionList)
        if selection_list:
            selected_options = selection_list.selected
            for opt in self.checkbox_options:
                params['options'][opt.arg] = opt.id in selected_options

        # 收集输入框值（使用输入框ID）
        for opt in self.input_options:
            value = self.query_one(f"#{opt.id}").value
            params['inputs'][opt.arg] = value.strip()

        # 仅在存在预设时收集
        if self.presets:
            radio_set = self.query_one("#preset-radio", RadioSet)
            if radio_set and radio_set.pressed_index is not None:
                preset_name = list(self.presets.keys())[radio_set.pressed_index]
                params['preset'] = preset_name

        return params

    def _execute_command_line(self, params: dict) -> None:
        """原有的命令行执行逻辑"""
        # 构建命令时只使用有值的输入框
        cmd_args = [self.program.strip('"')]

        # 添加选中的功能选项
        selection_list = self.query_one(SelectionList)
        selected_options = selection_list.selected
        for opt in self.checkbox_options:
            if opt.id in selected_options:
                cmd_args.append(opt.arg)

        # 只添加有值的输入框选项
        for opt in self.input_options:
            value = self.query_one(f"#{opt.id}").value
            if value.strip():  # 只有当值不为空时才添加
                cmd_args.extend([opt.arg, value])

        # 添加额外参数
        if self.extra_args:
            cmd_args.extend(self.extra_args)

        # 构建完整的命令
        python_cmd = f'python "{os.path.normpath(self.program)}" {" ".join(cmd_args[1:])}'
        
        # 从程序路径获取脚本名称
        script_path = os.path.normpath(self.program)  # 获取完整路径并规范化
        script_name = os.path.splitext(os.path.basename(script_path))[0]  # 去除扩展名

        # 尝试使用Windows Terminal
        try:
            # 优先使用Windows Terminal的PowerShell
            subprocess.run([
                'wt.exe', 
                '--window', '0',
                'new-tab', 
                '--title', f'{script_name}',  # 使用脚本名称作为标题
                'powershell.exe', 
                '-NoExit', 
                '-Command', 
                f"& {{python '{script_path}' {' '.join(cmd_args[1:])}}}"  # 修改PowerShell命令格式
            ], check=True, timeout=10, shell=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # 保底方案：直接使用PowerShell
            subprocess.run(
                ['powershell.exe', '-NoExit', '-Command', f"& {{python '{script_path}' {' '.join(cmd_args[1:])}}}"],  # 修改PowerShell命令格式
                check=True,
                shell=True
            )
        finally:
            self.exit()  # 确保最后退出

    def get_checkbox_state(self, checkbox_id: str) -> bool:
        """获取复选框状态"""
        return checkbox_id in self._checkbox_states

    def get_input_value(self, input_id: str) -> str:
        """获取输入框值"""
        return self._input_values.get(input_id, "")

# 预设配置示例 - JSON 格式
PRESET_CONFIGS = {
    "默认配置": {
        "description": "基础配置示例",
        "checkbox_options": ["feature1", "feature3"],
        "input_values": {
            "number": "100",
            "text": "",
            "path": "",
            "choice": "A"
        }
    },
    "快速模式": {
        "description": "优化性能的配置",
        "checkbox_options": ["feature1", "feature2", "feature4"],
        "input_values": {
            "number": "200",
            "text": "fast",
            "path": "/tmp",
            "choice": "B"
        }
    }
}

def create_config_app(
    program: str,
    checkbox_options: List[tuple] = None,
    input_options: List[tuple] = None,
    title: str = "配置界面",
    extra_args: List[str] = None,
    demo_mode: bool = False,
    preset_configs: dict = None,
    on_run: Callable[[dict], None] = None  # 新增回调参数
) -> ConfigTemplate:
    """
    创建配置界面的便捷函数
    
    Args:
        program: 要运行的程序路径
        checkbox_options: 复选框选项列表，每项格式为 (label, id, arg) 或 (label, id, arg, default)
        input_options: 输入框选项列表，每项格式为 (label, id, arg, default, placeholder)
        title: 界面标题
        extra_args: 额外的命令行参数
        demo_mode: 是否为演示模式
        preset_configs: JSON格式的预设配置字典，格式如下：
            {
                "预设名称": {
                    "description": "预设描述",
                    "checkbox_options": ["checkbox_id1", "checkbox_id2", ...],
                    "input_values": {
                        "input_id1": "value1",
                        "input_id2": "value2",
                        ...
                    }
                },
                ...
            }
    
    Returns:
        ConfigTemplate: 配置界面实例
    """
    # 处理checkbox选项
    checkbox_opts = []
    if checkbox_options:
        for item in checkbox_options:
            if len(item) == 4:
                label, id, arg, default = item
            else:
                label, id, arg = item
                default = False
            checkbox_opts.append(CheckboxOption(label, id, arg, default))

    # 处理input选项
    input_opts = []
    if input_options:
        for label, id, arg, *rest in input_options:
            default = rest[0] if len(rest) > 0 else ""
            placeholder = rest[1] if len(rest) > 1 else ""
            input_opts.append(InputOption(label, id, arg, default, placeholder))

    # 处理预设配置
    preset_configs = preset_configs or {}
    preset_list = []
    for name, config in preset_configs.items():
        preset_list.append(PresetConfig(
            name=name,
            description=config.get("description", ""),
            checkbox_options=config.get("checkbox_options", []),
            input_values=config.get("input_values", {})
        ))

    return ConfigTemplate(
        program=program,
        title=title,
        checkbox_options=checkbox_opts,
        input_options=input_opts,
        extra_args=extra_args,
        demo_mode=demo_mode,
        presets=preset_list,
        on_run=on_run  # 传递回调函数
    )

# 使用示例
if __name__ == "__main__":
    # 演示用例
    checkbox_options = [
        ("功能选项1", "feature1", "--feature1", True),
        ("功能选项2", "feature2", "--feature2"),
        ("功能选项3", "feature3", "--feature3", True),
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
        demo_mode=True,
        preset_configs=PRESET_CONFIGS  # 使用 JSON 格式的预设配置
    )
    app.run() 
from config import create_config_app
import os

if __name__ == "__main__":
    # 创建一个简单的测试脚本


    # 定义配置选项
    checkbox_options = [
        ("测试选项1", "test1", "--test1", True),
        ("测试选项2", "test2", "--test2", False),
    ]

    input_options = [
        ("输入参数", "input1", "--input", "", "请输入测试参数"),
    ]

    # 创建并运行配置界面
    app = create_config_app(
        program=r"D:\1VSCODE\1ehv\tui\test_script.py",
        checkbox_options=checkbox_options,
        input_options=input_options,
        title="PowerShell测试",
        demo_mode=False
    )
    app.run()

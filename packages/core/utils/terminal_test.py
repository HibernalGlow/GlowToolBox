import os
import sys
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

def run_terminal_diagnostics():
    """运行终端环境诊断测试"""
    console = Console()
    test_results = {}
    
    # 基础环境检测
    test_results["basic"] = {
        "Platform": sys.platform,
        "Python Version": sys.version,
        "Terminal": os.environ.get("TERM", "Unknown"),
        "IDE Detection": detect_ide(),
        "Encoding": sys.stdout.encoding,
        "Timestamp": datetime.now().isoformat()
    }
    
    # 终端能力检测
    test_results["capabilities"] = {
        "TrueColor Support": test_truecolor(console),
        "Unicode Support": test_unicode(console),
        "Emoji Support": test_emoji(console),
        "Box Drawing": test_box_drawing(console),
        "Cursor Movement": test_cursor_movement(console),
        "Link Support": test_hyperlinks(console)
    }
    
    # 环境变量扫描
    test_results["env_vars"] = {
        "IDE Indicators": {
            "PYCHARM_HOSTED": os.environ.get("PYCHARM_HOSTED"),
            "VSCODE_PID": os.environ.get("VSCODE_PID"),
            "WT_SESSION": os.environ.get("WT_SESSION")
        },
        "Terminal Size": f"{console.width}x{console.height}",
        "Color System": str(console.color_system).split(".")[-1]
    }
    
    # 显示诊断报告
    render_report(console, test_results)

def detect_ide():
    """检测IDE类型"""
    ide_map = {
        "PYCHARM_HOSTED": "PyCharm",
        "VSCODE_PID": "VS Code",
        "JPY_PARENT_PID": "Jupyter"
    }
    for var, name in ide_map.items():
        if var in os.environ:
            return f"{name} (env:{var})"
    return "Unknown/System Terminal"

def test_truecolor(console):
    """测试真彩色支持"""
    try:
        color_block = "".join(
            f"[rgb({r},{g},255)]▅[/]"
            for r in range(0, 255, 32)
            for g in range(0, 255, 32)
        )
        console.print("TrueColor测试:", color_block)
        return "Supported" if console.color_system == "truecolor" else "Limited"
    except Exception as e:
        return f"Error: {str(e)}"

def test_unicode(console):
    """测试Unicode支持"""
    test_chars = "∮∑≠∞≈←→⇅✔✗☯♥♫"
    console.print(f"Unicode测试: {test_chars}")
    return "Supported" if console.encoding == "utf-8" else "Limited"

def test_emoji(console):
    """测试Emoji支持"""
    emojis = "🚀🔥🐉🎨💡✅❌"
    console.print(f"Emoji测试: {emojis}")
    return "Supported" if console.encoding == "utf-8" else "Limited"

def test_box_drawing(console):
    """测试框线绘制字符"""
    box_chars = "┌─┐│└─┘"
    console.print(f"Box字符测试: {box_chars}")
    return "Rendered" if console.legacy_windows else "Native"

def test_cursor_movement(console):
    """测试光标移动支持"""
    try:
        console.print("[red]←[/]左 [green]→[/]右 [blue]↑[/]上 [magenta]↓[/]下")
        return "Supported"
    except Exception:
        return "Unsupported"

def test_hyperlinks(console):
    """测试超链接支持"""
    try:
        console.print("[link=https://example.com]虚拟链接测试[/link]")
        return "Supported"
    except Exception:
        return "Unsupported"

def render_report(console, results):
    """渲染诊断报告"""
    # 创建主表格
    main_table = Table(
        title="终端环境诊断报告",
        box=box.ROUNDED,
        header_style="bold magenta",
        expand=True
    )
    
    # 添加列
    main_table.add_column("测试类别", width=20)
    main_table.add_column("详细信息", width=60)
    
    # 基础信息
    basic_grid = Table.grid(padding=(0, 4))
    for k, v in results["basic"].items():
        basic_grid.add_row(f"[cyan]{k}:", f"[white]{v}")
    main_table.add_row("基础环境", basic_grid)
    
    # 能力检测
    caps_table = Table(
        box=None,
        show_header=False,
        row_styles=["dim", ""],
        padding=(0, 2)
    )
    for cap, result in results["capabilities"].items():
        status_style = "green" if "Supported" in result else "yellow"
        caps_table.add_row(
            f"[white]{cap}:",
            f"[{status_style}]{result}[/]"
        )
    main_table.add_row("终端能力", caps_table)
    
    # 环境变量
    env_panel = Panel(
        "\n".join([f"{k}: {v}" for k, v in results["env_vars"]["IDE Indicators"].items()]),
        title="IDE环境变量",
        border_style="blue"
    )
    
    # 最终布局
    console.print(main_table)
    console.print(env_panel)
    console.print(f"\n[bold yellow]诊断建议:[/] {generate_advice(results)}")

def generate_advice(results):
    """生成诊断建议"""
    issues = []
    caps = results["capabilities"]
    
    if "Limited" in caps["TrueColor Support"]:
        issues.append("终端颜色支持有限，建议使用现代终端")
    if "Limited" in caps["Unicode Support"]:
        issues.append("检测到Unicode支持问题，请设置UTF-8编码")
    if "Unsupported" in caps["Link Support"]:
        issues.append("超链接功能不可用，某些交互功能可能受限")
    
    if not issues:
        return "当前终端环境配置良好 ✅"
    return " | ".join(issues) + " (运行前请检查终端配置)"

if __name__ == "__main__":
    run_terminal_diagnostics()
    input("按回车键退出")
import tkinter as tk
from tkinter import messagebox
import importlib.util
import os

# 确保路径正确，这里将路径替换为你的文件路径
file_path = '0真目录一步到位.py'

# 动态加载 `目录一步到位.py`
if os.path.exists(file_path):
    spec = importlib.util.spec_from_file_location("step_to_directory", file_path)
    step_to_directory = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(step_to_directory)
else:
    raise FileNotFoundError(f"文件未找到: {file_path}")

# 模块开关
ENABLE_HTML_CONVERSION = True
ENABLE_DIRECTORY_REPLACEMENT = True
ENABLE_HEADING_ADJUSTMENT = True
ENABLE_SPACE_REMOVAL = True

# 引用目录一步到位.py中的函数
def html_conversion_function():
    step_to_directory.html_conversion_function()

def directory_replacement_function():
    step_to_directory.directory_replacement_function()

def heading_adjustment_function():
    step_to_directory.heading_adjustment_function()

def space_removal_function():
    step_to_directory.space_removal_function()

def run_modules():
    # 再次加载模块以确保最新状态
    spec.loader.exec_module(step_to_directory)
    
    if ENABLE_HTML_CONVERSION:
        html_conversion_function()
    if ENABLE_DIRECTORY_REPLACEMENT:
        directory_replacement_function()
    if ENABLE_HEADING_ADJUSTMENT:
        heading_adjustment_function()
    if ENABLE_SPACE_REMOVAL:
        space_removal_function()
    #messagebox.showinfo("完成", "所有选中的模块已经运行完毕。")

# GUI 设计
def create_gui():
    def toggle_module(module_var, module_name):
        global ENABLE_HTML_CONVERSION, ENABLE_DIRECTORY_REPLACEMENT, ENABLE_HEADING_ADJUSTMENT, ENABLE_SPACE_REMOVAL
        value = module_var.get()
        if module_name == "html_conversion":
            ENABLE_HTML_CONVERSION = value
        elif module_name == "directory_replacement":
            ENABLE_DIRECTORY_REPLACEMENT = value
        elif module_name == "heading_adjustment":
            ENABLE_HEADING_ADJUSTMENT = value
        elif module_name == "space_removal":
            ENABLE_SPACE_REMOVAL = value

    def toggle_all():
        all_selected = select_all_var.get()
        html_conversion_var.set(all_selected)
        directory_replacement_var.set(all_selected)
        heading_adjustment_var.set(all_selected)
        space_removal_var.set(all_selected)
        toggle_module(html_conversion_var, "html_conversion")
        toggle_module(directory_replacement_var, "directory_replacement")
        toggle_module(heading_adjustment_var, "heading_adjustment")
        toggle_module(space_removal_var, "space_removal")

    root = tk.Tk()
    root.title("脚本运行可视化")

    tk.Label(root, text="选择要运行的模块:").pack(anchor="w")

    # 全选复选框
    select_all_var = tk.BooleanVar(value=True)
    tk.Checkbutton(root, text="全选", variable=select_all_var, command=toggle_all).pack(anchor="w")

    # 添加复选框，默认全选
    html_conversion_var = tk.BooleanVar(value=True)
    tk.Checkbutton(root, text="转html表格", variable=html_conversion_var,
                   command=lambda: toggle_module(html_conversion_var, "html_conversion")).pack(anchor="w")

    directory_replacement_var = tk.BooleanVar(value=True)
    tk.Checkbutton(root, text="目录替换", variable=directory_replacement_var,
                   command=lambda: toggle_module(directory_replacement_var, "directory_replacement")).pack(anchor="w")

    heading_adjustment_var = tk.BooleanVar(value=True)
    tk.Checkbutton(root, text="连续同级标题", variable=heading_adjustment_var,
                   command=lambda: toggle_module(heading_adjustment_var, "heading_adjustment")).pack(anchor="w")

    space_removal_var = tk.BooleanVar(value=True)
    tk.Checkbutton(root, text="去汉字空格", variable=space_removal_var,
                   command=lambda: toggle_module(space_removal_var, "space_removal")).pack(anchor="w")

    # 运行按钮
    tk.Button(root, text="运行选中的模块", command=run_modules).pack(anchor="w")

    root.mainloop()

if __name__ == "__main__":
    create_gui()

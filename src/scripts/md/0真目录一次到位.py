import os
import importlib.util

def run_script(script_path):
    spec = importlib.util.spec_from_file_location("module.name", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# 指定要执行的脚本列表及顺序
scripts_to_run = [
    os.path.join('2others\md', '转html表格.py'),
    os.path.join('2others\md', '目录替换.py'),
    os.path.join('2others\md', '连续同级标题.py'),
    os.path.join('2others\md', '去汉字空格.py')
]

# 执行脚本
for script_path in scripts_to_run:
    print(f"Running script: {script_path}")
    run_script(script_path)
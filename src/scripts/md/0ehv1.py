import os
import importlib.util

def run_script(script_path):
    spec = importlib.util.spec_from_file_location("module.name", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# 指定要执行的脚本列表及顺序
scripts_to_run = [
    # os.path.join('ehv', 'ehv-webp-t.py'),
    os.path.join('ehv', 'ehv命名规范.py'),
    os.path.join('ehv', 'ehv画师分类.py'),
    # os.path.join('ehv', 'ehv自动封面.py')
]

# 执行脚本
for script_path in scripts_to_run:
    print(f"Running script: {script_path}")
    run_script(script_path)
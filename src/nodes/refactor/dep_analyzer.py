import ast
import os
import sys
import subprocess
from pathlib import Path

def find_python_files(directory):
    """递归查找目录下的所有Python文件"""
    return Path(directory).rglob('*.py')

def extract_imports(file_path):
    """解析Python文件并提取所有导入的库"""
    with open(file_path, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:  # 忽略相对导入
                imports.add(node.module.split('.')[0])
    return imports

def get_std_libs():
    """获取Python标准库列表"""
    std_modules = sys.stdlib_module_names
    return set(std_modules)

def analyze_dependencies(directory):
    """主分析函数"""
    all_imports = set()
    std_libs = get_std_libs()
    
    for py_file in find_python_files(directory):
        imports = extract_imports(py_file)
        all_imports.update(imports - std_libs)
    
    # 排除内置模块和当前项目模块
    project_modules = {'glowtoolbox'}  # 根据实际项目名称修改
    return sorted(all_imports - project_modules)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python dep_analyzer.py <target_directory>")
        sys.exit(1)
    
    target_dir = sys.argv[1]
    dependencies = analyze_dependencies(target_dir)
    
    print("检测到的第三方依赖：")
    for dep in dependencies:
        print(f"• {dep}")
    
    print("\n使用Poetry安装依赖：")
    print("poetry add " + " ".join(dependencies))
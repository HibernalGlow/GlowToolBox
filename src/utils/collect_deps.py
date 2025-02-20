import os
import sys
from pathlib import Path
import ast
import importlib

STDLIB_MODULES = {
    'abc', 'argparse', 'ast', 'asyncio', 'atexit', 'base64', 'collections', 
    'concurrent', 'contextlib', 'csv', 'ctypes', 'datetime', 'difflib', 
    'filecmp', 'fnmatch', 'functools', 'glob', 'hashlib', 'importlib', 
    'inspect', 'io', 'itertools', 'json', 'locale', 'logging', 'msvcrt', 
    'multiprocessing', 'os', 'pathlib', 'platform', 'queue', 'random', 're', 
    'shutil', 'signal', 'sqlite3', 'stat', 'string', 'subprocess', 'sys', 
    'tempfile', 'threading', 'time', 'timeit', 'tkinter', 'typing', 
    'unicodedata', 'urllib', 'uuid', 'warnings', 'winreg', 'zipfile', '__future__'
}

INTERNAL_MODULES = {
    'nodes', 'utils', 'scripts', 'pics', 'tui', 'textual_logger', 
    'performance_config', 'url_filter', 'src', 'archive'
}

def get_imports_from_file(file_path):
    """分析文件中的所有导入语句"""
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read())
        except:
            return set()
    
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                imports.add(name.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split('.')[0])
    return imports

def get_package_name(import_name):
    """获取import对应的包名"""
    try:
        module = importlib.import_module(import_name)
        if hasattr(module, '__package__') and module.__package__:
            return module.__package__.split('.')[0]
        return import_name
    except:
        return import_name

def scan_directory(directory):
    """扫描目录下所有Python文件的导入"""
    all_imports = set()
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                imports = get_imports_from_file(file_path)
                all_imports.update(imports)
    return all_imports

def is_stdlib_module(module_name):
    """检查是否是标准库模块"""
    try:
        module_spec = importlib.util.find_spec(module_name)
        if module_spec is None:
            return False
        return 'site-packages' not in str(module_spec.origin)
    except:
        return False

def get_package_mapping():
    """获取模块名到包名的映射"""
    return {
        'PIL': 'Pillow',
        'Pillow-avif': 'pillow-avif-plugin',
        'Pillow-jxl': 'pillow-jxl-plugin',
        'cv2': 'opencv-python',
        'yaml': 'PyYAML',
        'dotenv': 'python-dotenv',
        'fitz': 'PyMuPDF',
    }

def main():
    # 获取src目录
    src_dir = Path(__file__).parent.parent
    
    # 扫描所有Python文件
    all_imports = scan_directory(src_dir)
    
    # 过滤掉标准库和内部模块
    third_party_imports = {
        imp for imp in all_imports 
        if imp not in STDLIB_MODULES and imp not in INTERNAL_MODULES
    }
    
    # 模块名到包名的映射
    package_mapping = get_package_mapping()
    
    # 使用pipdeptree获取已安装包的版本
    import subprocess
    result = subprocess.run(['pipdeptree', '--json'], capture_output=True, text=True)
    import json
    deps_info = json.loads(result.stdout)
    
    # 生成requirements.in
    with open('requirements.in', 'w', encoding='utf-8') as f:
        f.write('# 第三方依赖包\n\n')
        for module in sorted(third_party_imports):
            package = package_mapping.get(module, module)
            for dep in deps_info:
                if dep['package']['key'] == package.lower():
                    version = dep['package']['installed_version']
                    f.write(f'{package}>={version}\n')
                    break
            else:
                if package not in STDLIB_MODULES and package not in INTERNAL_MODULES:
                    f.write(f'{package}\n')

if __name__ == '__main__':
    main() 
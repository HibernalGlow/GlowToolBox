import os
import re

def extract_classes(content):
    """提取所有类定义"""
    class_pattern = r"class\s+(\w+):"
    class_blocks = {}
    lines = content.split('\n')
    current_class = None
    current_block = []
    
    for line in lines:
        match = re.match(class_pattern, line)
        if match:
            if current_class:
                class_blocks[current_class] = '\n'.join(current_block)
            current_class = match.group(1)
            current_block = [line]
        elif current_class:
            current_block.append(line)
        elif not line.strip().startswith(('import', 'from', '#', 'def')):
            if 'GLOBAL_VARIABLES' not in class_blocks:
                class_blocks['GLOBAL_VARIABLES'] = []
            class_blocks['GLOBAL_VARIABLES'].append(line)
            
    if current_class:
        class_blocks[current_class] = '\n'.join(current_block)
        
    return class_blocks

def extract_imports(content):
    """提取所有导入语句"""
    imports = []
    for line in content.split('\n'):
        if line.strip().startswith(('import', 'from')):
            imports.append(line)
    return imports

def create_module_files(source_file):
    """创建模块文件"""
    # 读取源文件
    with open(source_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 创建modules目录
    base_dir = os.path.dirname(source_file)
    modules_dir = os.path.join(base_dir, 'modules')
    os.makedirs(modules_dir, exist_ok=True)
    
    # 提取导入语句和类定义
    imports = extract_imports(content)
    class_blocks = extract_classes(content)
    
    # 创建__init__.py
    init_content = []
    
    # 为每个类创建单独的文件
    for class_name, class_content in class_blocks.items():
        if class_name == 'GLOBAL_VARIABLES':
            # 创建globals.py存放全局变量
            with open(os.path.join(modules_dir, 'globals.py'), 'w', encoding='utf-8') as f:
                f.write('\n'.join(imports) + '\n\n')
                f.write('\n'.join(class_content))
            init_content.append(f"from .globals import *")
            continue
            
        module_name = f"{class_name.lower()}.py"
        with open(os.path.join(modules_dir, module_name), 'w', encoding='utf-8') as f:
            f.write('\n'.join(imports) + '\n\n')
            f.write(class_content)
        
        init_content.append(f"from .{class_name.lower()} import {class_name}")
    
    # 创建__init__.py
    with open(os.path.join(modules_dir, '__init__.py'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(init_content))
    
    # 创建main.py
    with open(os.path.join(base_dir, 'main.py'), 'w', encoding='utf-8') as f:
        f.write('''from modules import *

def main():
    """主函数"""
    # 检查是否有命令行参数
    if len(sys.argv) > 1:
        input_handler = InputHandler()
        args = input_handler.parse_arguments()
        run_with_args(args)
    else:
        # 没有命令行参数时启动TUI界面
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from tui.config import create_config_app

        # 定义复选框选项
        checkbox_options = [
            ("从剪贴板读取路径", "clipboard", "--clipboard", True),
            ("内置关键词过滤", "keywords", "--keywords", False),
            ("无限循环inf", "infinite", "--infinite", False),
            ("JXL的JPEG无损转换", "jxl_jpeg_lossless", "--jxl-jpeg-lossless", False),
            ("无损压缩", "lossless", "--lossless", False),
        ]

        # 定义输入框选项
        input_options = [
            ("目标格式", "format", "--format", "avif", "avif/webp/jxl/jpg/png"),
            ("压缩质量", "quality", "--quality", "90", "1-100"),
            ("监控间隔(分钟)", "interval", "--interval", "10", "分钟"),
            ("最小宽度(像素)", "min_width", "--min-width", "0", "像素"),
            ("性能配置文件", "performance_config", "--performance-config", "", "配置文件路径"),
            ("待处理路径", "path", "-p", "", "输入待处理文件夹路径"),
        ]

        # 预设配置
        preset_configs = {
            "AVIF-90-inf": {
                "description": "AVIF格式 90质量 无限模式",
                "checkbox_options": ["infinite","clipboard"],
                "input_values": {
                    "format": "avif",
                    "quality": "90",
                    "interval": "10",
                    "min_width": "0"
                }
            },
            "JXL-CJXL": {
                "description": "JXL格式 CJXL无损转换",
                "checkbox_options": ["clipboard", "jxl_jpeg_lossless"],
                "input_values": {
                    "format": "jxl",
                    "quality": "100",
                    "interval": "10",
                    "min_width": "0"
                }
            },
            "JXL-90": {
                "description": "JXL格式 90质量",
                "checkbox_options": ["clipboard"],
                "input_values": {
                    "format": "jxl",
                    "quality": "90",
                    "interval": "10",
                    "min_width": "0"
                }
            },
            "JXL-75": {
                "description": "JXL格式 75质量",
                "checkbox_options": ["clipboard"],
                "input_values": {
                    "format": "jxl",
                    "quality": "75",
                    "interval": "10",
                    "min_width": "0"
                }
            },
            "AVIF-90-1800": {
                "description": "AVIF格式 90质量 1800宽度过滤",
                "checkbox_options": ["clipboard"],
                "input_values": {
                    "format": "avif",
                    "quality": "90",
                    "interval": "10",
                    "min_width": "1800"
                }
            },
            "AVIF-90-1800-kw": {
                "description": "AVIF格式 90质量 1800宽度 关键词过滤",
                "checkbox_options": ["keywords","clipboard"],
                "input_values": {
                    "format": "avif",
                    "quality": "90",
                    "interval": "10",
                    "min_width": "1800"
                }
            }
        }

        # 创建配置界面
        app = create_config_app(
            program=__file__,
            checkbox_options=checkbox_options,
            input_options=input_options,
            title="图片压缩配置",
            preset_configs=preset_configs
        )
        
        app.run()

if __name__ == '__main__':
    main()
''')

if __name__ == '__main__':
    source_file = '1ehv/archive/011-picsconvert-magick-not-in-mem.py'
    create_module_files(source_file)
    print("脚本拆分完成!") 
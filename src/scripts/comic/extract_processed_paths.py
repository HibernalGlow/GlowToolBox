import os
import re
from pathlib import Path

def extract_processed_paths(logs_dir: str, output_file: str):
    """
    从日志文件夹提取已处理的路径并保存到文件
    """
    processed_dirs = set()
    
    # 遍历日志文件夹
    for root, _, files in os.walk(logs_dir):
        for file in files:
            if file.endswith('.log'):
                log_path = os.path.join(root, file)
                try:
                    with open(log_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # 匹配作者目录路径
                        paths = re.findall(r'E:\\1EHV\\[^"<>|:\n]+?(?=\]|\n|$)', content)
                        processed_dirs.update(paths)
                except Exception as e:
                    print(f"读取日志文件失败 {log_path}: {e}")
    
    # 清理路径
    cleaned_paths = set()
    for path in processed_dirs:
        # 清理路径并确保以]结尾
        clean_path = path.strip().strip('"\']') + ']'
        if clean_path.startswith('E:\\1EHV\\['):
            cleaned_paths.add(clean_path)
    
    # 保存到文件
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            for path in sorted(cleaned_paths):
                f.write(f"{path}\n")
        print(f"\n已保存 {len(cleaned_paths)} 个路径到: {output_file}")
        
        # 打印找到的路径
        if cleaned_paths:
            print("\n找到的路径:")
            for path in sorted(cleaned_paths):
                print(path)
        
    except Exception as e:
        print(f"保存文件失败: {e}")

if __name__ == '__main__':
    logs_dir = r"D:\1VSCODE\GlowToolBox\logs\recruit_cover_filter"
    output_file = r"D:\1VSCODE\GlowToolBox\data\processed_paths.txt"
    extract_processed_paths(logs_dir, output_file) 
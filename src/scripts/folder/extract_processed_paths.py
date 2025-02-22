import os
import re
from pathlib import Path

def extract_processed_paths(logs_dir: str, output_file: str):
    """
    从日志文件夹提取已处理的压缩包完整路径并保存到文件
    """
    processed_files = set()
    
    # 遍历日志文件夹
    for root, _, files in os.walk(logs_dir):
        for file in files:
            if file.endswith('.log'):
                log_path = os.path.join(root, file)
                try:
                    with open(log_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # 调试信息
                        print(f"正在处理日志文件: {log_path}")
                        
                        # 匹配压缩包路径
                        paths = re.findall(r'(E:\\1EHV\\[^"\n<>|:]+?\.(zip|rar|7z))', content, re.IGNORECASE)
                        if paths:
                            print(f"在文件 {log_path} 中找到 {len(paths)} 个路径")
                            # 由于findall返回元组，我们只需要第一个元素
                            paths = [path[0] for path in paths]
                        processed_files.update(paths)
                except Exception as e:
                    print(f"读取日志文件失败 {log_path}: {e}")
    
    # 保存到文件
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            for path in sorted(processed_files):
                f.write(f"{path}\n")
        print(f"\n已保存 {len(processed_files)} 个压缩包路径到: {output_file}")
        
        # 打印找到的路径
        if processed_files:
            print("\n找到的压缩包路径:")
            for path in sorted(processed_files):
                print(path)
        
    except Exception as e:
        print(f"保存文件失败: {e}")

if __name__ == '__main__':
    logs_dir = r"D:\1VSCODE\GlowToolBox\logs\recruit_cover_filter"
    output_file = r"D:\1VSCODE\GlowToolBox\data\processed_paths.txt"
    extract_processed_paths(logs_dir, output_file) 
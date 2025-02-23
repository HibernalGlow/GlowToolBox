import os
import re
from pathlib import Path

def extract_paths(logs_dir: str, output_file: str, mode: str):
    """
    从日志文件夹提取路径并保存到文件
    
    Args:
        logs_dir: 日志文件夹路径
        output_file: 输出文件路径
        mode: 提取模式 - 'archive' 提取压缩包路径, 'folder' 提取文件夹路径
    """
    processed_paths = set()
    
    # 根据模式选择正则表达式
    if mode == 'archive':
        pattern = r'(E:\\1EHV\\[^"\n<>|:]+?\.(zip|rar|7z))'
        desc = "压缩包"
    else:  # folder mode
        pattern = r'(E:\\1EHV\\[^"\n<>|:]+?)(?=\]|\n|$)'
        desc = "文件夹"
    
    # 遍历日志文件夹
    for root, _, files in os.walk(logs_dir):
        for file in files:
            if file.endswith('.log'):
                log_path = os.path.join(root, file)
                try:
                    with open(log_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        print(f"正在处理日志文件: {log_path}")
                        
                        paths = re.findall(pattern, content, re.IGNORECASE)
                        if paths:
                            print(f"在文件 {log_path} 中找到 {len(paths)} 个{desc}路径")
                            # 如果是元组结果，取第一个元素
                            if isinstance(paths[0], tuple):
                                paths = [path[0] for path in paths]
                        processed_paths.update(paths)
                except Exception as e:
                    print(f"读取日志文件失败 {log_path}: {e}")
    
    # 保存到文件
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            for path in sorted(processed_paths):
                f.write(f"{path}\n")
        print(f"\n已保存 {len(processed_paths)} 个{desc}路径到: {output_file}")
        
        # 打印找到的路径
        if processed_paths:
            print(f"\n找到的{desc}路径:")
            for path in sorted(processed_paths):
                print(path)
        
    except Exception as e:
        print(f"保存文件失败: {e}")

if __name__ == '__main__':
    logs_dir = r"D:\1VSCODE\GlowToolBox\logs\recruit_cover_filter"
    
    # 用户选择模式
    while True:
        mode = input("\n请选择提取模式:\n1. 提取压缩包路径\n2. 提取文件夹路径\n请输入(1/2): ").strip()
        if mode in ('1', '2'):
            break
        print("输入无效，请重新选择")
    
    # 根据模式设置输出文件
    if mode == '1':
        output_file = r"D:\1VSCODE\GlowToolBox\src\nodes\refactor\txt\processed_archives.txt"
        extract_paths(logs_dir, output_file, 'archive')
    else:
        output_file = r"D:\1VSCODE\GlowToolBox\src\nodes\refactor\txt\processed_folders.txt"
        extract_paths(logs_dir, output_file, 'folder') 
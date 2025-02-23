import os
import re
from pathlib import Path

def filter_archive_paths(ehv_dir: str, output_file: str):
    """
    遍历目录下的所有压缩包，过滤掉包含黑名单关键词的文件
    """
    # 黑名单关键词
    blacklist = [
        '画集', 'CG', '图集', 
        'artbook', 'art book', 'art-book',
        'cg集', 'CG集', 'イラスト',
        'Gallery', 'gallery', 
        'artwork', 'Artwork'
    ]
    
    # 编译黑名单正则表达式
    blacklist_pattern = '|'.join(blacklist)
    
    archive_files = set()
    filtered_files = set()
    
    # 遍历目录
    for root, _, files in os.walk(ehv_dir):
        for file in files:
            if file.lower().endswith(('.zip', '.rar', '.7z')):
                full_path = os.path.join(root, file)
                archive_files.add(full_path)
                
                # 检查是否包含黑名单关键词
                if not re.search(blacklist_pattern, full_path, re.IGNORECASE):
                    filtered_files.add(full_path)
    
    # 保存结果
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            for path in sorted(filtered_files):
                f.write(f"{path}\n")
                
        # 打印统计信息
        print(f"\n总共找到压缩包: {len(archive_files)} 个")
        print(f"过滤后保留: {len(filtered_files)} 个")
        print(f"被过滤掉: {len(archive_files) - len(filtered_files)} 个")
        print(f"\n结果已保存到: {output_file}")
        
        # 打印被过滤掉的文件示例
        filtered_out = archive_files - filtered_files
        if filtered_out:
            print("\n以下是部分被过滤掉的文件示例:")
            for path in sorted(filtered_out)[:10]:  # 只显示前10个
                print(path)
        
    except Exception as e:
        print(f"保存文件失败: {e}")

if __name__ == '__main__':
    ehv_dir = r"E:\999EHV"
    output_file = r"D:\1VSCODE\GlowToolBox\src\nodes\refactor\txt\filtered_archive_paths.txt"
    filter_archive_paths(ehv_dir, output_file)
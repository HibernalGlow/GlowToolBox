import os
import re
import shutil
from pathlib import Path
import argparse
from collections import defaultdict
import subprocess
import pyperclip

def get_base_name(folder_name):
    """获取文件夹的基本名称（去掉part部分）"""
    # 修改后的正则表达式，支持 part/p 两种前缀格式
    pattern = r'^(.+?)(?:[-_ ]*(?:part|p)[-_ ]*\d+)$'
    match = re.match(pattern, folder_name, re.IGNORECASE)
    return match.group(1).strip() if match else None

def merge_part_folders(base_path):
    """合并同名的part文件夹"""
    base_path = Path(base_path)
    folder_groups = defaultdict(list)
    
    # 收集所有一级文件夹并按基本名称分组
    for item in base_path.iterdir():
        if not item.is_dir():
            continue
            
        base_name = get_base_name(item.name)
        if base_name:
            folder_groups[base_name].append(item)
    
    # 处理每组文件夹
    for base_name, folders in folder_groups.items():
        if len(folders) <= 1:
            continue
            
        # 找到part/p 1文件夹作为目标文件夹
        target_folder = None
        other_folders = []
        
        for folder in folders:
            if re.search(r'(?:part|p)[-_ ]*1$', folder.name, re.IGNORECASE):
                target_folder = folder
            else:
                other_folders.append(folder)
        
        if not target_folder:
            print(f"警告：{base_name} 组中没有找到 part 1 文件夹，跳过处理")
            continue
        
        print(f"\n处理 {base_name} 组:")
        print(f"目标文件夹: {target_folder}")
        print(f"要合并的文件夹: {[f.name for f in other_folders]}")
        
        # 移动其他part文件夹中的内容到part 1
        for folder in other_folders:
            try:
                print(f"\n合并 {folder.name} 到 {target_folder.name}")
                # 创建临时文件夹用于解散操作
                temp_folder = target_folder / f"temp_{folder.name}"
                temp_folder.mkdir(exist_ok=True)
                
                # 先将文件移动到临时文件夹
                for item in folder.iterdir():
                    dest_path = temp_folder / item.name
                    if dest_path.exists():
                        print(f"目标路径已存在，重命名: {item.name}")
                        base, ext = os.path.splitext(item.name)
                        counter = 1
                        while dest_path.exists():
                            new_name = f"{base}_{counter}{ext}"
                            dest_path = temp_folder / new_name
                            counter += 1
                    
                    print(f"移动: {item.name} -> {dest_path}")
                    shutil.move(str(item), str(dest_path))
                
                # 删除空文件夹
                folder.rmdir()
                print(f"删除空文件夹: {folder}")
                
                # 对临时文件夹进行解散操作
                script_path = Path(__file__).parent / 'organize_folder.py'
                if script_path.exists():
                    print(f"\n解散文件夹内容: {temp_folder}")
                    try:
                        subprocess.run(['python', str(script_path), str(temp_folder), '--dissolve'], check=True)
                    except subprocess.CalledProcessError as e:
                        print(f"调用organize_folder.py失败: {e}")
                
                # 将解散后的文件移动到目标文件夹
                for item in temp_folder.iterdir():
                    final_dest = target_folder / item.name
                    if final_dest.exists():
                        base, ext = os.path.splitext(item.name)
                        counter = 1
                        while final_dest.exists():
                            new_name = f"{base}_{counter}{ext}"
                            final_dest = target_folder / new_name
                            counter += 1
                    shutil.move(str(item), str(final_dest))
                
                # 删除临时文件夹
                temp_folder.rmdir()
                
            except Exception as e:
                print(f"处理文件夹 {folder} 时出错: {e}")
                if temp_folder.exists():
                    shutil.rmtree(str(temp_folder))
        
        # 重命名文件夹（去掉part 1）
        try:
            new_name = base_name
            new_path = target_folder.parent / new_name
            if new_path.exists():
                print(f"目标路径已存在，添加数字后缀: {new_name}")
                counter = 1
                while new_path.exists():
                    new_path = target_folder.parent / f"{new_name}_{counter}"
                    counter += 1
            
            target_folder.rename(new_path)
            print(f"重命名文件夹: {target_folder.name} -> {new_path.name}")
            target_folder = new_path  # 更新target_folder为新的路径
        except Exception as e:
            print(f"重命名文件夹失败: {e}")

def get_multiple_paths(use_clipboard=False):
    """获取多个路径输入，支持剪贴板和手动输入"""
    paths = []
    
    # 从剪贴板读取路径
    if use_clipboard:
        try:
            clipboard_content = pyperclip.paste()
            if clipboard_content:
                clipboard_paths = [p.strip().strip('"') for p in clipboard_content.splitlines() if p.strip()]
                for path in clipboard_paths:
                    try:
                        normalized_path = os.path.normpath(path)
                        if os.path.exists(normalized_path):
                            paths.append(normalized_path)
                            print(f"📎 从剪贴板读取路径: {normalized_path}")
                    except Exception as e:
                        print(f"⚠️ 警告: 路径处理失败 - {path}")
                        print(f"❌ 错误信息: {str(e)}")
            else:
                print("⚠️ 剪贴板为空")
        except Exception as e:
            print(f"⚠️ 警告: 剪贴板读取失败: {str(e)}")
    
    # 如果没有使用剪贴板或剪贴板为空，使用手动输入
    if not paths:
        print("请输入目录路径（每行一个，输入空行结束）:")
        while True:
            path = input().strip()
            if not path:
                break
            
            try:
                path = path.strip().strip('"')
                normalized_path = os.path.normpath(path)
                
                if os.path.exists(normalized_path):
                    paths.append(normalized_path)
                else:
                    print(f"⚠️ 警告: 路径不存在 - {path}")
            except Exception as e:
                print(f"⚠️ 警告: 路径处理失败 - {path}")
                print(f"❌ 错误信息: {str(e)}")
    
    if not paths:
        raise ValueError("❌ 未输入有效路径")
    return paths

def main():
    parser = argparse.ArgumentParser(description='合并同名的part文件夹')
    parser.add_argument('paths', nargs='*', help='要处理的路径（可选）')
    parser.add_argument('--clipboard', '-c', action='store_true', help='从剪贴板读取路径')
    args = parser.parse_args()
    
    paths = []
    
    # 优先使用命令行参数
    if args.paths:
        paths = [os.path.normpath(p) for p in args.paths if os.path.exists(p)]
    
    # 如果没有有效的命令行参数，尝试其他输入方式
    if not paths:
        paths = get_multiple_paths(args.clipboard)
    
    # 处理每个路径
    for path in paths:
        print(f"\n开始处理路径: {path}")
        try:
            merge_part_folders(path)
        except Exception as e:
            print(f"处理路径 {path} 时出错: {e}")

if __name__ == '__main__':
    main()
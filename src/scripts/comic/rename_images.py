import os
import re
import zipfile
import tempfile
import shutil
import argparse
import pyperclip
import sys
import subprocess
import time  # 添加time模块导入
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

class InputHandler:
    """输入处理类"""
    @staticmethod
    def parse_arguments():
        parser = argparse.ArgumentParser(description='图片文件名清理工具')
        parser.add_argument('--clipboard', '-c', action='store_true', help='从剪贴板读取路径')
        parser.add_argument('--mode', '-m', choices=['image', 'zip'], help='处理模式：image(图片文件) 或 zip(压缩包)')
        parser.add_argument('path', nargs='*', help='要处理的文件或目录路径')
        return parser.parse_args()

    @staticmethod
    def get_paths_from_clipboard():
        """从剪贴板读取多行路径"""
        try:
            clipboard_content = pyperclip.paste()
            if not clipboard_content:
                return []
            paths = [path.strip().strip('"') for path in clipboard_content.splitlines() if path.strip()]
            valid_paths = [path for path in paths if os.path.exists(path)]
            if valid_paths:
                print(f'从剪贴板读取到 {len(valid_paths)} 个有效路径')
            else:
                print('剪贴板中没有有效路径')
            return valid_paths
        except Exception as e:
            print(f'读取剪贴板时出错: {e}')
            return []

    @staticmethod
    def get_input_paths(args):
        """获取输入路径"""
        paths = []
        
        # 从命令行参数获取路径
        if args.path:
            paths.extend(args.path)
            
        # 从剪贴板获取路径
        if args.clipboard:
            paths.extend(InputHandler.get_paths_from_clipboard())
            
        # 如果没有路径，提示用户输入
        if not paths:
            print("请输入要处理的文件夹或压缩包路径（每行一个，输入空行结束）：")
            while True:
                line = input().strip()
                if not line:
                    break
                path = line.strip().strip('"').strip("'")
                if os.path.exists(path):
                    paths.append(path)
                    print(f"✅ 已添加有效路径: {path}")
                else:
                    print(f"❌ 路径不存在: {path}")
                
        return [p for p in paths if os.path.exists(p)]

def backup_file(file_path, original_path, input_base_path):
    """备份文件到统一回收站目录，保持从输入路径开始的完整目录结构"""
    try:
        # 构建备份路径
        backup_base = r"E:\2EHV\.trash"
        # 计算相对路径（从输入路径开始）
        rel_path = os.path.relpath(os.path.dirname(original_path), input_base_path)
        backup_dir = os.path.join(backup_base, rel_path)
        
        # 确保备份目录存在
        os.makedirs(backup_dir, exist_ok=True)
        
        # 复制文件到备份目录
        backup_path = os.path.join(backup_dir, os.path.basename(original_path))
        shutil.copy2(file_path, backup_path)
        print(f"已备份: {backup_path}")
    except Exception as e:
        print(f"备份失败 {original_path}: {e}")

def is_ad_image(filename):
    """检查文件名是否匹配广告图片模式"""
    # 广告图片的关键词模式
    ad_patterns = [
        r'招募',
        r'credit',
        r'广告',
        r'[Cc]redit[s]?',
        r'宣传',
        r'招新',
        r'ver\.\d+\.\d+',
    ]
    
    # 合并所有模式为一个正则表达式
    combined_pattern = '|'.join(ad_patterns)
    return bool(re.search(combined_pattern, filename))

def handle_ad_file(file_path, input_base_path):
    """处理广告文件：备份并删除"""
    try:
        print(f"⚠️ 检测到广告图片: {os.path.basename(file_path)}")
        # 备份文件
        backup_file(file_path, file_path, input_base_path)
        # 删除文件
        os.remove(file_path)
        print(f"✅ 已删除广告图片")
        return True
    except Exception as e:
        print(f"❌ 删除广告图片失败: {str(e)}")
        return False

def rename_images_in_directory(dir_path):
    processed_count = 0
    skipped_count = 0
    removed_ads_count = 0  # 新增广告图片计数
    
    # 获取总文件数
    total_files = sum(1 for root, _, files in os.walk(dir_path) 
                     for f in files if f.lower().endswith(('.jpg', '.png', '.avif', '.jxl', 'webp')))
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task("处理图片文件...", total=total_files)
        
        # 遍历目录中的所有文件
        for root, dirs, files in os.walk(dir_path):
            for filename in files:
                if filename.lower().endswith(('.jpg', '.png', '.avif', '.jxl', 'webp')):
                    progress.update(task, description=f"处理: {filename}")
                    
                    # 检查是否为广告图片
                    file_path = os.path.join(root, filename)
                    if is_ad_image(filename):
                        if handle_ad_file(file_path, dir_path):
                            removed_ads_count += 1
                        progress.advance(task)
                        continue
                    
                    # 匹配文件名中的 [hash-xxxxxx] 模式
                    new_filename = re.sub(r'\[hash-[0-9a-fA-F]+\]', '', filename)
                    
                    # 如果文件名发生了变化
                    if new_filename != filename:
                        old_path = os.path.join(root, filename)
                        new_path = os.path.join(root, new_filename)
                        print(f"\n📝 处理文件: {filename}")
                        print(f"   新文件名: {new_filename}")
                        
                        # 如果目标文件已存在，先删除它
                        if os.path.exists(new_path):
                            try:
                                print(f"⚠️ 目标文件已存在，进行备份...")
                                backup_file(new_path, new_path, dir_path)
                                os.remove(new_path)
                            except Exception as e:
                                print(f"❌ 处理已存在的文件失败: {str(e)}")
                                skipped_count += 1
                                continue
                        
                        try:
                            # 备份原文件
                            backup_file(old_path, old_path, dir_path)
                            # 直接重命名
                            os.rename(old_path, new_path)
                            processed_count += 1
                            print(f"✅ 重命名成功")
                        except Exception as e:
                            print(f"❌ 重命名失败: {str(e)}")
                            skipped_count += 1
                    else:
                        skipped_count += 1
                    progress.advance(task)
    
    print(f"\n📊 处理完成:")
    print(f"   - 成功处理: {processed_count} 个文件")
    print(f"   - 删除广告: {removed_ads_count} 个文件")
    print(f"   - 跳过处理: {skipped_count} 个文件")

def has_hash_files_in_zip(zip_path):
    """快速检查压缩包中是否有包含[hash-]的文件"""
    try:
        # 使用7z列出文件
        list_cmd = ['7z', 'l', zip_path]
        result = subprocess.run(list_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"⚠️ 检查压缩包失败 {zip_path}: {result.stderr}")
            return True  # 如果检查失败，仍然继续处理
            
        # 检查文件名中是否包含[hash-]
        return '[hash-' in result.stdout
        
    except Exception as e:
        print(f"⚠️ 检查压缩包失败 {zip_path}: {e}")
        return True  # 如果出现异常，仍然继续处理

def rename_images_in_zip(zip_path, input_base_path):
    if not has_hash_files_in_zip(zip_path):
        return

    try:
        # 备份原始文件
        backup_file(zip_path, zip_path, input_base_path)
        
        # 使用7z列出文件
        list_cmd = ['7z', 'l', '-slt', zip_path]
        result = subprocess.run(list_cmd, capture_output=True, text=True)
        
        # 解析文件列表
        files_to_delete = []
        current_file = None
        for line in result.stdout.split('\n'):
            if line.startswith('Path = '):
                current_file = line[7:].strip()
                if current_file and is_ad_image(current_file):
                    files_to_delete.append(current_file)
                    print(f"⚠️ 检测到广告图片: {current_file}")
        
        if files_to_delete:
            # 构建删除命令
            delete_cmd = ['7z', 'd', zip_path] + files_to_delete
            delete_result = subprocess.run(delete_cmd, capture_output=True, text=True)
            
            if delete_result.returncode == 0:
                print(f"✅ 已从压缩包中删除 {len(files_to_delete)} 个广告图片")
            else:
                print(f"❌ 删除文件失败: {delete_result.stderr}")
        
        # 处理hash文件名
        # 使用7z重命名文件
        temp_dir = tempfile.mkdtemp()
        try:
            # 解压文件
            extract_cmd = ['7z', 'x', zip_path, f'-o{temp_dir}', '*']
            subprocess.run(extract_cmd, check=True)
            
            # 重命名文件
            renamed = False
            for root, _, files in os.walk(temp_dir):
                for filename in files:
                    new_filename = re.sub(r'\[hash-[0-9a-fA-F]+\]', '', filename)
                    if new_filename != filename:
                        old_path = os.path.join(root, filename)
                        new_path = os.path.join(root, new_filename)
                        os.rename(old_path, new_path)
                        print(f"重命名: {filename} -> {new_filename}")
                        renamed = True
            
            if renamed:
                # 重新打包
                create_cmd = ['7z', 'a', '-tzip', zip_path, f'{temp_dir}\\*']
                subprocess.run(create_cmd, check=True)
                print(f"✅ 压缩包处理完成：{zip_path}")
            
        finally:
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 7z命令执行失败: {str(e)}")
    except Exception as e:
        print(f"❌ 处理压缩包时出错: {str(e)}")
    print("继续处理下一个文件...")

if __name__ == "__main__":
    # 获取输入路径
    args = InputHandler.parse_arguments()
    
    # 如果没有指定模式，让用户选择
    if not args.mode:
        print("\n请选择处理模式：")
        print("1. 处理图片文件")
        print("2. 处理压缩包")
        while True:
            choice = input("请输入选项 (1/2): ").strip()
            if choice == '1':
                args.mode = 'image'
                break
            elif choice == '2':
                args.mode = 'zip'
                break
            else:
                print("无效的选项，请重新输入")
    
    target_paths = InputHandler.get_input_paths(args)
    
    if not target_paths:
        print("没有有效的输入路径")
        sys.exit(1)
    # 处理每个路径
    for target_path in target_paths:
        print(f"\n处理路径: {target_path}")
        input_base_path = os.path.dirname(target_path)  # 获取输入路径的父目录
        
        if os.path.isdir(target_path):
            if args.mode == 'image':
                # 直接处理文件夹中的图片
                rename_images_in_directory(target_path)
                print(f"文件夹处理完成：{target_path}")
            else:
                # 处理文件夹中的压缩包
                for root, _, files in os.walk(target_path):
                    for file in files:
                        if file.lower().endswith('.zip'):
                            zip_path = os.path.join(root, file)
                            rename_images_in_zip(zip_path, input_base_path)
        elif zipfile.is_zipfile(target_path):
            if args.mode == 'zip':
                rename_images_in_zip(target_path, input_base_path)
            else:
                print(f"警告: 当前为图片处理模式，跳过压缩包 {target_path}")
        else:
            print(f"警告: '{target_path}' 不是有效的压缩包或文件夹，跳过处理")
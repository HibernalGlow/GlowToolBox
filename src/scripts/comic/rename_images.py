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

def rename_images_in_directory(dir_path):
    processed_count = 0
    skipped_count = 0
    
    # 遍历目录中的所有文件
    print(f"\n开始处理目录: {dir_path}")
    for root, dirs, files in os.walk(dir_path):
        for filename in files:
            if filename.lower().endswith(('.jpg', '.png', '.avif', '.jxl', 'webp')):
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
                            backup_file(new_path, new_path)
                            os.remove(new_path)
                        except Exception as e:
                            print(f"❌ 处理已存在的文件失败: {str(e)}")
                            skipped_count += 1
                            continue
                    
                    try:
                        # 备份原文件
                        backup_file(old_path, old_path)
                        # 直接重命名
                        os.rename(old_path, new_path)
                        processed_count += 1
                        print(f"✅ 重命名成功")
                    except Exception as e:
                        print(f"❌ 重命名失败: {str(e)}")
                        skipped_count += 1
                else:
                    skipped_count += 1
    
    print(f"\n📊 处理完成:")
    print(f"   - 成功处理: {processed_count} 个文件")
    print(f"   - 跳过处理: {skipped_count} 个文件")
def has_hash_files_in_zip(zip_path):
    """使用7z检查压缩包中是否有包含[hash-]的文件"""
    try:
        # 使用7z列出文件列表
        result = subprocess.run(['7z', 'l', zip_path], capture_output=True, text=True)
        # 检查输出中是否包含[hash-]
        return '[hash-' in result.stdout
    except Exception as e:
        print(f"检查压缩包失败 {zip_path}: {e}")
        return False

def rename_images_in_zip(zip_path, input_base_path):
    """直接重命名压缩包内的文件，不解压"""
    # 先检查压缩包中是否有需要处理的文件
    if not has_hash_files_in_zip(zip_path):
        return

    new_zip_path = None  # 初始化变量
    try:
        # 创建新的压缩包路径
        original_dir = os.path.dirname(zip_path)
        file_name = os.path.splitext(os.path.basename(zip_path))[0]
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        new_zip_path = os.path.join(original_dir, f'{file_name}.new.zip')
        
        # 备份原始文件（使用完整路径）
        backup_file(zip_path, zip_path, input_base_path)

        # 使用7z重命名文件
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            with zipfile.ZipFile(new_zip_path, 'w', zipfile.ZIP_DEFLATED) as new_zip:
                for item in zip_ref.infolist():
                    # 读取原始文件内容
                    with zip_ref.open(item.filename) as source:
                        data = source.read()
                        
                    # 处理文件名
                    new_filename = re.sub(r'\[hash-[0-9a-fA-F]+\]', '', item.filename)
                    
                    # 如果文件名没有变化，直接写入
                    if new_filename == item.filename:
                        new_zip.writestr(item, data)
                    else:
                        # 创建新的ZipInfo对象以保留原始文件属性
                        new_info = zipfile.ZipInfo(new_filename)
                        new_info.date_time = item.date_time
                        new_info.compress_type = item.compress_type
                        new_info.create_system = item.create_system
                        new_info.external_attr = item.external_attr
                        new_zip.writestr(new_info, data)
                        print(f"重命名: {item.filename} -> {new_filename}")

        # 检查新压缩包大小
        if os.path.getsize(new_zip_path) > os.path.getsize(zip_path) + 1024*1024:
            print(f"警告: 新压缩包大小增加超过1MB，还原备份")
            os.remove(new_zip_path)
            return

        # 替换原始文件
        os.replace(new_zip_path, zip_path)
        print(f"压缩包处理完成：{zip_path}")
        
    except Exception as e:
        print(f"❌ 处理压缩包时出错: {str(e)}")
        if new_zip_path and os.path.exists(new_zip_path):
            os.remove(new_zip_path)
    finally:
        # 清理临时目录
        print(f"🧹 清理临时目录: {temp_dir}")
        shutil.rmtree(temp_dir)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as new_zip:
            # 将处理后的文件添加到zip中
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    new_zip.write(file_path, arcname)
        
        print(f"压缩包处理完成：{zip_path}")
        
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
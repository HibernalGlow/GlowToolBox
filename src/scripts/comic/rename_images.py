import os
import re
import zipfile
import tempfile
import shutil
import argparse
import pyperclip

class InputHandler:
    """输入处理类"""
    @staticmethod
    def parse_arguments():
        parser = argparse.ArgumentParser(description='图片文件名清理工具')
        parser.add_argument('--clipboard', '-c', action='store_true', help='从剪贴板读取路径')
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

def backup_original_files(original_path, files_to_rename):
    """备份要重命名的文件到 trash 文件夹"""
    try:
        if not files_to_rename:
            return
            
        # 创建 trash 目录
        base_name = os.path.basename(original_path)
        if base_name.endswith('.zip'):
            base_name = base_name[:-4]
        trash_dir = os.path.join(os.path.dirname(original_path), f'{base_name}.trash')
        os.makedirs(trash_dir, exist_ok=True)
        
        # 备份文件
        for file_path, new_name in files_to_rename:
            try:
                # 计算相对路径
                rel_path = os.path.relpath(file_path, original_path)
                # 创建备份目标路径
                dest_path = os.path.join(trash_dir, rel_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                # 复制文件
                shutil.copy2(file_path, dest_path)
            except Exception as e:
                print(f"❌ 备份文件失败 {file_path}: {e}")
                
        print(f"已备份原始文件到: {trash_dir}")
    except Exception as e:
        print(f"❌ 备份过程出错: {e}")

def rename_images_in_directory(dir_path):
    """重命名目录中的图片文件"""
    files_to_rename = []
    # 遍历目录中的所有文件
    for root, dirs, files in os.walk(dir_path):
        for filename in files:
            if filename.lower().endswith(('.jpg', '.png', '.avif', '.jxl')):
                # 匹配文件名中的 [hash-xxxxxx] 模式
                new_filename = re.sub(r'\[hash-[0-9a-fA-F]+\]', '', filename)
                
                # 如果文件名发生了变化
                if new_filename != filename:
                    old_path = os.path.join(root, filename)
                    new_path = os.path.join(root, new_filename)
                    files_to_rename.append((old_path, new_path))
    
    # 如果有文件需要重命名，先备份
    if files_to_rename:
        backup_original_files(dir_path, files_to_rename)
        # 执行重命名
        for old_path, new_path in files_to_rename:
            os.rename(old_path, new_path)

def rename_images_in_zip(zip_path):
    """处理压缩包中的图片文件"""
    temp_dir = tempfile.mkdtemp()
    try:
        # 解压文件
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # 重命名文件（包含备份）
        rename_images_in_directory(temp_dir)
        
        # 直接覆盖原始压缩包
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as new_zip:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    new_zip.write(file_path, arcname)
        
        print(f"压缩包处理完成：{zip_path}")
    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    # 获取输入路径
    args = InputHandler.parse_arguments()
    target_paths = InputHandler.get_input_paths(args)
    
    if not target_paths:
        print("没有有效的输入路径")
        sys.exit(1)
        
    # 处理每个路径
    for target_path in target_paths:
        print(f"\n处理路径: {target_path}")
        
        if os.path.isdir(target_path):
            # 直接处理文件夹
            rename_images_in_directory(target_path)
            print(f"文件夹处理完成：{target_path}")
        elif zipfile.is_zipfile(target_path):
            rename_images_in_zip(target_path)
        else:
            print(f"警告: '{target_path}' 不是有效的压缩包或文件夹，跳过处理")
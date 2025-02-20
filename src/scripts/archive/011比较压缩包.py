import os
import filecmp
import shutil
from pathlib import Path
import tempfile
from tqdm import tqdm
import subprocess

def extract_with_7z(archive_path, extract_path):
    """
    使用7z命令行解压文件
    """
    try:
        # 执行7z命令解压
        result = subprocess.run([
            "7z",
            "x",
            archive_path,
            f"-o{extract_path}",
            "-y"  # 自动回答yes
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"7z解压失败: {result.stderr}")
            
    except FileNotFoundError:
        raise Exception("未找到7z命令，请确保已安装7-Zip并添加到系统环境变量")

def compare_archives(archive1_path, archive2_path, output_dir, ignore_path_diff=False):
    """
    比较两个压缩文件的差异
    """
    print("正在解压文件...")
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir1 = os.path.join(temp_dir, 'archive1')
        temp_dir2 = os.path.join(temp_dir, 'archive2')
        
        # 使用7z解压两个文件
        print("正在解压第一个压缩包...")
        extract_with_7z(archive1_path, temp_dir1)
        print("正在解压第二个压缩包...")
        extract_with_7z(archive2_path, temp_dir2)
        
        print("正在比较文件...")
        # 获取文件列表
        files1 = set()
        files2 = set()
        
        # 遍历第一个目录
        for root, _, files in os.walk(temp_dir1):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, temp_dir1)
                if ignore_path_diff:
                    files1.add(os.path.basename(rel_path))
                else:
                    files1.add(rel_path)
                    
        # 遍历第二个目录
        for root, _, files in os.walk(temp_dir2):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, temp_dir2)
                if ignore_path_diff:
                    files2.add(os.path.basename(rel_path))
                else:
                    files2.add(rel_path)
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 比较文件并复制差异
        different_files = set()
        
        # 找出只在一个压缩包中存在的文件
        different_files.update(files1 - files2)
        different_files.update(files2 - files1)
            
        # 比较共同文件的内容
        common_files = files1 & files2
        print("正在比较共同文件...")
        for file in tqdm(common_files, desc="比较文件内容"):
            if ignore_path_diff:
                # 查找具有相同文件名的所有文件
                file1_paths = []
                file2_paths = []
                for root, _, files in os.walk(temp_dir1):
                    if file in files:
                        file1_paths.append(os.path.join(root, file))
                for root, _, files in os.walk(temp_dir2):
                    if file in files:
                        file2_paths.append(os.path.join(root, file))
                
                # 比较所有可能的组合
                files_different = True
                for path1 in file1_paths:
                    for path2 in file2_paths:
                        if filecmp.cmp(path1, path2, shallow=False):
                            files_different = False
                            break
                    if not files_different:
                        break
                
                if files_different:
                    different_files.add(file)
            else:
                file1_path = os.path.join(temp_dir1, file)
                file2_path = os.path.join(temp_dir2, file)
                if not filecmp.cmp(file1_path, file2_path, shallow=False):
                    different_files.add(file)
        
        # 复制差异文件到���出目录
        print("正在复制差异文件...")
        for file in tqdm(different_files, desc="复制差异文件"):
            if ignore_path_diff:
                # 复制所有同名文件
                output_subdir = os.path.join(output_dir, "archive1")
                os.makedirs(output_subdir, exist_ok=True)
                for root, _, files in os.walk(temp_dir1):
                    if file in files:
                        src = os.path.join(root, file)
                        dst = os.path.join(output_subdir, os.path.relpath(src, temp_dir1))
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(src, dst)
                
                output_subdir = os.path.join(output_dir, "archive2")
                os.makedirs(output_subdir, exist_ok=True)
                for root, _, files in os.walk(temp_dir2):
                    if file in files:
                        src = os.path.join(root, file)
                        dst = os.path.join(output_subdir, os.path.relpath(src, temp_dir2))
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(src, dst)
            else:
                # 分别复制两个压缩包中的文件
                if file in files1:
                    src = os.path.join(temp_dir1, file)
                    dst = os.path.join(output_dir, "archive1", file)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                if file in files2:
                    src = os.path.join(temp_dir2, file)
                    dst = os.path.join(output_dir, "archive2", file)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
        
        return different_files

if __name__ == "__main__":
    # 获取用户输入并去除可能存在的引号和首尾空格
    archive1_path = input("请输入第一个压缩包的路径: ").strip().strip('"').strip("'")
    archive2_path = input("请输入第二个压缩包的路径: ").strip().strip('"').strip("'")
    output_dir = input("请输入输出目录的路径: ").strip().strip('"').strip("'")
    ignore_path_diff = input("是否忽略路径差异? (y/n): ").strip().lower() == 'y'
    
    try:
        different_files = compare_archives(archive1_path, archive2_path, output_dir, ignore_path_diff)
        print("\n发现的差异文件：")
        for file in different_files:
            print(f"- {file}")
        print(f"\n差异文件已保存到: {output_dir}")
    except Exception as e:
        print(f"发生错误: {type(e).__name__}")
        print(f"错误信息: {str(e)}")
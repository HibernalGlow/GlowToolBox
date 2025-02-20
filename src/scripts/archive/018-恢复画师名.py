import os
import yaml
import subprocess
from tqdm import tqdm

def read_yaml_from_archive(archive_path):
    """从压缩包中读取YAML文件内容"""
    try:
        command = ['7z', 'l', archive_path]
        result = subprocess.run(command, capture_output=True, encoding='utf-8', errors='ignore', check=True)
        yaml_file = None
        
        for line in result.stdout.splitlines():
            if line.endswith('.yaml'):
                yaml_file = line.split()[-1]
                break
                
        if yaml_file:
            extract_command = ['7z', 'e', archive_path, f'./{yaml_file}', '-so']
            process = subprocess.Popen(extract_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = process.communicate()
            
            if error and b"Unknown switch" in error:
                extract_command = ['7z', 'e', archive_path, yaml_file, '-so']
                process = subprocess.Popen(extract_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                output, error = process.communicate()
            
            for encoding in ['utf-8', 'utf-8-sig', 'gbk', 'shift-jis']:
                try:
                    yaml_text = output.decode(encoding)
                    yaml_content = yaml.safe_load(yaml_text)
                    
                    if isinstance(yaml_content, list):
                        artist_name = yaml_content[-1].get('ArtistName', '').strip("'")
                        if artist_name:
                            return artist_name
                    break
                except UnicodeDecodeError:
                    continue
    except Exception as e:
        print(f"处理压缩包时发生错误: {e}")
    return None

def has_yaml_file(archive_path):
    """检查压缩包是否包含YAML文件"""
    try:
        command = ['7z', 'l', archive_path]
        result = subprocess.run(command, capture_output=True, encoding='utf-8', errors='ignore', check=True)
        return any(line.endswith('.yaml') for line in result.stdout.splitlines())
    except Exception:
        return False

def find_first_archive(folder_path):
    """递归查找文件夹中第一个包含YAML的压缩包"""
    for file in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file)
        if os.path.isfile(file_path) and file.endswith(('.zip', '.rar', '.7z')):
            if has_yaml_file(file_path):
                return file_path
            
    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)
        if os.path.isdir(item_path):
            archive = find_first_archive(item_path)
            if archive:
                return archive
                
    return None

def process_artist_folders(target_directory):
    """处理画师文件夹的重命名"""
    folders = [f for f in os.listdir(target_directory) if os.path.isdir(os.path.join(target_directory, f))]
    
    for folder_name in tqdm(folders, desc="处理画师文件夹"):
        folder_path = os.path.join(target_directory, folder_name)
        
        archive_file = find_first_archive(folder_path)
        if not archive_file:
            print(f"警告: 文件夹中未找到包含YAML的压缩包: {folder_path}")
            continue
            
        artist_name = read_yaml_from_archive(archive_file)
        if artist_name and artist_name != folder_name:
            new_folder_path = os.path.join(target_directory, artist_name)
            try:
                os.rename(folder_path, new_folder_path)
                print(f"已重命名: {folder_path} -> {new_folder_path}")
            except Exception as e:
                print(f"重命名失败 {folder_path}: {e}")

if __name__ == '__main__':
    target_directory = input("请输入路径: ").strip().strip('"')
    process_artist_folders(target_directory)
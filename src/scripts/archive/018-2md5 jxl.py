import os
import hashlib
import shutil
import yaml
import logging

# 配置
source_directory = input("请输入图片文件夹目录路径: ")  # 源文件夹目录
target_directory = r'E:\1BACKUP\ehv\bak\output'
mode_choice = input("请选择模式（1: 重命名模式，2: 恢复模式）: ")
is_rename_mode = True if mode_choice == '1' else False  # 根据用户输入选择模式
overwrite_existing = False # 控制是否覆盖
yaml_file = "folder_mapping.yaml"  # 记录 MD5 和原名对应关系的 yaml 文件
log_file = "process_log.log"  # 日志文件

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()  # 控制台输出
    ]
)

def calculate_md5(folder_name):
    """计算文件夹名的 MD5 值"""
    md5_hash = hashlib.md5(folder_name.encode()).hexdigest()
    return md5_hash

def find_image_only_folders(source_dir):
    """找到所有不包含子文件夹且包含任意图片文件的文件夹"""
    image_extensions = ['.jxl']
    valid_folders = []

    for root, dirs, files in os.walk(source_dir):
        # 如果该文件夹没有子文件夹
        if not dirs:
            # 检查文件夹中是否包含任意图片文件
            contains_images = any(file.lower().endswith(tuple(image_extensions)) for file in files)
            if contains_images:  # 只要有一个图片文件即可
                valid_folders.append(root)

    return valid_folders

def rename_and_copy_folder(folder_path, target_dir, overwrite):
    """重命名文件夹并复制到目标文件夹"""
    folder_name = os.path.basename(folder_path)
    md5_name = calculate_md5(folder_name)
    new_folder_path = os.path.join(target_dir, md5_name)

    # 检查目标文件夹是否已经存在
    if os.path.exists(new_folder_path):
        if overwrite:
            logging.warning(f"目标文件夹 {new_folder_path} 已存在，准备覆盖。")
            shutil.rmtree(new_folder_path)  # 删除已有的文件夹
            shutil.copytree(folder_path, new_folder_path)
            logging.info(f"文件夹 {folder_name} 已覆盖并重命名为 {md5_name}")
        else:
            logging.warning(f"目标文件夹 {new_folder_path} 已存在，跳过复制。")
    else:
        shutil.copytree(folder_path, new_folder_path)
        logging.info(f"文件夹 {folder_name} 已复制并重命名为 {md5_name}")

    return folder_name, new_folder_path

def save_to_yaml(mapping, yaml_path):
    """将 MD5 和原名对应关系保存到 YAML 文件"""
    with open(yaml_path, 'w', encoding='utf-8') as file:
        yaml.dump(mapping, file, allow_unicode=True)

def load_from_yaml(yaml_path):
    """从 YAML 文件加载 MD5 和原名的对应关系"""
    if not os.path.exists(yaml_path):
        return {}
    with open(yaml_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def restore_folder_name(md5_name, original_name, original_path):
    """恢复文件夹原名，不论是否能覆盖原路径"""
    folder_path = os.path.join(target_directory, md5_name)
    if os.path.exists(folder_path):
        original_folder_path = os.path.join(original_path, original_name)
        
        # 检查原文件夹路径是否存在，如果存在则删除原文件夹
        if os.path.exists(original_folder_path):
            try:
                shutil.rmtree(original_folder_path)
                logging.info(f"原文件夹 {original_folder_path} 已删除。")
            except Exception as e:
                logging.error(f"删除原文件夹 {original_folder_path} 时出错: {e}")
        else:
            logging.warning(f"原文件夹路径 {original_folder_path} 不存在，跳过删除。")

        # 将 MD5 文件夹恢复为原名
        try:
            shutil.move(folder_path, original_folder_path)
            logging.info(f"文件夹 {md5_name} 已恢复为原名 {original_name} 并移动至 {original_folder_path}")
        except Exception as e:
            logging.error(f"移动文件夹 {md5_name} 到 {original_folder_path} 时出错: {e}")
    else:
        logging.warning(f"文件夹 {md5_name} 不存在，无法恢复")

def rename_mode():
    """重命名模式逻辑"""
    valid_folders = find_image_only_folders(source_directory)
    if valid_folders:
        mapping = load_from_yaml(yaml_file)
        for folder in valid_folders:
            folder_name, new_folder_path = rename_and_copy_folder(folder, target_directory, overwrite_existing)
            # 保存 MD5 和原名对应关系
            mapping[calculate_md5(folder_name)] = {'original_name': folder_name, 'original_path': os.path.dirname(folder)}
        save_to_yaml(mapping, yaml_file)
    else:
        logging.info("没有找到符合条件的文件夹。")

def restore_mode():
    """恢复模式逻辑"""
    mapping = load_from_yaml(yaml_file)
    if mapping:
        for md5_name, info in mapping.items():
            restore_folder_name(md5_name, info['original_name'], info['original_path'])
    else:
        logging.info("没有找到恢复信息。")

# 主逻辑
if __name__ == "__main__":
    if is_rename_mode:
        rename_mode()
    else:
        restore_mode()

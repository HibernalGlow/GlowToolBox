import os
import yaml
import subprocess
from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

YAML_OUTPUT_PATH = r'E:\1BACKUP\ehv\uuid-upscale.yaml'

def load_existing_records():
    """加载已存在的记录"""
    if os.path.exists(YAML_OUTPUT_PATH):
        try:
            with open(YAML_OUTPUT_PATH, 'r', encoding='utf-8') as f:
                existing_records = yaml.safe_load(f) or []
                # 创建UUID到记录的映射
                return {
                    record['UUID']: record for record in existing_records
                }, {
                    record['Path']: record for record in existing_records
                }
        except Exception as e:
            print(f"读取现有记录时发生错误: {e}")
    return {}, {}

def load_yaml_uuid_from_archive(archive_path):
    """从压缩包中获取YAML文件的UUID"""
    try:
        command = ['7z', 'l', archive_path]
        result = subprocess.run(command, capture_output=True, text=True, check=True)

        for line in result.stdout.splitlines():
            line = line.strip()
            if line.endswith('.yaml'):
                parts = line.split()
                yaml_filename = parts[-1]
                yaml_uuid = os.path.splitext(yaml_filename)[0]
                return yaml_uuid
    except Exception as e:
        print(f"处理文件 {archive_path} 时发生错误: {e}")
    return None

def process_single_archive(archive_path, uuid_records, path_records):
    """处理单个压缩文件并返回其UUID"""
    try:
        # 检查路径是否已存在
        archive_path = str(Path(archive_path))
        if archive_path in path_records:
            return None

        uuid = load_yaml_uuid_from_archive(archive_path)
        if uuid:
            # 检查UUID是否已存在且路径不同
            if uuid in uuid_records and uuid_records[uuid]['Path'] != archive_path:
                print(f"警告: UUID {uuid} 已存在于不同路径:")
                print(f"现有: {uuid_records[uuid]['Path']}")
                print(f"新的: {archive_path}")
                return None
            
            return {
                'UUID': uuid,
                'Path': archive_path,
                'FileName': os.path.basename(archive_path)
            }
    except Exception as e:
        print(f"处理文件 {archive_path} 时发生错误: {e}")
    return None

def save_to_yaml(results):
    """将结果保存到YAML文件"""
    with open(YAML_OUTPUT_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(results, f, allow_unicode=True, sort_keys=False)

def main():
    target_directory = input("请输入要扫描的路径: ").strip().strip('"')
    
    # 加载现有记录
    uuid_records, path_records = load_existing_records()
    print(f"已加载 {len(uuid_records)} 条现有记录")

    # 收集所有ZIP和CBZ文件
    archive_files = []
    for root, _, files in os.walk(target_directory):
        for file in files:
            if file.lower().endswith(('.zip', '.cbz')):
                archive_files.append(os.path.join(root, file))

    new_results = []
    # 使用线程池处理文件
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(process_single_archive, archive, uuid_records, path_records) 
                  for archive in archive_files]
        for future in tqdm(as_completed(futures), total=len(futures), desc="处理文件"):
            result = future.result()
            if result:
                new_results.append(result)

    # 合并新旧记录
    all_results = list(uuid_records.values()) + new_results

    # 将结果保存到YAML文件
    save_to_yaml(all_results)

    print(f"处理完成，新增 {len(new_results)} 个记录")
    print(f"当前总记录数: {len(all_results)}")
    print(f"结果已保存到: {YAML_OUTPUT_PATH}")

if __name__ == '__main__':
    main()
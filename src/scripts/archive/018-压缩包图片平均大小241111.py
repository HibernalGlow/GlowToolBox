import zipfile
import shutil
import yaml
import subprocess
import os
from pathlib import Path
from tqdm import tqdm
from datetime import datetime

# 添加YAML记录路径
YAML_OUTPUT_PATH = r'E:\1BACKUP\ehv\image-size-records.yaml'

def contains_tdel_file(directory):
    """检查目录中是否包含 .artistdel 文件"""
    return any(directory.glob("*.artistdel"))

def contains_keywords_in_zip(zip_path, keywords):
    """检查压缩包内的文件名是否包含指定关键词"""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            for file_info in zip_file.filelist:
                if any(keyword in file_info.filename for keyword in keywords):
                    return True
    except Exception as e:
        print(f"无法检查压缩包 {zip_path}: {str(e)}")
    return False

def check_images_in_zip(zip_path, min_size_kb=0, max_size_kb=500):
    """检查压缩包中的图片平均大小"""
    image_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.avif', '.jxl', '.gif', '.bmp')
    image_count = 0
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            for file_info in zip_file.filelist:
                if file_info.filename.lower().endswith(image_extensions):
                    image_count += 1
        
        if image_count == 0:
            return {
                'valid': False,
                'avg_size': 0,
                'message': "无图片文件",
                'image_count': 0
            }
        
        file_size_kb = zip_path.stat().st_size / 1024
        avg_size = file_size_kb / image_count
        
        return {
            'valid': min_size_kb <= avg_size <= max_size_kb,
            'avg_size': avg_size,
            'message': f"平均: {avg_size:.2f}KB, 数量: {image_count}",
            'image_count': image_count
        }
        
    except zipfile.BadZipFile:
        return {'valid': False, 'avg_size': 0, 'message': "无效压缩包", 'image_count': 0}
    except Exception as e:
        return {'valid': False, 'avg_size': 0, 'message': f"错误: {str(e)}", 'image_count': 0}

def load_yaml_uuid_from_archive(zip_path):
    """从压缩包中获取YAML文件的UUID"""
    try:
        command = ['7z', 'l', str(zip_path)]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if line.strip().endswith('.yaml'):
                parts = line.strip().split()
                yaml_filename = parts[-1]
                return os.path.splitext(yaml_filename)[0]
    except Exception as e:
        tqdm.write(f"获取UUID时出错 {zip_path}: {str(e)}")
    return None

def load_or_save_records(records=None):
    """加载或保存YAML记录"""
    if records is None:
        if os.path.exists(YAML_OUTPUT_PATH):
            try:
                with open(YAML_OUTPUT_PATH, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or []
            except Exception as e:
                print(f"读取记录出错: {e}")
                return []
        return []
    else:
        try:
            with open(YAML_OUTPUT_PATH, 'w', encoding='utf-8') as f:
                yaml.dump(records, f, allow_unicode=True, sort_keys=False, indent=2)
        except Exception as e:
            print(f"保存记录出错: {e}")

def collect_zip_files(source_dir, skip_tdel=False):
    """收集所有zip文件"""
    source_dir = Path(source_dir)
    zip_files = []
    
    if not source_dir.exists():
        print(f"源目录不存在: {source_dir}")
        return []
        
    # 收集直接位于source_dir的zip文件
    zip_files.extend(source_dir.glob("*.zip"))
    
    # 收集子目录中的zip文件
    for subdir in source_dir.iterdir():
        if subdir.is_dir():
            if skip_tdel and contains_tdel_file(subdir):
                print(f"跳过文件夹: {subdir} (包含.artistdel文件)")
                continue
            zip_files.extend(subdir.rglob("*.zip"))
    
    return sorted(zip_files)

def analyze_zip_files(zip_files, source_dir):
    """分析所有zip文件并返回结果列表"""
    results = []
    
    for zip_path in tqdm(zip_files, desc="分析文件"):
        result = {
            'path': zip_path,
            'rel_path': zip_path.relative_to(source_dir),
            'size': zip_path.stat().st_size,
            'uuid': load_yaml_uuid_from_archive(zip_path),
            'size_check': None,
            'keyword_check': None,
            'selected': False
        }
        results.append(result)
    
    return results

def apply_size_filter(file_results, min_size_kb, max_size_kb):
    """应用大小筛选"""
    for result in tqdm(file_results, desc="检查文件大小"):
        size_info = check_images_in_zip(result['path'], min_size_kb, max_size_kb)
        result['size_check'] = size_info
        result['selected'] = result['selected'] or size_info['valid']

def apply_keyword_filter(file_results, keywords):
    """应用关键词筛选"""
    for result in tqdm(file_results, desc="检查关键词"):
        has_keywords = contains_keywords_in_zip(result['path'], keywords)
        result['keyword_check'] = has_keywords
        result['selected'] = result['selected'] and has_keywords

def copy_selected_files(file_results, target_dir, records):
    """复制选中的文件并更新记录"""
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    
    copied_count = 0
    total_size = 0
    
    for result in tqdm(file_results, desc="复制文件"):
        if not result['selected']:
            continue
            
        if result['uuid'] and any(record.get('UUID') == result['uuid'] for record in records):
            continue
            
        try:
            # 获取源文件的完整路径
            source_path = result['path']
            
            # 计算目标路径：保持源文件的相对路径结构
            # 如果源文件路径是 "E:/source/dir1/dir2/file.zip"
            # 目标路径将是 "target_dir/dir1/dir2/file.zip"
            target_path = target_dir / source_path.name
            
            # 创建目标目录（如果不存在）
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            shutil.copy2(source_path, target_path)
            
            # 创建记录
            if result['uuid']:
                record = {
                    'UUID': result['uuid'],
                    'Path': str(source_path.name),  # 只记录文件名
                    'FileName': source_path.name,
                    '文件大小': f"{result['size']/1024/1024:.2f}MB",
                    '平均图片大小': f"{result['size_check']['avg_size']:.2f}KB",
                    '检查时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                records.append(record)
            
            copied_count += 1
            total_size += result['size']
            
            # 输出信息
            message = f"{source_path.name}"
            if result['size_check']:
                message += f" - {result['size_check']['message']}"
            message += f" - {result['size']/1024/1024:.2f}MB"
            tqdm.write(f"{message} - 已复制")
            
        except Exception as e:
            tqdm.write(f"复制文件出错 {result['path']}: {str(e)}")
    
    return copied_count, total_size

def scan_directory(source_dir, min_size_kb=0, max_size_kb=500, enable_copy=False, 
                  target_dir=None, skip_tdel=False, keywords=None, enable_keyword_check=False):
    """主函数：扫描目录并处理文件"""
    # 1. 收集所有zip文件
    zip_files = collect_zip_files(source_dir, skip_tdel)
    if not zip_files:
        print("未找到zip文件")
        return
    print(f"共找到 {len(zip_files)} 个zip文件")
    
    # 2. 加载现有记录
    records = load_or_save_records()
    print(f"已加载 {len(records)} 条记录")
    
    # 3. 分析所有文件
    file_results = analyze_zip_files(zip_files, Path(source_dir))
    
    # 4. 应用筛选条件
    if min_size_kb is not None and max_size_kb is not None:
        apply_size_filter(file_results, min_size_kb, max_size_kb)
    
    if enable_keyword_check and keywords:
        apply_keyword_filter(file_results, keywords)
    
    # 5. 复制文件并更新记录
    if enable_copy and target_dir:
        copied_count, total_size = copy_selected_files(file_results, target_dir, records)
        load_or_save_records(records)
        
        print(f"\n已复制 {copied_count} 个文件")
        print(f"总大小: {total_size/1024/1024:.2f}MB")
    else:
        # 只显示统计信息
        selected = [r for r in file_results if r['selected']]
        total_size = sum(r['size'] for r in selected)
        print(f"\n符合条件的文件数: {len(selected)}")
        print(f"总大小: {total_size/1024/1024:.2f}MB")

if __name__ == "__main__":
    source_dir = r"E:\1EHV\[emily]"
    target_dir = r"E:\2EHV"
    min_size = 10    # 最小平均大小 (KB)
    max_size = 200000    # 最大平均大小 (KB)
    enable_copy = False  # 是否启用复制功能
    skip_tdel = False   # 是否跳过包含.artistdel文件的文件夹
    keywords = ['.jxl']  # 关键词列表
    enable_keyword_check = True  # 是否启用关键词检查功能
    
    scan_directory(
        source_dir=source_dir,
        min_size_kb=min_size,
        max_size_kb=max_size,
        enable_copy=enable_copy,
        target_dir=target_dir if enable_copy else None,
        skip_tdel=skip_tdel,
        keywords=keywords,
        enable_keyword_check=enable_keyword_check
    )
    print("\n处理完成")
import zipfile
import shutil
import os
from pathlib import Path
from tqdm import tqdm

def collect_zip_files(source_dir):
    """收集目录下所有zip文件"""
    source_dir = Path(source_dir)
    if not source_dir.exists():
        print(f"源目录不存在: {source_dir}")
        return []
        
    # 收集所有zip文件（包括子目录）
    zip_files = list(source_dir.rglob("*.zip"))
    
    if not zip_files:
        print(f"未找到zip文件")
        return []
        
    print(f"共找到 {len(zip_files)} 个zip文件")
    return sorted(zip_files)

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

def analyze_zip_file(zip_path, min_size_kb=None, max_size_kb=None, keywords=None):
    """分析单个zip文件"""
    result = {
        'path': zip_path,
        'size': zip_path.stat().st_size,
        'selected': True
    }
    
    # 检查大小
    if min_size_kb is not None and max_size_kb is not None:
        size_info = check_images_in_zip(zip_path, min_size_kb, max_size_kb)
        result['size_check'] = size_info
        result['selected'] = result['selected'] and size_info['valid']
    
    # 检查关键词
    if keywords:
        has_keywords = contains_keywords_in_zip(zip_path, keywords)
        result['keyword_check'] = has_keywords
        result['selected'] = result['selected'] and has_keywords
    
    return result

def copy_files(source_files, target_dir):
    """复制文件到目标目录"""
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    
    copied_count = 0
    total_size = 0
    
    for file_info in tqdm(source_files, desc="复制文件"):
        if not file_info['selected']:
            continue
            
        try:
            source_path = file_info['path']
            target_path = target_dir / source_path.name
            
            # 复制文件
            shutil.copy2(source_path, target_path)
            
            copied_count += 1
            total_size += file_info['size']
            
            # 输出信息
            message = f"{source_path.name}"
            if 'size_check' in file_info:
                message += f" - {file_info['size_check']['message']}"
            message += f" - {file_info['size']/1024/1024:.2f}MB"
            tqdm.write(f"{message} - 已复制")
            
        except Exception as e:
            tqdm.write(f"复制文件出错 {source_path}: {str(e)}")
    
    return copied_count, total_size

def process_directory(source_dir, target_dir, min_size_kb=None, max_size_kb=None, keywords=None, do_copy=True):
    """处理源目录"""
    # 收集所有zip文件
    zip_files = collect_zip_files(source_dir)
    if not zip_files:
        return
    
    # 分析文件
    file_results = []
    keyword_count = 0
    selected_size = 0  # 添加符合条件文件的总大小统计
    for file_path in tqdm(zip_files, desc="分析文件"):
        result = analyze_zip_file(
            file_path, 
            min_size_kb, 
            max_size_kb,
            keywords
        )
        if keywords and result.get('keyword_check'):
            keyword_count += 1
        if result['selected']:
            selected_size += result['size']  # 累计符合条件文件的大小
        file_results.append(result)
    
    # 输出统计信息
    total_files = len(zip_files)
    selected_files = sum(1 for r in file_results if r['selected'])
    print(f"\n符合条件的文件: {selected_files}/{total_files}")
    print(f"符合条件的文件总大小: {selected_size/1024/1024:.2f}MB")
    
    if keywords:
        keyword_percentage = (keyword_count / total_files) * 100 if total_files > 0 else 0
        print(f"包含关键词的文件: {keyword_count}/{total_files} ({keyword_percentage:.2f}%)")
    
    # 根据开关决定是否复制文件
    if do_copy:
        copied_count, total_size = copy_files(file_results, target_dir)
        print(f"已复制: {copied_count} 个文件")
        print(f"已复制总大小: {total_size/1024/1024:.2f}MB")
    else:
        print("仅分析模式，未执行复制操作")

if __name__ == "__main__":
    # 配置参数
    config = {
        'source_dir': r"E:\1EHV",  # 源目录
        'target_dir': r"E:\2EHV",          # 目标目录
        # 'min_size_kb': None,    # 最小平均大小 (KB)，设为 None 禁用大小检查
        'min_size_kb': 1000,    
        # 'max_size_kb': None,    # 最大平均大小 (KB)，设为 None 禁用大小检查
        'max_size_kb': 5000,    
        # 'keywords': ['.jxl'],   # 关键词列表，设为 None 禁用关键词检查
        'keywords': None,   # 关键词列表，设为 None 禁用关键词检查
        'do_copy': False,        # 是否执行复制操作
    }
    
    process_directory(**config)
    print("\n处理完成")
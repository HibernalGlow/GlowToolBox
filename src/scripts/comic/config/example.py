from pathlib import Path
from .filter_manager import FilterManager

def main():
    # 创建过滤器管理器
    manager = FilterManager()
    
    # 添加小图过滤器
    manager.add_filter('small', {
        'min_size': 631
    })
    
    # 添加灰度图过滤器
    manager.add_filter('grayscale', {})
    
    # 添加重复图片过滤器
    manager.add_filter('duplicate', {
        'hamming_distance': 0,
        'ref_hamming_distance': 12,
        'hash_file': 'path/to/hash/file.json'  # 可选
    })
    
    # 准备要处理的图片路径列表
    image_paths = [
        Path('path/to/image1.jpg'),
        Path('path/to/image2.png'),
        # ...更多图片路径
    ]
    
    # 使用所有过滤器处理图片
    results = manager.process_images(image_paths)
    
    # 获取所有需要删除的文件
    removed_files, removal_reasons = manager.get_all_removed_files(results)
    
    # 打印结果
    print("\n处理结果:")
    for filter_type, result in results.items():
        print(f"\n{filter_type}过滤器:")
        print(f"- 需要删除的文件数: {len(result['removed_files'])}")
        for file_path in result['removed_files']:
            reason = result['removal_reasons'][file_path]
            print(f"  - {file_path.name}: {reason}")
    
    print("\n所有需要删除的文件:")
    for file_path in removed_files:
        reason = removal_reasons[file_path]
        print(f"- {file_path.name}: {reason}")

if __name__ == '__main__':
    main() 
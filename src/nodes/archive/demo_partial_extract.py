import argparse
import json
import os
import zipfile
import tempfile
import random
from nodes.archive.partial_extractor import PartialExtractor

def generate_test_zip(file_count=20):
    """生成测试用ZIP文件
    
    Args:
        file_count (int): 要生成的测试文件数量
        
    Returns:
        tuple: (zip文件路径, 文件名列表)
    """
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "test7dsfwefe.zip")
    
    # 生成文件列表
    file_names = [f"test_{i+1}.jpg" for i in range(file_count)]
    
    # 创建ZIP文件
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for file_name in file_names:
            content = f"这是测试文件 {file_name} 的内容"
            zf.writestr(file_name, content)
    
    return zip_path, file_names

def verify_extraction(target_dir, expected_files):
    """验证解压结果
    
    Args:
        target_dir (str): 解压目标目录
        expected_files (list): 期望解压出的文件列表
        
    Returns:
        bool: 验证是否通过
    """
    # 获取实际解压的文件列表
    actual_files = set(os.listdir(target_dir))
    expected_files = set(expected_files)
    
    # 验证文件数量和内容
    if actual_files != expected_files:
        print(f"文件列表不匹配！")
        print(f"期望文件: {expected_files}")
        print(f"实际文件: {actual_files}")
        return False
    
    # 验证每个文件的内容
    for file_name in actual_files:
        with open(os.path.join(target_dir, file_name), 'r') as f:
            content = f.read()
            expected_content = f"这是测试文件 {file_name} 的内容"
            if content != expected_content:
                print(f"文件 {file_name} 内容不匹配！")
                return False
    
    return True

def main():
    parser = argparse.ArgumentParser(
        description="部分解压测试工具",
        formatter_class=argparse.RawTextHelpFormatter  # 保留格式
    )
    # 新增自动化测试参数
    parser.add_argument('--manual', action='store_true',
                      help='使用手动模式（需要指定压缩包路径和范围配置）')
    parser.add_argument('--test_files', type=int, default=20,
                      help='自动化测试生成的文件数量（默认：20）')
    parser.add_argument('--test_mode', choices=['index','selection','step','slice'], default='slice',
                      help='自动化测试模式（默认：slice）')
    parser.add_argument('--slice_type', choices=['head','tail'], default='head',
                      help='切片类型：head=前N张，tail=后N张（默认：head）')
    parser.add_argument('--slice_count', type=int, default=5,
                      help='切片数量（默认：5）')
    
    # 手动模式参数
    parser.add_argument('--archive_path', help='压缩包路径（支持ZIP/7Z格式）')
    parser.add_argument('--target_dir', default='./extracted', help='解压目标目录')
    parser.add_argument('--range_control', help='范围控制配置的JSON字符串')
    
    args = parser.parse_args()
    
    try:
        # 确保目标目录存在
        os.makedirs(args.target_dir, exist_ok=True)
        
        if not args.manual:
            print(f"开始自动测试模式: {args.test_mode}")
            print(f"测试文件数量: {args.test_files}")
            
            # 生成测试ZIP
            zip_path, file_names = generate_test_zip(args.test_files)
            print(f"已生成测试ZIP文件: {zip_path}")
            print(f"包含文件数量: {len(file_names)}")
            print("\n生成的文件列表:")
            for i, name in enumerate(file_names):
                print(f"{i}: {name}")
            
            # 根据测试模式生成范围配置
            if args.test_mode == 'slice':
                count = min(args.slice_count, args.test_files)
                if args.slice_type == 'head':
                    # 提取前N张
                    range_config = {
                        'ranges': [(0, count - 1)],
                        'combine': 'union'
                    }
                    print(f"\n提取前{count}张图片")
                else:
                    # 提取后N张
                    range_config = {
                        'ranges': [(args.test_files - count, args.test_files - 1)],
                        'combine': 'union'
                    }
                    print(f"\n提取后{count}张图片")
                
                print("预期选择的文件:")
                if args.slice_type == 'head':
                    for i in range(count):
                        print(f"{i}: {file_names[i]}")
                else:
                    for i in range(args.test_files - count, args.test_files):
                        print(f"{i}: {file_names[i]}")
            
            elif args.test_mode == 'index':
                start = random.randint(0, min(5, args.test_files-1))
                end = random.randint(start+5, args.test_files-1)
                range_config = {
                    'ranges': [(start, end)],
                    'combine': 'union'
                }
                print(f"\n使用索引模式，范围: {start} - {end}")
                print("预期选择的文件:")
                for i in range(start, end + 1):
                    print(f"{i}: {file_names[i]}")
            
            elif args.test_mode == 'selection':
                count = min(5, args.test_files)
                indices = sorted(random.sample(range(args.test_files), count))
                # 将选择的索引转换为范围列表
                ranges = []
                for idx in indices:
                    ranges.append((idx, idx + 1))  # 每个选中的索引转换为范围
                range_config = {
                    'ranges': ranges,
                    'combine': 'union'
                }
                print(f"\n使用选择模式，选中索引: {indices}")
                print("预期选择的文件:")
                for i in indices:
                    print(f"{i}: {file_names[i]}")
            
            elif args.test_mode == 'step':
                step = 2
                count = min(5, (args.test_files - 3) // step + 1)
                # 生成步进范围
                ranges = []
                start = 3
                for i in range(count):
                    current = start + i * step
                    if current < args.test_files:
                        ranges.append((current, current + 1))
                range_config = {
                    'ranges': ranges,
                    'combine': 'union'
                }
                print(f"\n使用步进模式，起始: 3, 步长: {step}, 数量: {count}")
                print("预期选择的文件:")
                indices = [r[0] for r in ranges]
                for i in indices:
                    print(f"{i}: {file_names[i]}")
            
            print(f"\n使用配置: {json.dumps(range_config, indent=2, ensure_ascii=False)}")
            
            # 执行解压测试
            success = PartialExtractor.partial_extract(
                archive_path=zip_path,
                target_dir=args.target_dir,
                range_control=range_config
            )
            
            # 计算预期的文件列表
            expected_files = []
            if args.test_mode == 'slice':
                if args.slice_type == 'head':
                    expected_files = file_names[:args.slice_count]
                else:
                    expected_files = file_names[-args.slice_count:]
            elif args.test_mode == 'index':
                expected_files = file_names[range_config['ranges'][0][0]:range_config['ranges'][0][1] + 1]
            elif args.test_mode == 'selection':
                indices = [r[0] for r in range_config['ranges']]
                expected_files = [file_names[i] for i in indices]
            elif args.test_mode == 'step':
                indices = [r[0] for r in range_config['ranges']]
                expected_files = [file_names[i] for i in indices]
            
            # 验证解压结果
            if success:
                verify_result = verify_extraction(args.target_dir, expected_files)
                if verify_result:
                    print("\n✅ 测试成功：解压完成且验证通过！")
                else:
                    print("\n❌ 测试失败：解压完成但验证未通过！")
            else:
                print("\n❌ 测试失败：解压过程出错！")
            
            print(f"\n解压结果保存在：{os.path.abspath(args.target_dir)}")
            
        else:
            # 手动模式
            if not args.archive_path or not args.range_control:
                raise ValueError("手动模式需要指定 --archive_path 和 --range_control 参数")
            
            range_config = json.loads(args.range_control)
            success = PartialExtractor.partial_extract(
                archive_path=args.archive_path,
                target_dir=args.target_dir,
                range_control=range_config
            )
            print(f"手动模式：解压{'成功' if success else '失败'}！")
            print(f"结果保存在：{os.path.abspath(args.target_dir)}")
        
    except json.JSONDecodeError:
        print("错误：range_control参数必须是有效的JSON格式")
    except Exception as e:
        print(f"错误：{str(e)}")

if __name__ == "__main__":
    main()
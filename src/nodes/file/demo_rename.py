import os
import logging
from directory_handler import PathManager

def demo_rename_files():
    # 设置日志格式
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # 创建测试文件
    test_dir = os.path.join(os.path.dirname(__file__), 'test_files')
    os.makedirs(test_dir, exist_ok=True)

    # 创建示例文件
    test_files = [
        'test1.txt',
        'test2.txt',
        'test3.txt'
    ]

    for file in test_files:
        file_path = os.path.join(test_dir, file)
        with open(file_path, 'w') as f:
            f.write(f'This is {file}')

    # 测试文件系统中的文件重命名
    try:
        # 重命名第一个文件
        original_path = os.path.join(test_dir, 'test1.txt')
        new_name = 'renamed_file'
        new_path = PathManager.rename_file_in_filesystem(original_path, new_name)
        logging.info(f'成功重命名文件: {original_path} -> {new_path}')

        # 测试重复文件名处理
        original_path = os.path.join(test_dir, 'test2.txt')
        new_path = PathManager.rename_file_in_filesystem(original_path, new_name)
        logging.info(f'成功重命名文件（自动处理重复）: {original_path} -> {new_path}')

        # 测试压缩包内文件重命名路径生成
        archive_path = os.path.join(test_dir, 'test3.txt')
        new_archive_path = PathManager.rename_file_in_archive(archive_path, 'archive_renamed')
        logging.info(f'生成压缩包内文件重命名路径: {archive_path} -> {new_archive_path}')

    except Exception as e:
        logging.error(f'重命名操作失败: {str(e)}')

    # 清理测试文件
    try:
        for root, _, files in os.walk(test_dir):
            for file in files:
                os.remove(os.path.join(root, file))
        os.rmdir(test_dir)
        logging.info('清理测试文件完成')
    except Exception as e:
        logging.error(f'清理测试文件失败: {str(e)}')

if __name__ == '__main__':
    demo_rename_files()
import os
import logging
import zipfile
from directory_handler import PathManager

def demo_rename_files():
    # 设置日志格式
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # 创建测试目录
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

    # 创建测试压缩包
    zip_path = os.path.join(test_dir, 'test_archive.zip')
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for file in test_files:
            file_path = os.path.join(test_dir, file)
            zf.write(file_path, file)  # 将文件添加到压缩包，使用相对路径

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

        # 测试压缩包内文件重命名
        archive_path = os.path.join(test_dir, 'test_archive.zip')
        file_in_archive = 'test3.txt'
        new_name_in_archive = 'archive_renamed'
        
        # 创建临时目录
        temp_dir = PathManager.create_temp_directory(archive_path)
        
        # 解压文件
        with zipfile.ZipFile(archive_path, 'r') as zf:
            zf.extractall(temp_dir)
        
        # 重命名解压后的文件
        original_file = os.path.join(temp_dir, file_in_archive)
        new_path = PathManager.rename_file_in_filesystem(original_file, new_name_in_archive)
        
        # 创建新的压缩包
        new_zip_path = archive_path + '.new'
        with zipfile.ZipFile(new_zip_path, 'w') as zf:
            # 添加重命名后的文件
            zf.write(new_path, os.path.basename(new_path))
            # 添加其他未重命名的文件
            for file in os.listdir(temp_dir):
                if file != file_in_archive:
                    file_path = os.path.join(temp_dir, file)
                    zf.write(file_path, file)
        
        # 替换原压缩包
        os.replace(new_zip_path, archive_path)
        logging.info(f'成功重命名压缩包内文件: {file_in_archive} -> {new_name_in_archive}')

        # 清理临时目录
        PathManager.cleanup_temp_files(temp_dir, new_zip_path, None)

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
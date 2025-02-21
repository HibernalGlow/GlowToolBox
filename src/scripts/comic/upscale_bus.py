import os
import shutil
import zipfile
import subprocess
import json
from datetime import datetime
import concurrent.futures
import send2trash  # 添加send2trash库用于将文件移动到回收站
from nodes.record.logger_config import setup_logger
config = {
    'script_name': 'upscale_bus',
}
logger, config_info = setup_logger(config)

def remove_empty_directories(directory):
    """删除指定目录下的所有空文件夹"""
    removed_count = 0
    for root, dirs, _ in os.walk(directory, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                if not os.listdir(dir_path):  # 检查文件夹是否为空
                    os.rmdir(dir_path)
                    removed_count += 1
                    logger.info(f"已删除空文件夹: {dir_path}")
            except Exception as e:
                logger.info(f"删除空文件夹失败 {dir_path}: {e}")
    return removed_count

def remove_temp_files(directory):
    """删除指定目录下的所有 .tdel 和 .bak 文件"""
    removed_count = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(('.tdel', '.bak')):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    removed_count += 1
                    logger.info(f"已删除临时文件: {file_path}")
                except Exception as e:
                    logger.info(f"删除临时文件失败 {file_path}: {e}")
    return removed_count

def count_files_in_zip(zip_path):
    """统计zip文件中的文件数量，忽略特定类型的文件"""
    ignore_extensions = ('.md', '.yaml', '.yml', '.txt', '.json', '.db', '.ini')
    try:
        with zipfile.ZipFile(zip_path) as zip_file:
            # 过滤掉要忽略的文件类型和目录条目
            valid_files = [name for name in zip_file.namelist() 
                         if not name.lower().endswith(ignore_extensions)
                         and not name.endswith('/')  # 排除目录条目
                         and zip_file.getinfo(name).file_size > 0]  # 排除0字节的目录占位文件
            return len(valid_files)
    except Exception as e:
        logger.info(f"读取zip文件失败 {zip_path}: {str(e)}")
        return 0

def compare_and_copy_archives(source_dir, target_dir, is_move=False):
    # 记录处理结果
    success_count = 0
    skip_count = 0
    error_files = []
    
    # 遍历源目录
    for root, _, files in os.walk(source_dir):
        for file in files:
            if file.endswith(('.cbz', '.zip')):
                # 构建源文件和目标文件的路径
                source_path = os.path.join(root, file)
                rel_path = os.path.relpath(root, source_dir)
                
                # 所有文件都使用zip扩展名
                source_file = file.replace('.cbz', '.zip') if file.endswith('.cbz') else file
                target_file = source_file  # 目标文件也用zip扩展名
                
                temp_source = os.path.join(root, source_file)
                target_path = os.path.join(target_dir, rel_path, target_file)
                
                # 确保目标目录存在
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                
                # 如果是cbz，改名为zip
                if file.endswith('.cbz'):
                    os.rename(source_path, temp_source)
                
                try:
                    # 如果目标文件不存在，直接复制或移动
                    if not os.path.exists(target_path):
                        if is_move:
                            shutil.move(temp_source, target_path)
                            logger.info(f"移动文件: {file} -> {target_file}")
                        else:
                            shutil.copy2(temp_source, target_path)
                            logger.info(f"新文件复制: {file} -> {target_file}")
                        success_count += 1
                    else:
                        # 比较文件数量（忽略特定类型文件）
                        source_count = count_files_in_zip(temp_source)
                        target_count = count_files_in_zip(target_path)
                            
                        if source_count == target_count:
                            if is_move:
                                try:
                                    send2trash.send2trash(target_path)  # 将原文件移动到回收站
                                    logger.info(f"已将原文件移动到回收站: {target_path}")
                                    shutil.move(temp_source, target_path)
                                    logger.info(f"移动并覆盖: {file} -> {target_file}")
                                except Exception as e:
                                    logger.info(f"移动到回收站失败: {str(e)}")
                                    continue
                            else:
                                try:
                                    send2trash.send2trash(target_path)  # 将原文件移动到回收站
                                    logger.info(f"已将原文件移动到回收站: {target_path}")
                                    shutil.copy2(temp_source, target_path)
                                    logger.info(f"覆盖文件: {file} -> {target_file}")
                                except Exception as e:
                                    logger.info(f"移动到回收站失败: {str(e)}")
                                    continue
                            success_count += 1
                            logger.info(f"有效文件数量: {source_count}")
                        else:
                            skip_count += 1
                            error_msg = f"跳过: {file} - 文件数量不一致 (源:{source_count}, 目标:{target_count})"
                            error_files.append(error_msg)
                            logger.info(error_msg)

                except Exception as e:
                    skip_count += 1
                    error_msg = f"错误: {file} - {str(e)}"
                    error_files.append(error_msg)
                    logger.info(error_msg)
    
    # 如果是移动模式，删除源目录中的空文件夹
    if is_move:
        removed_count = remove_empty_directories(source_dir)
        logger.info(f"\n已删除 {removed_count} 个空文件夹")
    
    # 打印总结
    logger.info("\n处理完成！")
    logger.info(f"成功处理: {success_count} 个文件")
    logger.info(f"跳过处理: {skip_count} 个文件")
    if error_files:
        logger.info("\n详细错误列表:")
        for error in error_files:
            logger.info(error)

def check_archive(file_path):
    """检测压缩包是否损坏"""
    try:
        result = subprocess.run(['7z', 't', file_path], 
                              capture_output=True, 
                              text=True)
        return result.returncode == 0
    except Exception as e:
        logger.info(f"检测文件 {file_path} 时发生错误: {str(e)}")
        return False

def load_check_history(history_file):
    """加载检测历史记录，只读取最后一行有效数据"""
    history = {}
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # 逆序读取，找到最后一个有效行
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    file_path = entry.get('path')
                    if file_path and file_path not in history:
                        history[file_path] = {
                            'time': entry.get('timestamp'),
                            'valid': entry.get('valid')
                        }
                except json.JSONDecodeError:
                    continue  # 跳过不完整的行
    return history

def save_check_history(history_file, new_entry):
    """追加方式保存检测记录，每行一个完整的JSON对象"""
    try:
        # 只保留timestamp字段
        new_entry['timestamp'] = datetime.now().isoformat()
        # 删除旧的time字段
        if 'time' in new_entry:
            del new_entry['time']
        with open(history_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(new_entry, ensure_ascii=False) + '\n')
    except Exception as e:
        logger.info(f"保存检查记录失败: {str(e)}")

def process_corrupted_archives(directory, skip_checked=True, max_workers=4):
    """处理目录下的损坏压缩包"""
    archive_extensions = ('.zip', '.rar', '.7z', '.cbz')
    history_file = os.path.join(directory, 'archive_check_history.json')
    
    # 添加这行初始化check_history
    check_history = load_check_history(history_file)
    
    # 删除temp_开头的文件夹
    for root, dirs, _ in os.walk(directory, topdown=True):
        for dir_name in dirs[:]:
            if dir_name.startswith('temp_'):
                try:
                    dir_path = os.path.join(root, dir_name)
                    logger.info(f"正在删除临时文件夹: {dir_path}")
                    shutil.rmtree(dir_path)
                except Exception as e:
                    logger.info(f"删除文件夹 {dir_path} 时发生错误: {str(e)}")

    # 收集需要处理的文件
    files_to_process = []
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.lower().endswith(archive_extensions):
                file_path = os.path.join(root, filename)
                if file_path.endswith('.tdel'):
                    continue
                if skip_checked and file_path in check_history and check_history[file_path]['valid']:
                    logger.info(f"跳过已检查且完好的文件: {file_path}")
                    continue
                files_to_process.append(file_path)

    def process_single_file(file_path):
        logger.info(f"正在检测: {file_path}")
        is_valid = check_archive(file_path)
        return {
            'path': file_path,
            'valid': is_valid,
            'timestamp': datetime.now().isoformat()
        }

    # 使用线程池处理文件
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for file_path in files_to_process:
            future = executor.submit(process_single_file, file_path)
            futures.append(future)
        
        # 处理结果
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            file_path = result['path']
            is_valid = result['valid']
            
            check_history[file_path] = {
                'timestamp': result['timestamp'],
                'valid': is_valid
            }
            
            # 保存时改为调用新的保存方法
            save_check_history(history_file, {
                'path': file_path,
                'valid': is_valid,
                'timestamp': datetime.now().isoformat()
            })
            
            if not is_valid:
                new_path = file_path + '.tdel'
                if os.path.exists(new_path):
                    try:
                        os.remove(new_path)
                        logger.info(f"删除已存在的文件: {new_path}")
                    except Exception as e:
                        logger.info(f"删除文件 {new_path} 时发生错误: {str(e)}")
                        continue
                
                try:
                    os.rename(file_path, new_path)
                    logger.info(f"文件损坏,已重命名为: {new_path}")
                except Exception as e:
                    logger.info(f"重命名文件时发生错误: {str(e)}")
            else:
                logger.info(f"文件完好")

if __name__ == "__main__":
    # 定义目录路径列表
    directory_pairs = [
        ("D:\\3EHV", "E:\\7EHV"),
        ("E:\\7EHV", "E:\\999EHV"),
    ]
    is_move = True  # 设置为True则移动文件，False则复制文件
    
    # 依次处理每对目录
    for source_dir, target_dir in directory_pairs:
        logger.info(f"\n开始处理目录对：")
        logger.info(f"源目录: {source_dir}")
        logger.info(f"目标目录: {target_dir}")
        
        if not os.path.exists(source_dir):
            logger.info("源目录不存在！")
            continue
        elif not os.path.exists(target_dir):
            logger.info("目标目录不存在！")
            continue
            
        # 先检测损坏的压缩包
        logger.info("\n开始检测损坏压缩包...")
        process_corrupted_archives(source_dir)
        
        # 删除临时文件
        temp_files_removed = remove_temp_files(source_dir)
        logger.info(f"\n已删除 {temp_files_removed} 个临时文件")
        
        # 执行文件移动/复制操作
        compare_and_copy_archives(source_dir, target_dir, is_move)

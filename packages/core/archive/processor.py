from src.core.image_processor import ImageProcessor
from src.core.duplicate_detector import DuplicateDetector
from src.utils.archive_utils import ArchiveUtils
from src.services.logging_service import LoggingService
from src.services.backup_service import BackupService
from src.utils.path_utils import PathManager
import logging
import os
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from send2trash import send2trash
from src.utils.directory_handler import DirectoryHandler
import time
from src.utils.archive_utils import ArchiveUtil
from src.utils.archive_utils import ArchiveExtractor
from src.utils.hash_utils import HashFileHandler
from src.utils.path_utils import PathManager
from src.utils.archive_utils import ArchiveUtils
import os
import json
from src.handler.processed_log_handler import ProcessedLogHandler
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.services.backup_service import BackupService
from src.config.settings import Settings
from pics.calculate_hash_custom import PathURIGenerator



class ArchiveProcessor:
    """
    类描述
    """
    @staticmethod
    def merge_archives(paths, params):
        """
        合并压缩包为一个临时压缩包进行处理
        
        Args:
            paths: 压缩包路径列表或文件夹路径列表
            params: 参数字典
        
        Returns:
            (temp_dir, merged_zip_path, archive_paths): 临时目录、合并后的压缩包路径和原始压缩包路径列表
        """
        temp_dir = None
        try:
            archive_paths = []
            for path in paths:
                if os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        archive_paths.extend((os.path.join(root, file) for file in files if file.lower().endswith('.zip')))
                elif path.lower().endswith('.zip'):
                    archive_paths.append(path)

            # 新增备份步骤：为每个要合并的压缩包创建备份
            for zip_path in archive_paths:
                backup_path = zip_path + '.bak'
                try:
                    if not os.path.exists(backup_path):
                        shutil.copy2(zip_path, backup_path)
                        logging.info(f"[#file_ops]已创建合并前备份: {backup_path}")
                except Exception as e:
                    logging.error(f"[#file_ops]创建合并前备份失败 {zip_path}: {e}")

            if not archive_paths:
                logging.info( f"❌ 没有找到要处理的压缩包")
                return (None, None, None)
                
            directories = {os.path.dirname(path) for path in archive_paths}
            if len(directories) > 1:
                logging.info( f"❌ 所选压缩包不在同一目录")
                return (None, None, None)
            base_dir = list(directories)[0]
            timestamp = int(time.time() * 1000)
            temp_dir = os.path.join(base_dir, f'temp_merge_{timestamp}')
            os.makedirs(temp_dir, exist_ok=True)
            for zip_path in archive_paths:
                logging.info( f'解压: {zip_path}')
                archive_name = os.path.splitext(os.path.basename(zip_path))[0]
                archive_temp_dir = os.path.join(temp_dir, archive_name)
                os.makedirs(archive_temp_dir, exist_ok=True)
                success, error = ArchiveUtils.run_7z_command('x', zip_path, '解压文件', [f'-o{archive_temp_dir}', '-y'])
                if not success:
                    logging.info( f"❌ 解压失败: {zip_path}\n错误: {error}")
                    PathManager.cleanup_temp_files(temp_dir, None, None)
                    return (None, None, None)
            merged_zip_path = os.path.join(base_dir, f'merged_{timestamp}.zip')
            logging.info( '创建合并压缩包')
            success, error = ArchiveUtils.run_7z_command('a', merged_zip_path, '创建合并压缩包', ['-tzip', os.path.join(temp_dir, '*')])
            if not success:
                logging.info( f"❌ 创建合并压缩包失败: {error}")
                PathManager.cleanup_temp_files(temp_dir, None, None)
                return (None, None, None)
            return (temp_dir, merged_zip_path, archive_paths)
        except Exception as e:
            logging.info( f"❌ 合并压缩包时出错: {e}")
            if temp_dir and os.path.exists(temp_dir):
                PathManager.cleanup_temp_files(temp_dir, None, None)
            return (None, None, None)

    @staticmethod
    def process_single_archive(file_path, params):
        """处理单个压缩包文件"""
        try:
            logging.info( f"开始处理文件: {file_path}")
            
            if not os.path.exists(file_path):
                logging.info( f"❌ 文件不存在: {file_path}")
                return []
                
            cmd = ['7z', 'l', file_path]
            result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                logging.info( f"❌ 压缩包可能损坏: {file_path}")
                return []
                
            if result.stdout is None:
                logging.info( f"❌ 无法读取压缩包内容: {file_path}")
                return []
                
            has_images = any((line.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.jxl', '.avif', '.jxl')) 
                            for line in result.stdout.splitlines()))
            if not has_images:
                logging.info( f"⚠️ 跳过无图片的压缩包: {file_path}")
                return []
                
            processed_archives = []
            
                
            if not params['ignore_processed_log']:
                if ProcessedLogHandler.has_processed_log(file_path):
                    logging.info( f"⚠️ 文件已有处理记录: {file_path}")
                    return processed_archives
                    
            logging.info( "开始处理压缩包内容...")
            processed_archives.extend(ArchiveProcessor.process_archive_in_memory(file_path, params))
            
            if processed_archives:
                # 更新重复信息面板
                info = processed_archives[-1]
                logging.info( 
                    f"处理结果:\n"
                    f"- 哈希重复: {info.get('hash_duplicates_removed', 0)} 张\n"
                    f"- 普通重复: {info.get('normal_duplicates_removed', 0)} 张\n"
                    f"- 小图: {info.get('small_images_removed', 0)} 张\n"
                    f"- 白图: {info.get('white_images_removed', 0)} 张\n"
                    f"- 减少大小: {info['size_reduction_mb']:.2f} MB"
                )
                
                # 更新进度面板
                logging.info( f"✅ 成功处理: {os.path.basename(file_path)}")
                    
                if params['add_processed_log_enabled']:
                    processed_info = {
                        'hash_duplicates_removed': info.get('hash_duplicates_removed', 0),
                        'normal_duplicates_removed': info.get('normal_duplicates_removed', 0),
                        'small_images_removed': info.get('small_images_removed', 0),
                        'white_images_removed': info.get('white_images_removed', 0)
                    }
                    ProcessedLogHandler.add_processed_log(file_path, processed_info)
                    logging.info( "已添加处理日志")
            else:
                logging.info( f"⚠️ 压缩包处理完成，但没有需要处理的内容: {file_path}")
                
            backup_file_path = file_path + '.bak'
            if os.path.exists(backup_file_path):
                BackupService.handle_bak_file(backup_file_path, params)
                logging.info( "已处理备份文件")
                
            return processed_archives
            
        except UnicodeDecodeError as e:
            logging.info( f"❌ 处理压缩包时出现编码错误 {file_path}: {e}")
            return []
        except Exception as e:
            logging.info( f"❌ 处理文件时发生异常: {file_path}\n{str(e)}")
            return []

    @staticmethod
    def split_merged_archive(processed_zip, original_archives, temp_dir, params):
        """
        将处理后的合并压缩包拆分回原始压缩包
        
        Args:
            processed_zip: 处理后的合并压缩包路径
            original_archives: 原始压缩包路径列表
            temp_dir: 临时目录路径
            params: 参数字典
        """
        try:
            logging.info( '开始拆分处理后的压缩包')
            extract_dir = os.path.join(temp_dir, 'processed')
            os.makedirs(extract_dir, exist_ok=True)
            success, error = ArchiveUtils.run_7z_command('x', processed_zip, '解压处理后的压缩包', [f'-o{extract_dir}', '-y'])
            if not success:
                logging.info( f"❌ 解压处理后的压缩包失败: {error}")
                return False
            for original_zip in original_archives:
                archive_name = os.path.splitext(os.path.basename(original_zip))[0]
                source_dir = os.path.join(extract_dir, archive_name)
                if not os.path.exists(source_dir):
                    logging.info( f"⚠️ 找不到对应的目录: {source_dir}")
                    continue
                new_zip = original_zip + '.new'
                success, error = ArchiveUtils.run_7z_command('a', new_zip, '创建新压缩包', ['-tzip', os.path.join(source_dir, '*')])
                if success:
                    try:
                        if params.get('backup_removed_files_enabled', True):
                            send2trash(original_zip)
                        else:
                            os.remove(original_zip)
                        os.rename(new_zip, original_zip)
                        logging.info( f'成功更新压缩包: {original_zip}')
                    except Exception as e:
                        logging.info( f"❌ 替换压缩包失败 {original_zip}: {e}")
                else:
                    logging.info( f"❌ 创建新压缩包失败 {new_zip}: {error}")
            return True
        except Exception as e:
            logging.info( f"❌ 拆分压缩包时出错: {e}")
            return False

    @staticmethod
    def handle_size_comparison(file_path, new_zip_path, backup_file_path):
        """
        比较新旧文件大小并处理替换
        
        Args:
            file_path: 原始文件路径
            new_zip_path: 新压缩包路径
            backup_file_path: 备份文件路径
        
        Returns:
            (success, size_change): 处理是否成功和文件大小变化(MB)
        """
        try:
            if not os.path.exists(new_zip_path):
                logging.info( f"❌ 新压缩包不存在: {new_zip_path}")
                return (False, 0)
            original_size = os.path.getsize(file_path)
            new_size = os.path.getsize(new_zip_path)
            REDUNDANCY_SIZE = 1 * 1024 * 1024
            if new_size >= original_size + REDUNDANCY_SIZE:
                logging.info( f"⚠️ 新压缩包 ({new_size / 1024 / 1024:.2f}MB) 未比原始文件 ({original_size / 1024 / 1024:.2f}MB) 小超过1MB，还原备份")
                os.remove(new_zip_path)
                if os.path.exists(backup_file_path):
                    os.replace(backup_file_path, file_path)
                return (False, 0)
            os.replace(new_zip_path, file_path)
            size_change = (original_size - new_size) / (1024 * 1024)
            logging.info( f'更新压缩包: {file_path} (减少 {size_change:.2f}MB)')
            return (True, size_change)
        except Exception as e:
            logging.info( f"❌ 比较文件大小时出错: {e}")
            if os.path.exists(backup_file_path):
                os.replace(backup_file_path, file_path)
            if os.path.exists(new_zip_path):
                os.remove(new_zip_path)
            return (False, 0)

    @staticmethod
    def process_archive_in_memory(file_path, params):
        """处理单个压缩包的主函数"""
        processed_archives = []
        temp_dir = None
        backup_file_path = None
        new_zip_path = None
        try:
            logging.info(f"[#file_ops]开始处理压缩包: {file_path}")

            temp_dir, backup_file_path, new_zip_path = ArchiveExtractor.prepare_archive(file_path)
            if not temp_dir:
                logging.info(f"[#file_ops]❌ 准备环境失败: {file_path}")
                return []
                
            logging.info(f"[#file_ops]环境准备完成")
            
            image_files = ArchiveExtractor.get_image_files(temp_dir)
            if not image_files:
                logging.info(f"[#file_ops]⚠️ 未找到图片文件")
                PathManager.cleanup_temp_files(temp_dir, new_zip_path, backup_file_path)
                return []
                
            
            removed_files = set()
            duplicate_files = set()
            removal_reasons = {}  # 初始化removal_reasons
            lock = threading.Lock()
            existing_file_names = set()
            image_processor = ImageProcessor()
            # image_processor.set_global_hashes(global_hashes)  # 设置全局哈希
            
            # 添加zip_path到params
            params['zip_path'] = file_path
            
            # 在处理图片时显示进度
            with ThreadPoolExecutor(max_workers=params['max_workers']) as executor:
                futures = []
                total_files = len(image_files)
                processed_files = 0
                
                for img_path in image_files:
                    rel_path = os.path.relpath(img_path, temp_dir)
                    future = executor.submit(
                        image_processor.process_single_image, 
                        img_path, 
                        rel_path, 
                        existing_file_names, 
                        params, 
                        lock
                    )
                    futures.append((future, img_path))
                    
                image_hashes = []
                for future, img_path in futures:
                    try:
                        img_hash, img_data, _, reason = future.result()
                        processed_files += 1
                        percentage = (processed_files / total_files) * 100
                        logging.info(f"[#cur_progress=]处理图片 ({processed_files}/{total_files}) {percentage:.1f}%")
                        
                        if reason in ['small_image', 'white_image']:
                            removed_files.add(img_path)
                            removal_reasons[img_path] = reason
                        elif img_hash is not None and params['remove_duplicates']:
                            image_hashes.append((img_hash, img_data, img_path, reason))
                            
                    except Exception as e:
                        logging.info(f"[#hash_calc]❌ 处理图片失败 {img_path}: {e}")
                        processed_files += 1
                        percentage = (processed_files / total_files) * 100
                        logging.info(f"[#hash_calc=]处理图片 ({processed_files}/{total_files}) {percentage:.1f}%")

            if params['remove_duplicates'] and image_hashes:
                unique_images, _, dup_removal_reasons = DuplicateDetector.remove_duplicates_in_memory(image_hashes, params)
                removal_reasons.update(dup_removal_reasons)  # 合并删除原因
                processed_files = {img[2] for img in unique_images}
                for img_hash, _, img_path, _ in image_hashes:
                    if img_path not in processed_files:
                        duplicate_files.add(img_path)
                        
                # 处理完成后，将临时哈希更新到全局哈希
                # if image_processor.temp_hashes:
                #     with lock:
                #         global_hashes.update(image_processor.temp_hashes)
                #         logging.info(f"[#hash_calc]已批量添加 {len(image_processor.temp_hashes)} 个哈希到全局缓存")
                #         # 清空临时存储
                #         image_processor.temp_hashes.clear()

            # 保存更新后的缓存
            # ImageHashCalculator.save_global_hashes(global_hashes)  # 注释掉原来的全局保存
            
            # 为当前压缩包保存哈希文件
            zip_path = params.get('zip_path')
            if zip_path:
                zip_dir = os.path.dirname(zip_path)
                zip_name = os.path.splitext(os.path.basename(zip_path))[0]                
                # 构建压缩包特定的哈希字典
                zip_hashes = {}
                for img_hash, _, img_path, _ in image_hashes:
                    if img_hash:
                        rel_path = os.path.relpath(img_path, temp_dir)
                        img_uri = PathURIGenerator.generate(f"{zip_path}!{rel_path}")
                        # 统一哈希值格式：如果是字典则提取hash字段
                        hash_value = img_hash['hash'] if isinstance(img_hash, dict) else img_hash
                        zip_hashes[img_uri] = {"hash": hash_value}  # 直接存储为新格式
                
                # 保存到collection文件
                try:
                    # 确保目录存在
                    os.makedirs(os.path.dirname(Settings.HASH_COLLECTION_FILE), exist_ok=True)
                    
                    # 读取现有collection
                    collection_data = {
                        "_hash_params": "hash_size=10;hash_version=1",
                        "dry_run": False,
                        "hashes": {}
                    }
                    
                    if os.path.exists(Settings.HASH_COLLECTION_FILE):
                        try:
                            with open(Settings.HASH_COLLECTION_FILE, 'r', encoding='utf-8') as f:
                                file_content = f.read().strip()
                                if not file_content:  # 文件为空
                                    logging.info(f"[#hash_calc]Collection文件为空，将创建新文件")
                                    collection_data = {
                                        "_hash_params": "hash_size=10;hash_version=1",
                                        "dry_run": False,
                                        "hashes": {}
                                    }
                                else:
                                    try:
                                        loaded_data = json.loads(file_content)
                                        if not isinstance(loaded_data, dict):
                                            raise ValueError("JSON数据格式不正确，不是字典格式")
                                            
                                        # 保留原有的元数据
                                        collection_data = {
                                            "_hash_params": loaded_data.get("_hash_params", "hash_size=10;hash_version=1"),
                                            "dry_run": loaded_data.get("dry_run", False),
                                            "hashes": {}
                                        }
                                        
                                        # 处理哈希数据
                                        if "hashes" in loaded_data and isinstance(loaded_data["hashes"], dict):
                                            collection_data["hashes"] = loaded_data["hashes"]
                                        else:
                                            # 尝试处理旧格式
                                            for uri, hash_value in loaded_data.items():
                                                if uri not in ["_hash_params", "dry_run"]:
                                                    if isinstance(hash_value, str):
                                                        collection_data["hashes"][uri] = {"hash": hash_value}
                                                    elif isinstance(hash_value, dict) and "hash" in hash_value:
                                                        collection_data["hashes"][uri] = hash_value
                                                        
                                        logging.info(f"[#hash_calc]成功读取Collection文件，包含 {len(collection_data['hashes'])} 个哈希值")
                                        
                                    except json.JSONDecodeError as je:
                                        # 检查文件内容，输出更详细的错误信息
                                        logging.error(f"[#hash_calc]JSON解析错误: {str(je)}")
                                        logging.error(f"[#hash_calc]文件内容预览: {file_content[:200]}...")
                                        raise  # 重新抛出异常，让外层处理
                                        
                        except (json.JSONDecodeError, ValueError) as e:
                            # 只有在确实是JSON格式错误时才创建备份
                            error_time = int(time.time())
                            backup_path = f"{Settings.HASH_COLLECTION_FILE}.error_{error_time}"
                            shutil.copy2(Settings.HASH_COLLECTION_FILE, backup_path)
                            logging.error(f"[#hash_calc]Collection文件格式错误，已备份到: {backup_path}")
                            logging.error(f"[#hash_calc]错误详情: {str(e)}")
                            # 创建新的collection数据结构
                            collection_data = {
                                "_hash_params": "hash_size=10;hash_version=1",
                                "dry_run": False,
                                "hashes": {}
                            }
                        except Exception as e:
                            logging.error(f"[#hash_calc]读取Collection文件时发生未知错误: {str(e)}")
                            raise  # 对于其他类型的错误，向上抛出
                    else:
                        logging.info(f"[#hash_calc]Collection文件不存在，将创建新文件")
                    
                    # 更新collection（合并新的哈希值）
                    collection_data["hashes"].update(zip_hashes)
                    
                    # 在写入之前验证数据结构
                    if not isinstance(collection_data, dict) or "hashes" not in collection_data:
                        raise ValueError("Collection数据结构无效")
                    
                    # 保存更新后的collection
                    temp_file = f"{Settings.HASH_COLLECTION_FILE}.temp"
                    try:
                        with open(temp_file, 'w', encoding='utf-8') as f:
                            json.dump(collection_data, f, ensure_ascii=False, indent=2)
                        # 如果写入成功，替换原文件
                        os.replace(temp_file, Settings.HASH_COLLECTION_FILE)
                        logging.info(f"[#hash_calc]已更新 {len(zip_hashes)} 个哈希到collection文件")
                    except Exception as e:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                        raise
                except Exception as e:
                    logging.error(f"[#file_ops]保存collection文件失败: {str(e)}")
                    # 尝试备份损坏的文件
                    if os.path.exists(Settings.HASH_COLLECTION_FILE):
                        backup_path = Settings.HASH_COLLECTION_FILE + '.bak'
                        try:
                            shutil.copy2(Settings.HASH_COLLECTION_FILE, backup_path)
                            logging.info(f"[#hash_calc]已备份可能损坏的collection文件到: {backup_path}")
                        except Exception as backup_error:
                            logging.error(f"[#hash_calc]备份collection文件失败: {str(backup_error)}")
            
            if not ArchiveProcessor.cleanup_and_compress(temp_dir, removed_files, duplicate_files, new_zip_path, params, removal_reasons):
                logging.info( f"❌ 清理和压缩失败: {file_path}")
                if os.path.exists(backup_file_path):
                    os.replace(backup_file_path, file_path)
                return []
            if not os.path.exists(new_zip_path):
                logging.info( f"❌ 新压缩包不存在: {new_zip_path}")
                if os.path.exists(backup_file_path):
                    os.replace(backup_file_path, file_path)
                return []
            original_size = os.path.getsize(file_path)
            new_size = os.path.getsize(new_zip_path)
            REDUNDANCY_SIZE = 1 * 1024 * 1024
            if new_size >= original_size + REDUNDANCY_SIZE:
                logging.info( f"⚠️ 新压缩包 ({new_size / 1024 / 1024:.2f}MB) 不小于原始文件 ({original_size / 1024 / 1024:.2f}MB)，还原备份")
                os.remove(new_zip_path)
                if os.path.exists(backup_file_path):
                    os.replace(backup_file_path, file_path)
                return []
            # 替换原始文件
            os.replace(new_zip_path, file_path)
            # 让 BackupService.handle_bak_file 来处理备份文件，不在这里直接删除
            BackupService.handle_bak_file(backup_file_path, params)
            
            result = {
                'file_path': file_path,
                'hash_duplicates_removed': len([f for f in duplicate_files if removal_reasons.get(f) == 'hash_duplicate']),
                'normal_duplicates_removed': len([f for f in duplicate_files if removal_reasons.get(f) == 'normal_duplicate']),
                'small_images_removed': len([f for f in removed_files if removal_reasons.get(f) == 'small_image']),
                'white_images_removed': len([f for f in removed_files if removal_reasons.get(f) == 'white_image']),
                'size_reduction_mb': (original_size - new_size) / (1024 * 1024)
            }
            processed_archives.append(result)
        except Exception as e:
            logging.info( f"❌ 处理压缩包时出错 {file_path}: {e}")
            if backup_file_path and os.path.exists(backup_file_path):
                os.replace(backup_file_path, file_path)
            return []
        finally:
            PathManager.cleanup_temp_files(temp_dir, new_zip_path, backup_file_path)
        return processed_archives

    @staticmethod
    def cleanup_and_compress(temp_dir, removed_files, duplicate_files, new_zip_path, params, removal_reasons):
        """清理文件并创建新压缩包"""
        try:
            if removed_files is None:
                removed_files = set()
            if duplicate_files is None:
                duplicate_files = set()
            if not isinstance(removed_files, set) or not isinstance(duplicate_files, set):
                logging.info( f"❌ 无效的参数类型: removed_files={type(removed_files)}, duplicate_files={type(duplicate_files)}")
                return False
            BackupService.backup_removed_files(new_zip_path, removed_files, duplicate_files, params, removal_reasons)
            all_files_to_remove = removed_files | duplicate_files
            removed_count = 0
            for file_path in all_files_to_remove:
                try:
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                        removed_count += 1
                        logging.info( f'已删除文件: {file_path}')
                except Exception as e:
                    logging.info( f"❌ 删除文件失败 {file_path}: {e}")
                    continue
            if removed_count > 0:
                logging.info( f'已删除 {removed_count} 个文件')
            empty_dirs_removed = DirectoryHandler.remove_empty_directories(temp_dir)
            if empty_dirs_removed > 0:
                logging.info( f'已删除 {empty_dirs_removed} 个空文件夹')
            if not os.path.exists(temp_dir) or not any(os.scandir(temp_dir)):
                logging.info( f'临时目录为空或不存在: {temp_dir}')
                temp_empty_file = os.path.join(temp_dir, '.empty')
                os.makedirs(temp_dir, exist_ok=True)
                with open(temp_empty_file, 'w') as f:
                    pass
                success, error = ArchiveUtils.run_7z_command('a', new_zip_path, '创建空压缩包', ['-tzip', temp_empty_file])
                os.remove(temp_empty_file)
                if success and os.path.exists(new_zip_path):
                    logging.info( f'成功创建空压缩包: {new_zip_path}')
                    return True
                else:
                    logging.info( f"❌ 创建空压缩包失败: {error}")
                    return False
            success, error = ArchiveUtils.run_7z_command('a', new_zip_path, '创建新压缩包', ['-tzip', os.path.join(temp_dir, '*')])
            if success:
                if not os.path.exists(new_zip_path):
                    logging.info( f"❌ 压缩包创建失败: {new_zip_path}")
                    return False
                logging.info( f'成功创建新压缩包: {new_zip_path}')
                return True
            else:
                logging.info( f"❌ 创建压缩包失败: {error}")
                return False
        except Exception as e:
            logging.info( f"❌ 清理和压缩时出错: {e}")
            return False

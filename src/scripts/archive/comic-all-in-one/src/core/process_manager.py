from src.core.archive_processor import ArchiveProcessor
from src.services.logging_service import LoggingService
from src.services.stats_service import StatsService
import logging
import os
import shutil
from src.utils.hash_utils import HashFileHandler
from src.utils.path_utils import PathManager
from src.services.backup_service import BackupHandler
import subprocess
from src.utils.content_filter import ContentFilter
from src.utils.directory_handler import DirectoryHandler
from src.services.logging_service import LoggingService

class ProcessManager:
    """
    类描述
    """
    @staticmethod
    def generate_summary_report(processed_archives):
        """生成处理摘要并显示到面板"""
        if not processed_archives:
            logging.info( '没有处理任何压缩包。')
            return
            
        # 使用StatsService中的统计数据
        summary = [
            "📊 处理完成摘要",
            f"总共处理: {len(processed_archives)} 个压缩包",
            f"删除哈希重复图片: {StatsService.hash_duplicates_count} 张",
            f"删除普通重复图片: {StatsService.normal_duplicates_count} 张",
            f"删除小图: {StatsService.small_images_count} 张",
            f"删除白图: {StatsService.white_images_count} 张",
            f"总共减少: {sum(archive['size_reduction_mb'] for archive in processed_archives):.2f} MB",
            "\n详细信息:"
        ]
        
        # 按目录组织处理结果
        common_path_prefix = os.path.commonpath([archive['file_path'] for archive in processed_archives])
        tree_structure = {}
        for archive in processed_archives:
            relative_path = os.path.relpath(archive['file_path'], common_path_prefix)
            path_parts = relative_path.split(os.sep)
            current_level = tree_structure
            for part in path_parts:
                current_level = current_level.setdefault(part, {})
            current_level['_summary'] = (
                f"哈希重复: {archive.get('hash_duplicates_removed', 0)} 张, "
                f"普通重复: {archive.get('normal_duplicates_removed', 0)} 张, "
                f"小图: {archive.get('small_images_removed', 0)} 张, "
                f"白图: {archive.get('white_images_removed', 0)} 张, "
                f"减少: {archive['size_reduction_mb']:.2f} MB"
            )
        
        # 生成树形结构的详细信息
        def build_tree_text(level, indent=''):
            tree_text = []
            for name, content in level.items():
                if name == '_summary':
                    tree_text.append(f'{indent}{content}')
                else:
                    tree_text.append(f'{indent}├─ {name}')
                    tree_text.extend(build_tree_text(content, indent + '│   '))
            return tree_text
        
        # 添加树形结构到摘要
        summary.extend(build_tree_text(tree_structure))
        
        # 更新到面板
        logging.info( '\n'.join(summary))
        logging.info( "✅ 处理完成，已生成摘要报告")


    @staticmethod
    def process_normal_archives(directories, args):
        """处理普通模式的压缩包或目录"""
        for directory in directories:
            if os.path.exists(directory):
                params = InputHandler.prepare_params(args)
                ProcessManager.process_all_archives([directory], params)
                if args.bak_mode != 'keep':
                    for root, _, files in os.walk(directory):
                        for file in files:
                            if file.endswith('.bak'):
                                bak_path = os.path.join(root, file)
                                BackupHandler.handle_bak_file(bak_path, args)
                DirectoryHandler.remove_empty_directories(directory)
            else:
                logging.info( f"输入的路径不存在: {directory}")

    @staticmethod
    def process_merged_archives(directories, args):
        """处理合并模式的压缩包"""
        temp_dir, merged_zip, archive_paths = ArchiveProcessor.merge_archives(directories, args)
        if temp_dir and merged_zip:
            try:
                params = InputHandler.prepare_params(args)
                ProcessManager.process_all_archives([merged_zip], params)
                if ArchiveProcessor.split_merged_archive(merged_zip, archive_paths, temp_dir, params):
                    logging.info( '成功完成压缩包的合并处理和拆分')
                else:
                    logging.info( '拆分压缩包失败')
            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                if os.path.exists(merged_zip):
                    os.remove(merged_zip)

    @staticmethod
    def print_config(args, max_workers):
        """打印当前配置信息"""
        # 清屏
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # 使用log_panel输出配置信息
        config_info = [
            '\n=== 当前配置信息 ===',
            '启用的功能:',
            f"  - 小图过滤: {('是' if args.remove_small else '否')}"
        ]
        
        if args.remove_small:
            config_info.append(f'    最小尺寸: {args.min_size}x{args.min_size} 像素')
            
        config_info.extend([
            f"  - 黑白图过滤: {('是' if args.remove_grayscale else '否')}"
        ])
        

            
        config_info.extend([
            f"  - 重复图片过滤: {('是' if args.remove_duplicates else '否')}"
        ])
        
        if args.remove_duplicates:
            config_info.extend([
                f'    内部去重汉明距离阈值: {args.hamming_distance}',
                f'    外部参考汉明距离阈值: {args.ref_hamming_distance}'
            ])
            
        config_info.extend([
            f"  - 合并压缩包处理: {('是' if args.merge_archives else '否')}",
            f"从剪贴板读取: {('是' if args.clipboard else '否')}",
            f'备份文件处理模式: {args.bak_mode}',
            f'线程数: {max_workers}',
            '==================\n'
        ])
        
        initialize_logger()
        logging.info( '\n'.join(config_info))

    @staticmethod
    def process_all_archives(directories, params):
        """
        主处理函数
        
        Args:
            directories: 要处理的目录列表
            params: 参数字典，包含所有必要的处理参数
        """

            
        processed_archives = []
        logging.info( "开始处理拖入的目录或文件")
        
        # 计算总文件数
        total_zip_files = sum((1 for directory in directories 
                             for root, _, files in os.walk(directory) 
                             for file in files if file.lower().endswith('zip')))
        
        # 更新总体进度面板
        logging.info( 
            f"总文件数: {total_zip_files}\n"
            f"已处理: 0\n"
            f"成功: 0\n"
            f"警告: 0\n"
            f"错误: 0"
        )

        # 设置总数
        StatsService.set_total(total_zip_files)
            
        for directory in directories:
            archives = ProcessManager.process_directory(directory, params)
            processed_archives.extend(archives)
                
            # 更新总体进度
            success_count = sum(1 for a in archives if (a.get('duplicates_removed', 0) > 0 or 
                                                      a.get('small_images_removed', 0) > 0 or 
                                                      a.get('white_images_removed', 0) > 0))
            warning_count = sum(1 for a in archives if (a.get('duplicates_removed', 0) == 0 and 
                                                      a.get('small_images_removed', 0) == 0 and 
                                                      a.get('white_images_removed', 0) == 0))
            error_count = StatsService.processed_count - len(archives)
                
            logging.info( 
                f"总文件数: {total_zip_files}\n"
                f"已处理: {StatsService.processed_count}\n"
                f"成功: {success_count}\n"
                f"警告: {warning_count}\n"
                f"错误: {error_count}"
            )
        
        ProcessManager.generate_summary_report(processed_archives)
        logging.info( "所有目录处理完成")
        return processed_archives

    @staticmethod
    def process_directory(directory, params):
        """处理单个目录"""
        try:
            logging.info( f"\n开始处理目录: {directory}")
            processed_archives = []
            if os.path.isfile(directory):
                logging.info( f"处理单个文件: {directory}")
                if directory.lower().endswith('zip'):
                    if ContentFilter.should_process_file(directory, params):
                        logging.info( f"开始处理压缩包: {directory}")
                        archives = ProcessManager.process_single_archive(directory, params)
                        processed_archives.extend(archives)
                    else:
                        logging.info( f"跳过文件（根据过滤规则）: {directory}")
                    StatsService.increment()
                else:
                    logging.info( f"跳过非zip文件: {directory}")
            elif os.path.isdir(directory):
                logging.info( f"扫描目录中的文件: {directory}")
                files_to_process = []
                for root, _, files in os.walk(directory):
                    logging.debug( f"扫描子目录: {root}")
                    for file in files:
                        if file.lower().endswith('zip'):
                            file_path = os.path.join(root, file)
                            logging.info( f"发现zip文件: {file_path}")
                            if ContentFilter.should_process_file(file_path, params):
                                logging.info( f"添加到处理列表: {file_path}")
                                files_to_process.append(file_path)
                            else:
                                logging.info( f"跳过文件（根据过滤规则）: {file_path}")
                                StatsService.increment()
                logging.info( f"扫描完成: 找到 {len(files_to_process)} 个要处理的文件")
                for file_path in files_to_process:
                    try:
                        logging.info( f"\n正在处理压缩包: {file_path}")
                        archives = ProcessManager.process_single_archive(file_path, params)
                        if archives:
                            logging.info( f"成功处理压缩包: {file_path}")
                        else:
                            logging.info( f"压缩包处理完成，但没有变化: {file_path}")
                        processed_archives.extend(archives)
                    except Exception as e:
                        logging.info( f"处理压缩包出错: {file_path}\n错误: {e}")
                    finally:
                        StatsService.increment()
            if os.path.isdir(directory):
                exclude_keywords = params.get('exclude_paths', [])
            return processed_archives
        except Exception as e:
            logging.info( f"处理目录时发生异常: {directory}\n{str(e)}")
            return []

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
                BackupHandler.handle_bak_file(backup_file_path, params)
                logging.info( "已处理备份文件")
                
            return processed_archives
            
        except UnicodeDecodeError as e:
            logging.info( f"❌ 处理压缩包时出现编码错误 {file_path}: {e}")
            return []
        except Exception as e:
            logging.info( f"❌ 处理文件时发生异常: {file_path}\n{str(e)}")
            return []

    @staticmethod
    def get_max_workers():
        """获取最大工作线程数"""
        return max_workers  # 返回全局配置的max_workers值

    """处理管理类"""
    @staticmethod
    def process_normal_archives(directories, args):
        """处理普通模式的压缩包或目录"""
        pass

    @staticmethod
    def process_merged_archives(directories, args):
        """处理合并模式的压缩包"""
        pass

    @staticmethod
    def process_all_archives(directories, params):
        """主处理函数"""
        pass

    @staticmethod
    def process_directory(directory, params):
        """处理单个目录"""
        pass

    @staticmethod
    def process_single_archive(file_path, params):
        """处理单个压缩包文件"""
        pass 
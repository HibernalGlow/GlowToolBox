import os
import shutil
from send2trash import send2trash
from src.services.logging_service import LoggingService
import logging


class BackupService:
    """
    类描述
    """
    @staticmethod
    def handle_bak_file(bak_path, params=None):
        """
        根据指定模式处理bak文件
        
        Args:
            bak_path: 备份文件路径
            params: 参数字典或Namespace对象，包含:
                - bak_mode: 备份文件处理模式 ('keep', 'recycle', 'delete')
                - backup_removed_files_enabled: 是否使用回收站
        """
        try:
            # 如果没有传入参数，使用默认值
            if params is None:
                params = {}
            
            # 获取模式，支持字典和Namespace对象，默认为keep
            mode = params.bak_mode if hasattr(params, 'bak_mode') else params.get('bak_mode', 'keep')
            
            if mode == 'keep':
                logging.info( f'保留备份文件: {bak_path}')
                return
                
            if not os.path.exists(bak_path):
                logging.info( f'备份文件不存在: {bak_path}')
                return
                
            # 获取是否使用回收站，支持字典和Namespace对象

            # 如果是回收站模式，或者启用了备份文件
            if mode == 'recycle':
                try:
                    send2trash(bak_path)
                    logging.info( f'已将备份文件移至回收站: {bak_path}')
                except Exception as e:
                    logging.info( f"❌ 移动备份文件到回收站失败 {bak_path}: {e}")
            # 只有在明确指定删除模式时才直接删除
            elif mode == 'delete':
                try:
                    os.remove(bak_path)
                    logging.info( f'已删除备份文件: {bak_path}')
                except Exception as e:
                    logging.info( f"❌ 删除备份文件失败 {bak_path}: {e}")
        except Exception as e:
            logging.info( f"❌ 处理备份文件时出错 {bak_path}: {e}")



    @staticmethod
    def backup_removed_files(zip_path, removed_files, duplicate_files, params, removal_reasons):
        """
        将删除的文件备份到trash文件夹中，保持原始目录结构
        
        Args:
            zip_path: 原始压缩包路径
            removed_files: 被删除的小图/白图文件集合
            duplicate_files: 被删除的重复图片文件集合
            params: 参数字典
            removal_reasons: 文件删除原因的字典，键为文件路径，值为删除原因
        """
        try:
            if not params.get('backup_removed_files_enabled', True):
                logging.info( '跳过备份删除的文件')
                return
            if not removed_files and (not duplicate_files):
                return
                
            zip_name = os.path.splitext(os.path.basename(zip_path))[0]
            trash_dir = os.path.join(os.path.dirname(zip_path), f'{zip_name}.trash')
            os.makedirs(trash_dir, exist_ok=True)
            
            # 分类备份不同类型的文件
            for file_path in removed_files | duplicate_files:
                try:
                    # 根据记录的删除原因确定子目录
                    reason = removal_reasons.get(file_path)
                    if reason == 'hash_duplicate':
                        subdir = 'hash_duplicates'
                    elif reason == 'normal_duplicate':
                        subdir = 'normal_duplicates'
                    elif reason == 'small_image':
                        subdir = 'small_images'
                    elif reason == 'white_image':
                        subdir = 'white_images'
                    else:
                        subdir = 'other'
                    
                    # 创建目标路径并复制文件
                    rel_path = os.path.relpath(file_path, os.path.dirname(zip_path))
                    dest_path = os.path.join(trash_dir, subdir, rel_path)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy2(file_path, dest_path)
                    logging.info( f"已备份到 {subdir}: {rel_path}")
                    
                except Exception as e:
                    logging.info( f"❌ 备份文件失败 {file_path}: {e}")
                    continue
                
            logging.info( f'已备份删除的文件到: {trash_dir}')
            
        except Exception as e:
            logging.info( f"❌ 备份删除文件时出错: {e}")

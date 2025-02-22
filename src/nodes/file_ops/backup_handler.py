import os
import shutil
import logging
from typing import Set, Dict

logger = logging.getLogger(__name__)

class BackupHandler:
    """处理文件备份和删除的类"""
    
    @staticmethod
    def backup_removed_files(
        zip_path: str, 
        removed_files: Set[str], 
        removal_reasons: Dict[str, Dict],
        trash_folder_name: str = "trash"
    ) -> Dict[str, bool]:
        """
        将删除的文件备份到trash文件夹中，按删除原因分类
        
        Args:
            zip_path: 原始压缩包路径
            removed_files: 被删除的文件集合
            removal_reasons: 文件删除原因的字典
            trash_folder_name: 垃圾箱文件夹名称
            
        Returns:
            Dict[str, bool]: 文件路径到备份是否成功的映射
        """
        backup_results = {}
        
        try:
            if not removed_files:
                return backup_results
                
            zip_name = os.path.splitext(os.path.basename(zip_path))[0]
            trash_dir = os.path.join(os.path.dirname(zip_path), f'{zip_name}.{trash_folder_name}')
            
            # 按删除原因分类
            for file_path in removed_files:
                try:
                    reason = removal_reasons.get(file_path, {}).get('reason', 'unknown')
                    subdir = os.path.join(trash_dir, reason)
                    os.makedirs(subdir, exist_ok=True)
                    
                    # 复制文件到对应子目录
                    dest_path = os.path.join(subdir, os.path.basename(file_path))
                    shutil.copy2(file_path, dest_path)
                    backup_results[file_path] = True
                    
                except Exception as e:
                    logger.error(f"备份文件失败 {file_path}: {e}")
                    backup_results[file_path] = False
                    continue
                    
            return backup_results
            
        except Exception as e:
            logger.error(f"备份删除文件时出错: {e}")
            return {file: False for file in removed_files}
    
    @staticmethod
    def remove_files(files_to_remove: Set[str]) -> Dict[str, bool]:
        """
        删除指定的文件
        
        Args:
            files_to_remove: 要删除的文件集合
            
        Returns:
            Dict[str, bool]: 文件路径到删除是否成功的映射
        """
        results = {}
        for file_path in files_to_remove:
            try:
                os.remove(file_path)
                results[file_path] = True
            except Exception as e:
                logger.error(f"删除文件失败 {file_path}: {e}")
                results[file_path] = False
        return results 
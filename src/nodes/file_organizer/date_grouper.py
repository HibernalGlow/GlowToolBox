import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging
from dataclasses import dataclass

@dataclass
class FileInfo:
    path: Path
    timestamp: datetime
    
class DateGrouper:
    """文件日期分组器"""
    
    def __init__(self, source_dir: str, target_dir: Optional[str] = None):
        """
        初始化日期分组器
        
        Args:
            source_dir: 源文件目录
            target_dir: 目标目录（可选，如果不指定则在源目录下创建分组）
        """
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir) if target_dir else self.source_dir
        self.logger = logging.getLogger(__name__)
        
    def _get_file_timestamp(self, file_path: Path) -> datetime:
        """获取文件的时间戳"""
        timestamp = file_path.stat().st_mtime
        return datetime.fromtimestamp(timestamp)
    
    def _collect_files(self) -> List[FileInfo]:
        """收集所有文件信息"""
        files = []
        for file_path in self.source_dir.rglob('*'):
            if file_path.is_file():
                timestamp = self._get_file_timestamp(file_path)
                files.append(FileInfo(file_path, timestamp))
        return files
    
    def _group_by_date(self, files: List[FileInfo]) -> Dict[str, List[FileInfo]]:
        """按日期对文件进行分组"""
        groups = {}
        for file in files:
            date_str = file.timestamp.strftime('%Y-%m-%d')
            if date_str not in groups:
                groups[date_str] = []
            groups[date_str].append(file)
        return groups
    
    def _create_date_folders(self, groups: Dict[str, List[FileInfo]]) -> None:
        """创建日期文件夹"""
        for date_str in groups.keys():
            folder_path = self.target_dir / date_str
            folder_path.mkdir(parents=True, exist_ok=True)
    
    def _move_files(self, groups: Dict[str, List[FileInfo]]) -> None:
        """移动文件到对应的日期文件夹"""
        for date_str, files in groups.items():
            target_folder = self.target_dir / date_str
            for file_info in files:
                target_path = target_folder / file_info.path.name
                if not target_path.exists():
                    shutil.move(str(file_info.path), str(target_path))
                    self.logger.info(f"Moved {file_info.path.name} to {date_str}/")
                else:
                    self.logger.warning(f"File {file_info.path.name} already exists in {date_str}/")
    
    def organize(self) -> None:
        """执行文件组织"""
        try:
            self.logger.info(f"Starting to organize files in {self.source_dir}")
            
            # 收集文件
            files = self._collect_files()
            if not files:
                self.logger.warning("No files found to organize")
                return
                
            # 按日期分组
            groups = self._group_by_date(files)
            
            # 创建日期文件夹
            self._create_date_folders(groups)
            
            # 移动文件
            self._move_files(groups)
            
            self.logger.info("File organization completed successfully")
            
        except Exception as e:
            self.logger.error(f"Error organizing files: {str(e)}")
            raise

def setup_logging():
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def main():
    """主函数，用于直接运行模块"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        source_dir = input("请输入要整理的源文件夹路径: ").strip()
        target_dir = input("请输入目标文件夹路径（可选，直接回车则在源文件夹内分组）: ").strip()
        
        if not source_dir:
            logger.error("源文件夹路径不能为空")
            return
            
        target_dir = target_dir if target_dir else None
        grouper = DateGrouper(source_dir, target_dir)
        grouper.organize()
        
    except KeyboardInterrupt:
        logger.info("操作已取消")
    except Exception as e:
        logger.error(f"发生错误: {str(e)}")

if __name__ == "__main__":
    main() 
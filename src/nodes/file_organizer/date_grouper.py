import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple
import logging
from dataclasses import dataclass
from dateutil.parser import parse as date_parse

@dataclass
class FileInfo:
    path: Path
    timestamp: datetime

class DateFormat:
    """日期格式预设"""
    YEAR_MONTH_DAY = "%y/%m/%d"  # 24/02/28 -> 24/02/28/
    YEAR_MONTH = "%y/%m"         # 24/02    -> 24/02/
    YEAR = "%y"                  # 24       -> 24/
    
    @staticmethod
    def get_format_help():
        return """支持的日期格式：
        - %y/%m/%d : 年/月/日 (例如: 24/02/28)
        - %y/%m    : 年/月   (例如: 24/02)
        - %y       : 年      (例如: 24)
        也可以自定义格式，例如：
        - %Y/%m/%d : 完整年份 (例如: 2024/02/28)
        - %y_%m_%d : 使用下划线分隔
        注意：使用斜杠(/)会自动创建多级目录
        """

class DateGrouper:
    """文件日期分组器"""
    
    def __init__(self, 
                 source_dir: str, 
                 target_dir: Optional[str] = None,
                 date_format: str = DateFormat.YEAR_MONTH_DAY,
                 recursive: bool = True,
                 merge_levels: Optional[List[int]] = None):
        """
        初始化日期分组器
        
        Args:
            source_dir: 源文件目录
            target_dir: 目标目录（可选，如果不指定则在源目录下创建分组）
            date_format: 日期格式（默认：年/月/日）
            recursive: 是否递归处理子目录
            merge_levels: 需要合并的层级列表（从0开始，例如[1]表示合并月份层级）
        """
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir) if target_dir else self.source_dir
        self.date_format = date_format
        self.recursive = recursive
        self.merge_levels = merge_levels or []
        self.logger = logging.getLogger(__name__)
        
    def _get_file_timestamp(self, file_path: Path) -> datetime:
        """获取文件的时间戳"""
        timestamp = file_path.stat().st_mtime
        return datetime.fromtimestamp(timestamp)
    
    def _collect_files(self) -> List[FileInfo]:
        """收集所有文件信息"""
        files = []
        glob_pattern = '**/*' if self.recursive else '*'
        for file_path in self.source_dir.glob(glob_pattern):
            if file_path.is_file():
                timestamp = self._get_file_timestamp(file_path)
                files.append(FileInfo(file_path, timestamp))
        return files
    
    def _format_date(self, timestamp: datetime) -> Tuple[str, List[str]]:
        """格式化日期，返回完整路径和层级列表"""
        try:
            date_str = timestamp.strftime(self.date_format)
            # 移除开头和结尾的斜杠，然后分割
            levels = [x for x in date_str.strip('/').split('/') if x]
            # 处理层级合并
            if self.merge_levels:
                for level in sorted(self.merge_levels, reverse=True):
                    if level < len(levels):
                        levels[level] = '*'
            return '/'.join(levels), levels
        except ValueError as e:
            self.logger.error(f"日期格式错误: {str(e)}")
            return timestamp.strftime(DateFormat.YEAR_MONTH_DAY), []
    
    def _group_by_date(self, files: List[FileInfo]) -> Dict[str, List[FileInfo]]:
        """按日期对文件进行分组"""
        groups = {}
        for file in files:
            date_str, _ = self._format_date(file.timestamp)
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
        total_files = sum(len(files) for files in groups.values())
        moved_files = 0
        
        for date_str, files in groups.items():
            target_folder = self.target_dir / date_str
            for file_info in files:
                target_path = target_folder / file_info.path.name
                if not target_path.exists():
                    shutil.move(str(file_info.path), str(target_path))
                    moved_files += 1
                    self.logger.info(f"已移动 [{moved_files}/{total_files}] {file_info.path.name} -> {date_str}/")
                else:
                    self.logger.warning(f"文件已存在: {date_str}/{file_info.path.name}")
    
    def organize(self) -> None:
        """执行文件组织"""
        try:
            self.logger.info(f"开始整理文件夹: {self.source_dir}")
            self.logger.info(f"使用日期格式: {self.date_format}")
            if self.merge_levels:
                self.logger.info(f"合并层级: {self.merge_levels}")
            
            # 收集文件
            files = self._collect_files()
            if not files:
                self.logger.warning("没有找到需要整理的文件")
                return
                
            self.logger.info(f"找到 {len(files)} 个文件")
            
            # 按日期分组
            groups = self._group_by_date(files)
            
            # 创建日期文件夹
            self._create_date_folders(groups)
            
            # 移动文件
            self._move_files(groups)
            
            self.logger.info("文件整理完成")
            
        except Exception as e:
            self.logger.error(f"整理过程出错: {str(e)}")
            raise

def setup_logging():
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def print_date_format_help():
    """打印日期格式帮助信息"""
    print("\n" + DateFormat.get_format_help())

def main():
    """主函数，用于直接运行模块"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        print("\n=== 文件日期分组工具 ===")
        print_date_format_help()
        
        source_dir = input("\n请输入要整理的源文件夹路径: ").strip()
        if not source_dir:
            logger.error("源文件夹路径不能为空")
            return
            
        target_dir = input("请输入目标文件夹路径（可选，直接回车则在源目录下分组）: ").strip()
        target_dir = target_dir if target_dir else None
        
        date_format = input("请输入日期格式（直接回车使用默认格式 YY/MM/DD）: ").strip()
        date_format = date_format if date_format else DateFormat.YEAR_MONTH_DAY
        
        merge_input = input("请输入要合并的层级（用逗号分隔，从0开始，例如1表示合并月份层级）: ").strip()
        merge_levels = [int(x.strip()) for x in merge_input.split(',')] if merge_input else None
        
        recursive = input("是否处理子目录？(y/N): ").strip().lower() == 'y'
        
        grouper = DateGrouper(
            source_dir=source_dir,
            target_dir=target_dir,
            date_format=date_format,
            recursive=recursive,
            merge_levels=merge_levels
        )
        grouper.organize()
        
    except KeyboardInterrupt:
        logger.info("\n操作已取消")
    except Exception as e:
        logger.error(f"发生错误: {str(e)}")

if __name__ == "__main__":
    main() 
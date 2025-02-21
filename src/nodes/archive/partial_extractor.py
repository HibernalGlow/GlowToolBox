import os
import subprocess
from typing import List, Set, Dict, Any
import shutil
from ..pics.range_control import RangeControl

class PartialExtractor:
    """处理压缩包部分解压的类"""
    
    @staticmethod
    def list_archive_contents(archive_path: str) -> List[str]:
        """
        列出压缩包中的所有文件
        
        Args:
            archive_path: 压缩包路径
            
        Returns:
            List[str]: 压缩包中的文件列表
        """
        try:
            cmd = ['7z', 'l', archive_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"列出压缩包内容失败: {result.stderr}")
                
            # 解析7z输出
            files = []
            for line in result.stdout.splitlines():
                if line.strip() and any(line.lower().endswith(ext) for ext in 
                    ('.jpg', '.jpeg', '.png', '.webp', '.jxl', '.avif')):
                    # 提取文件名
                    parts = line.split()
                    if len(parts) >= 6:  # 7z输出格式：日期 时间 属性 大小 压缩后大小 文件名
                        files.append(parts[-1])
            
            return sorted(files)  # 返回排序后的文件列表
            
        except Exception as e:
            raise Exception(f"获取压缩包内容失败: {str(e)}")
    
    @staticmethod
    def extract_selected_files(archive_path: str, target_dir: str, 
                             selected_indices: Set[int], file_list: List[str]) -> bool:
        """
        解压选定的文件
        
        Args:
            archive_path: 压缩包路径
            target_dir: 目标目录
            selected_indices: 选中的文件索引集合
            file_list: 完整的文件列表
            
        Returns:
            bool: 是否成功解压
        """
        try:
            # 创建临时列表文件
            list_file = os.path.join(target_dir, '@files.txt')
            selected_files = [file_list[i] for i in selected_indices]
            
            with open(list_file, 'w', encoding='utf-8') as f:
                for file in selected_files:
                    f.write(file + '\n')
            
            # 使用列表文件解压
            cmd = ['7z', 'x', archive_path, f'-o{target_dir}', f'@{list_file}', '-y']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # 清理列表文件
            os.remove(list_file)
            
            if result.returncode != 0:
                raise Exception(f"解压失败: {result.stderr}")
                
            return True
            
        except Exception as e:
            if os.path.exists(list_file):
                os.remove(list_file)
            raise Exception(f"部分解压失败: {str(e)}")
    
    @staticmethod
    def partial_extract(archive_path: str, target_dir: str, range_control: Dict[str, Any]) -> bool:
        """
        根据范围控制配置部分解压压缩包
        
        Args:
            archive_path: 压缩包路径
            target_dir: 目标目录
            range_control: 范围控制配置
            
        Returns:
            bool: 是否成功解压
        """
        try:
            # 获取压缩包内容
            file_list = PartialExtractor.list_archive_contents(archive_path)
            if not file_list:
                return False
                
            # 处理范围控制
            selected_indices = RangeControl.process_range_control(range_control, len(file_list))
            
            # 解压选定文件
            return PartialExtractor.extract_selected_files(
                archive_path, target_dir, selected_indices, file_list
            )
            
        except Exception as e:
            raise Exception(f"部分解压失败: {str(e)}") 
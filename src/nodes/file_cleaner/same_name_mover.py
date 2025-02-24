import os
import re
import logging
import shutil
from pathlib import Path
from typing import List, Tuple, Dict
from colorama import init, Fore, Style

# 初始化colorama
init()

class SameNameMover:
    """处理重名文件移动的类"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志格式"""
        formatter = logging.Formatter('%(message)s')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def _group_similar_files(self, files: List[str]) -> Dict[str, List[str]]:
        """
        将文件按基础名称分组,只处理_数字的情况
        返回: {基础名称: [相关文件列表]}
        """
        groups = {}
        for filename in files:
            # 移除文件扩展名
            name_without_ext = os.path.splitext(filename)[0]
            
            # 只移除_数字并清理空格
            base = re.sub(r'_\d+', '', name_without_ext)
            base = re.sub(r'\s+', ' ', base).strip()
            
            if base not in groups:
                groups[base] = []
            groups[base].append(filename)
            
            # 调试输出
            if len(groups[base]) > 1:
                self.logger.info(f"{Fore.YELLOW}找到相似文件组: {base}{Style.RESET_ALL}")
                for f in groups[base]:
                    self.logger.info(f"  - {f}")
                
        return groups
    
    def _find_duplicate_files(self, directory: str) -> List[Tuple[str, List[str]]]:
        """
        查找目录中的重名文件（只处理当前目录）
        返回: [(原始文件名, [重复文件列表])]
        """
        duplicates = []
        
        try:
            # 只获取当前目录的文件列表
            files = [f for f in os.listdir(directory) if f.lower().endswith('.zip')]
            if not files:
                return []
                
            # 按基础名称分组
            groups = {}
            for filename in files:
                # 检查是否包含_数字
                if '_' in filename:
                    # 获取_数字之前的部分作为基础名称
                    base = filename[:filename.rindex('_')]
                    if base not in groups:
                        groups[base] = []
                    groups[base].append(filename)
                    
                    # 调试输出
                    if len(groups[base]) == 1:
                        self.logger.info(f"{Fore.YELLOW}找到可能的重复文件组: {base}{Style.RESET_ALL}")
                        self.logger.info(f"  - {filename}")
            
            # 处理每个分组
            for base_name, group_files in groups.items():
                # 检查原始文件是否存在
                original = base_name + '.zip'
                if original in files:
                    duplicates.append((
                        os.path.join(directory, original),
                        [os.path.join(directory, f) for f in group_files]
                    ))
                    self.logger.info(f"  原始文件: {original}")
                    for dup in group_files:
                        self.logger.info(f"  重复文件: {dup}")
            
            return duplicates
            
        except Exception as e:
            self.logger.error(f"{Fore.RED}扫描目录时出错: {str(e)}{Style.RESET_ALL}")
            return []
    
    def move_duplicates(self, source_dir: str, target_dir: str, dry_run: bool = True) -> None:
        """
        移动重复文件到目标目录，保持原始目录结构
        :param source_dir: 源目录
        :param target_dir: 目标目录
        :param dry_run: 如果为True，只显示要移动的文件而不实际移动
        """
        duplicates = self._find_duplicate_files(source_dir)
        
        if not duplicates:
            self.logger.info(f"{Fore.GREEN}✨ 没有找到需要移动的重复文件{Style.RESET_ALL}")
            return
        
        total_duplicates = sum(len(dups) for _, dups in duplicates)
        
        self.logger.info(f"\n{Fore.CYAN}找到 {total_duplicates} 个重复文件:{Style.RESET_ALL}")
        
        for original, duplicate_list in duplicates:
            self.logger.info(f"\n{Fore.WHITE}原始文件: {os.path.relpath(original, source_dir)}{Style.RESET_ALL}")
            for duplicate in duplicate_list:
                # 计算相对路径
                rel_path = os.path.relpath(duplicate, source_dir)
                # 构建目标路径
                target_path = os.path.join(target_dir, rel_path)
                # 确保目标目录存在
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                
                if dry_run:
                    self.logger.info(f"{Fore.YELLOW}将移动: {rel_path}{Style.RESET_ALL}")
                else:
                    try:
                        shutil.move(duplicate, target_path)
                        self.logger.info(f"{Fore.GREEN}已移动: {rel_path}{Style.RESET_ALL}")
                    except Exception as e:
                        self.logger.error(f"{Fore.RED}移动失败 {rel_path}: {str(e)}{Style.RESET_ALL}")
        
        mode_str = "预览" if dry_run else "移动"
        self.logger.info(f"\n{Fore.GREEN}✅ {mode_str}完成{Style.RESET_ALL}")

def move_same_name_files(source_dir: str, target_dir: str = "E:\\2EHV\\same_name", dry_run: bool = False) -> None:
    """
    移动重名文件的便捷函数
    :param source_dir: 源目录路径
    :param target_dir: 目标目录路径，默认为 E:\\2EHV\\same_name
    :param dry_run: 是否为预览模式
    """
    try:
        mover = SameNameMover()
        mover.move_duplicates(source_dir, target_dir, dry_run)
    except Exception as e:
        print(f"{Fore.RED}发生错误: {str(e)}{Style.RESET_ALL}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='移动重名压缩文件到指定目录')
    parser.add_argument('source_dir', nargs='?', default='.', 
                      help='要处理的源目录路径（默认为当前目录）')
    parser.add_argument('--target', default='E:\\2EHV\\same_name',
                      help='目标目录路径（默认为 E:\\2EHV\\same_name）')
    parser.add_argument('--move', action='store_true',
                      help='实际移动文件（默认只预览）')
    
    args = parser.parse_args()
    
    try:
        source_dir = os.path.abspath(args.source_dir)
        if not os.path.exists(source_dir):
            print(f"{Fore.RED}错误: 源目录不存在: {source_dir}{Style.RESET_ALL}")
            return
        
        # 确保目标目录存在
        os.makedirs(args.target, exist_ok=True)
        
        mover = SameNameMover()
        mover.move_duplicates(source_dir, args.target, dry_run=not args.move)
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}操作已取消{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}发生错误: {str(e)}{Style.RESET_ALL}")

if __name__ == '__main__':
    main() 
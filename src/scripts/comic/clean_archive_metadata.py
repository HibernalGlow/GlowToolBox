import os
import sys
import logging
import zipfile
import subprocess
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import pyperclip
from typing import List, Tuple
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt
from rich.console import Console
from rich.logging import RichHandler

# 配置rich控制台
console = Console()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
logger = logging.getLogger(__name__)

class ArchiveCleaner:
    """压缩包清理类"""
    
    @staticmethod
    def list_archive_contents(archive_path: str) -> List[str]:
        """列出压缩包中的文件"""
        try:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                return zf.namelist()
        except Exception:
            try:
                result = subprocess.run(
                    ['7z', 'l', archive_path],
                    capture_output=True,
                    text=True,
                    encoding='gbk',
                    errors='ignore',
                    check=True
                )
                if result.returncode == 0:
                    files = []
                    for line in result.stdout.splitlines():
                        if line.strip() and not line.startswith('---'):
                            parts = line.split()
                            if len(parts) >= 5:
                                files.append(parts[-1])
                    return files
            except subprocess.CalledProcessError:
                pass
        return []

    @staticmethod
    def analyze_archive(archive_path: str) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        """分析压缩包中的YAML和JSON文件
        
        Returns:
            Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]: (yaml_files, json_files)
            每个文件以元组形式返回：(完整文件名, 不含扩展名的文件名)
        """
        files = ArchiveCleaner.list_archive_contents(archive_path)
        yaml_files = [(f, os.path.splitext(f)[0]) for f in files if f.endswith('.yaml')]
        json_files = [(f, os.path.splitext(f)[0]) for f in files if f.endswith('.json') and not f.endswith('meta.json')]
        return yaml_files, json_files

    @staticmethod
    def delete_files_from_archive(archive_path: str, files_to_delete: List[str]) -> bool:
        """从压缩包中删除指定文件"""
        if not files_to_delete:
            return True

        try:
            # 尝试使用zipfile
            try:
                with zipfile.ZipFile(archive_path, 'a') as zf:
                    for file in files_to_delete:
                        try:
                            zf.remove(file)
                            logger.info(f"[删除] {os.path.basename(archive_path)} -> {file}")
                        except KeyError:
                            pass
                return True
            except Exception:
                # 如果zipfile失败，使用7z
                for file in files_to_delete:
                    try:
                        subprocess.run(
                            ['7z', 'd', archive_path, file],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=True
                        )
                        logger.info(f"[删除] {os.path.basename(archive_path)} -> {file}")
                    except subprocess.CalledProcessError:
                        logger.error(f"删除文件失败: {file}")
                        return False
                return True
        except Exception as e:
            logger.error(f"处理压缩包失败 {archive_path}: {e}")
            return False

    @staticmethod
    def process_archive(archive_path: str) -> None:
        """处理单个压缩包"""
        try:
            yaml_files, json_files = ArchiveCleaner.analyze_archive(archive_path)
            
            # 创建文件名到文件的映射
            yaml_map = {name: full_path for full_path, name in yaml_files}
            json_map = {name: full_path for full_path, name in json_files}
            
            files_to_delete = []
            
            # 处理同名文件
            for name in set(yaml_map.keys()) & set(json_map.keys()):
                # 如果存在同名文件，删除YAML文件
                files_to_delete.append(yaml_map[name])
                logger.info(f"[分析] {os.path.basename(archive_path)} - 发现同名文件，保留JSON: {json_map[name]}")
            
            # 处理剩余文件
            remaining_yaml = [f for f, n in yaml_files if n not in json_map]
            remaining_json = [f for f, n in json_files if n not in yaml_map]
            
            # 如果剩余文件总数小于等于1，跳过
            if len(remaining_yaml) + len(remaining_json) <= 1:
                return
            
            # 如果还有YAML文件，删除所有剩余JSON文件
            if remaining_yaml:
                files_to_delete.extend(remaining_json)
                # 如果有多个YAML，只保留第一个
                if len(remaining_yaml) > 1:
                    files_to_delete.extend(remaining_yaml[1:])
                logger.info(f"[分析] {os.path.basename(archive_path)} - 保留YAML: {remaining_yaml[0]}")
            
            # 如果只有多个JSON文件，保留第一个
            elif len(remaining_json) > 1:
                files_to_delete.extend(remaining_json[1:])
                logger.info(f"[分析] {os.path.basename(archive_path)} - 保留JSON: {remaining_json[0]}")
            
            # 执行删除
            if files_to_delete:
                if ArchiveCleaner.delete_files_from_archive(archive_path, files_to_delete):
                    logger.info(f"[完成] {os.path.basename(archive_path)}")
                else:
                    logger.error(f"[失败] {os.path.basename(archive_path)}")
            
        except Exception as e:
            logger.error(f"处理失败 {archive_path}: {e}")

def process_directory(target_directory: str, max_workers: int = 4) -> None:
    """处理目录中的所有压缩包"""
    # 收集所有压缩包
    console.print("[bold blue]正在扫描压缩包...[/]")
    archive_files = []
    for root, _, files in os.walk(target_directory):
        for file in files:
            if file.endswith(('.zip', '.rar', '.7z')):
                archive_files.append(os.path.join(root, file))
    
    total_files = len(archive_files)
    console.print(f"[bold green]找到 {total_files} 个压缩包[/]")
    
    if total_files == 0:
        console.print("[bold red]没有找到需要处理的压缩包[/]")
        return
    
    # 使用rich进度条
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        # 创建总进度任务
        overall_task = progress.add_task(
            "[cyan]总进度", 
            total=total_files,
            visible=True
        )
        
        # 并行处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for path in archive_files:
                future = executor.submit(ArchiveCleaner.process_archive, path)
                futures.append(future)
            
            # 更新进度
            completed = 0
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"任务执行失败: {e}")
                finally:
                    completed += 1
                    progress.update(overall_task, advance=1)
    
    console.print("[bold green]✨ 处理完成![/]")

def get_target_directory(args) -> str:
    """获取目标目录"""
    if args.clipboard:
        try:
            target_directory = pyperclip.paste().strip().strip('"')
            if not os.path.exists(target_directory):
                console.print(f"[bold red]剪贴板中的路径无效: {target_directory}[/]")
                sys.exit(1)
            console.print(f"[bold blue]从剪贴板读取路径: {target_directory}[/]")
            return target_directory
        except Exception as e:
            console.print(f"[bold red]从剪贴板读取路径失败: {e}[/]")
            sys.exit(1)
    elif args.path:
        if not os.path.exists(args.path):
            console.print(f"[bold red]指定的路径无效: {args.path}[/]")
            sys.exit(1)
        return args.path
    else:
        # 使用rich提示输入
        while True:
            target_directory = Prompt.ask(
                "[bold cyan]请输入要处理的目录路径[/]",
                default=r"E:\2EHV"
            )
            target_directory = target_directory.strip().strip('"')
            
            if os.path.exists(target_directory):
                return target_directory
            else:
                console.print("[bold red]输入的路径无效，请重新输入[/]")

def main():
    parser = argparse.ArgumentParser(description='清理压缩包中的元数据文件')
    parser.add_argument('-c', '--clipboard', action='store_true', help='从剪贴板读取路径')
    parser.add_argument('--path', help='要处理的路径')
    args = parser.parse_args()
    
    # 获取目标目录
    target_directory = get_target_directory(args)
    
    # 处理目录
    process_directory(target_directory)

if __name__ == '__main__':
    main()
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
import multiprocessing
from datetime import datetime
import py7zr
import tempfile

# 创建日志目录
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

# 生成日志文件名
log_file = os.path.join(log_dir, f'clean_archive_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

# 配置rich控制台
console = Console()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        RichHandler(console=console, rich_tracebacks=True),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 记录启动信息
logger.info("程序启动")
logger.info(f"日志文件保存在: {log_file}")

class ArchiveCleaner:
    """压缩包清理类"""
    
    @staticmethod
    def list_archive_contents(archive_path: str) -> List[str]:
        """列出压缩包中的文件"""
        try:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                return zf.namelist()
        except Exception as e:
            logger.debug(f"使用zipfile读取失败: {e}，尝试使用7z")
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
            except subprocess.CalledProcessError as e:
                logger.error(f"使用7z读取失败: {e}")
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
        """使用BandZip命令行删除文件"""
        if not files_to_delete:
            return True

        archive_name = os.path.basename(archive_path)
        logger.info(f"开始处理压缩包: {archive_name}")
        logger.info(f"需要删除的文件: {files_to_delete}")

        try:
            # 备份原文件
            backup_path = archive_path + ".bak"
            shutil.copy2(archive_path, backup_path)
            logger.info(f"[备份] 创建原文件备份: {backup_path}")

            # 使用BandZip删除文件
            deleted_count = 0
            for file in files_to_delete:
                try:
                    # 使用BandZip的bz命令删除文件
                    result = subprocess.run(
                        [
                            'bz', 'd',          # 删除命令
                            archive_path,        # 压缩包路径
                            file,               # 要删除的文件
                            '/q',               # 安静模式
                            '/y',               # 自动确认
                            '/utf8'             # 使用UTF-8编码
                        ],
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='ignore'
                    )

                    # 检查是否成功
                    if result.returncode == 0:
                        deleted_count += 1
                        logger.info(f"[删除成功] {file}")
                    else:
                        logger.warning(f"删除失败: {file}")
                        logger.debug(f"BandZip输出: {result.stdout}\n{result.stderr}")

                except Exception as e:
                    logger.error(f"删除文件失败 {file}: {e}")

            # 检查是否有文件被删除
            if deleted_count == 0:
                logger.warning("未成功删除任何文件")
                # 恢复备份
                if os.path.exists(backup_path):
                    shutil.copy2(backup_path, archive_path)
                    logger.info("[恢复] 从备份恢复原文件")
                return False

            logger.info(f"[完成] 成功删除了 {deleted_count} 个文件")
            
            # 删除备份
            if os.path.exists(backup_path):
                os.remove(backup_path)
            
            return True

        except Exception as e:
            logger.error(f"处理过程中发生错误: {e}")
            # 恢复备份
            if os.path.exists(backup_path):
                try:
                    shutil.copy2(backup_path, archive_path)
                    logger.info("[恢复] 从备份恢复原文件")
                except Exception as e:
                    logger.error(f"恢复备份失败: {e}")
            return False

        finally:
            # 确保删除备份文件
            if os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                    logger.debug("[清理] 删除备份文件")
                except Exception as e:
                    logger.error(f"删除备份文件失败: {e}")

    @staticmethod
    def process_archive(archive_path: str) -> None:
        """处理单个压缩包"""
        try:
            yaml_files, json_files = ArchiveCleaner.analyze_archive(archive_path)
            
            # 如果没有需要删除的文件，则跳过处理
            if not yaml_files and not json_files:
                logger.debug(f"跳过处理 {os.path.basename(archive_path)}: 未找到需要删除的文件")
                return
            
            # 合并所有需要删除的文件
            files_to_delete = [f for f, _ in yaml_files]
            files_to_delete.extend([f for f, _ in json_files if not f.endswith('meta.json')])
            
            if files_to_delete:
                logger.info(f"找到需要删除的文件: YAML({len(yaml_files)}), JSON({len(json_files)})")
                if ArchiveCleaner.delete_files_from_archive(archive_path, files_to_delete):
                    logger.info(f"[完成] {os.path.basename(archive_path)}")
                else:
                    logger.error(f"[失败] {os.path.basename(archive_path)}")
            else:
                logger.debug(f"跳过处理 {os.path.basename(archive_path)}: 没有需要删除的文件")
            
        except Exception as e:
            logger.error(f"处理失败 {archive_path}: {e}")

def process_directory(target_directory: str, max_workers: int = None) -> None:
    """处理目录中的所有压缩包"""
    # 如果没有指定线程数，则使用CPU核心数的2倍（因为是IO密集型任务）
    if max_workers is None:
        max_workers = multiprocessing.cpu_count() * 2
    
    # 记录处理信息
    logger.info(f"开始处理目录: {target_directory}")
    logger.info(f"使用线程数: {max_workers}")
    
    # 收集所有压缩包
    console.print("[bold blue]正在扫描压缩包...[/]")
    archive_files = []
    for root, _, files in os.walk(target_directory):
        for file in files:
            if file.endswith(('.zip', '.rar', '.7z')):
                archive_files.append(os.path.join(root, file))
    
    total_files = len(archive_files)
    console.print(f"[bold green]找到 {total_files} 个压缩包[/]")
    console.print(f"[bold blue]使用 {max_workers} 个线程进行处理[/]")
    
    # 记录扫描结果
    logger.info(f"扫描完成，共找到 {total_files} 个压缩包")
    
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
                default=r"E:\1EHV"
            )
            target_directory = target_directory.strip().strip('"')
            
            if os.path.exists(target_directory):
                return target_directory
            else:
                console.print("[bold red]输入的路径无效，请重新输入[/]")

def main():
    try:
        parser = argparse.ArgumentParser(description='清理压缩包中的元数据文件')
        parser.add_argument('-c', '--clipboard', action='store_true', help='从剪贴板读取路径')
        parser.add_argument('--path', help='要处理的路径')
        parser.add_argument('-w', '--workers', type=int, help='线程数量（默认为CPU核心数的2倍）')
        args = parser.parse_args()
        
        # 获取目标目录
        target_directory = get_target_directory(args)
        
        # 处理目录
        process_directory(target_directory, args.workers)
        
        # 记录完成信息
        logger.info("程序执行完成")
        console.print(f"[bold green]日志已保存到: {log_file}[/]")
        
    except Exception as e:
        logger.exception("程序执行过程中发生错误")
        console.print("[bold red]程序执行出错，详细信息请查看日志文件[/]")
        sys.exit(1)

if __name__ == '__main__':
    main()
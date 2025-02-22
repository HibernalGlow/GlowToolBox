#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
行去重工具
------------------------

功能说明：
    用于对比两个预制文件中的行内容，如果文件A中的行包含了文件B中的任何行，
    则从文件A中删除该行。主要用于过滤重复或相关的内容。

使用方法：
    直接运行脚本即可，会自动处理预制文件夹中的文件：
    D:/1VSCODE/GlowToolBox/src/nodes/refactor/lines_dedup_file/

注意事项：
    1. 文件编码应为UTF-8
    2. 预制文件夹中需要有 source.txt 和 filter.txt 两个文件
    3. 结果会保存在同一目录下的 output.txt 中

作者：Claude
创建日期：2024-03-xx
"""

import re
from pathlib import Path
from typing import Set, Optional, Union
from rich import print as rprint
from rich.console import Console
from collections import Counter

console = Console()

# 预制文件路径
BASE_DIR = Path("D:/1VSCODE/GlowToolBox/src/nodes/refactor/lines_dedup_file")
SOURCE_FILE = BASE_DIR / "source.txt"
FILTER_FILE = BASE_DIR / "filter.txt" 
OUTPUT_FILE = BASE_DIR / "output.txt"

def normalize_line(line: str) -> str:
    """
    标准化行内容，去除首尾空白
    
    Args:
        line: 原始行字符串
        
    Returns:
        标准化后的字符串
    """
    return line.strip()

def read_lines(file_path: Union[str, Path]) -> Set[str]:
    """
    读取文件中的行并返回集合
    
    Args:
        file_path: 文件路径
        
    Returns:
        行内容集合
    """
    lines = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if line.strip():
                    normalized_line = normalize_line(line)
                    lines.append(normalized_line)
        
        # 检查重复行
        line_counts = Counter(lines)
        duplicates = {line: count for line, count in line_counts.items() if count > 1}
        if duplicates:
            rprint("[bold red]发现重复行:[/bold red]")
            for line, count in duplicates.items():
                rprint(f"[red]内容: {line} 出现了 {count} 次[/red]")
        
        unique_lines = set(lines)
        rprint(f"[bold blue]从 {file_path} 读取到 {len(lines)} 行 (去重后 {len(unique_lines)} 行)[/bold blue]")
        return unique_lines
    except Exception as e:
        rprint(f"[bold red]读取文件 {file_path} 时出错: {e}[/bold red]")
        return set()

def filter_lines(lines_a: Set[str], lines_b: Set[str]) -> Set[str]:
    """
    过滤出在A中但不包含B中任何行的内容
    
    Args:
        lines_a: A文件中的行集合
        lines_b: B文件中的行集合
        
    Returns:
        过滤后的行集合
    """
    filtered_lines = set()
    removed_lines = set()
    
    rprint("\n[bold cyan]开始过滤过程:[/bold cyan]")
    rprint(f"[cyan]源文件中共有 {len(lines_a)} 个唯一行[/cyan]")
    rprint(f"[cyan]过滤文件中共有 {len(lines_b)} 个唯一行[/cyan]")
    
    for line_a in lines_a:
        should_keep = True
        for line_b in lines_b:
            if line_b in line_a:
                should_keep = False
                rprint(f"[red]移除行: {line_a}[/red]")
                rprint(f"[yellow]因为包含: {line_b}[/yellow]")
                removed_lines.add(line_a)
                break
        if should_keep:
            filtered_lines.add(line_a)
    
    rprint("\n[bold green]过滤统计:[/bold green]")
    rprint(f"[red]被移除的行数: {len(removed_lines)}[/red]")
    rprint(f"[green]保留的行数: {len(filtered_lines)}[/green]")
    
    return filtered_lines

def main():
    # 确保目录存在
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    
    # 检查必需文件是否存在
    if not SOURCE_FILE.exists():
        rprint(f"[bold red]错误：源文件不存在: {SOURCE_FILE}[/bold red]")
        return
    if not FILTER_FILE.exists():
        rprint(f"[bold red]错误：过滤文件不存在: {FILTER_FILE}[/bold red]")
        return
    
    # 读取文件
    lines_source = read_lines(SOURCE_FILE)
    lines_filter = read_lines(FILTER_FILE)
    
    if not lines_source or not lines_filter:
        rprint("[bold red]错误：输入文件为空或无法读取[/bold red]")
        return
    
    # 过滤行内容
    filtered_lines = filter_lines(lines_source, lines_filter)
    
    # 写入结果
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            for line in sorted(filtered_lines):
                f.write(f"{line}\n")
        rprint(f"[bold green]处理完成！共过滤出 {len(filtered_lines)} 个唯一行[/bold green]")
        rprint(f"[bold green]结果已保存到: {OUTPUT_FILE}[/bold green]")
    except Exception as e:
        rprint(f"[bold red]写入输出文件时出错: {e}[/bold red]")

if __name__ == "__main__":
    main() 
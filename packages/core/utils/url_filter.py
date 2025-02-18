#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
使用方法示例：
    cd D:/1VSCODE
    python ./1ehv/utils/url_filter.py 1.md 2.md 3.md

URL过滤工具 (命令行版本)
------------------------

功能说明：
    用于对比两个文件中的URL，如果文件A中的URL包含了文件B中的任何URL，
    则从文件A中删除该URL。主要用于过滤重复或相关的URL链接。

使用方法：
    1. 基本用法：
       python url_filter.py 文件A.txt 文件B.txt 输出.txt

    2. 相对路径：
       cd 到项目目录后运行
       python ./1ehv/utils/url_filter.py 1.md 2.md 3.md

参数说明：
    文件A.txt: 基准文件，包含需要过滤的URL列表
    文件B.txt: 包含用于匹配的URL列表
    输出.txt:  过滤后的结果文件

注意事项：
    1. 文件编码应为UTF-8
    2. 每行一个URL
    3. 支持各种URL编码格式
    4. 会自动处理URL编码和特殊字符

作者：Claude
创建日期：2024-03-xx
"""

import re
import sys
from pathlib import Path
from typing import Set, Optional, Union
from urllib.parse import unquote, quote, urlparse
from rich import print as rprint
from rich.console import Console
from collections import Counter

console = Console()

def normalize_url(url: str) -> str:
    """
    标准化URL，处理各种编码情况
    
    Args:
        url: 原始URL字符串
        
    Returns:
        标准化后的URL字符串
    """
    # 首先进行完整的URL解码
    decoded_url = unquote(url.strip())
    # 再次解码以处理双重编码的情况
    decoded_url = unquote(decoded_url)
    
    # 处理常见的HTML编码字符
    html_entities = {
        '%20': ' ',  # 空格
        '%2B': '+',  # 加号
        '%2F': '/',  # 斜杠
        '%3F': '?',  # 问号
        '%3D': '=',  # 等号
        '%26': '&',  # &符号
        '%25': '%',  # %符号
        '%23': '#',  # #符号
        '%5B': '[',  # [
        '%5D': ']',  # ]
        '%7B': '{',  # {
        '%7D': '}',  # }
        '%7C': '|',  # |
        '%5C': '\\', # 反斜杠
        '%3A': ':',  # 冒号
        '%3B': ';',  # 分号
        '%3C': '<',  # <
        '%3E': '>',  # >
        '%40': '@',  # @
        '%2C': ',',  # 逗号
    }
    
    # for encoded, decoded in html_entities.items():
    #     decoded_url = decoded_url.replace(encoded, decoded)
    
    return decoded_url

def read_urls(file_path: Union[str, Path]) -> Set[str]:
    """
    读取文件中的URL并返回集合
    
    Args:
        file_path: 文件路径
        
    Returns:
        URL集合
    """
    urls = []  # 先使用列表来收集所有URL，包括重复的
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if line.strip():
                    original_url = line.strip()
                    normalized_url = normalize_url(original_url)
                    if original_url != normalized_url:
                        rprint(f"[yellow]URL标准化 (第{line_num}行): [/yellow]")
                        rprint(f"[red]原始: {original_url}[/red]")
                        rprint(f"[green]标准化: {normalized_url}[/green]")
                    urls.append(normalized_url)
        
        # 检查重复URL
        url_counts = Counter(urls)
        duplicates = {url: count for url, count in url_counts.items() if count > 1}
        if duplicates:
            rprint("[bold red]发现重复URL:[/bold red]")
            for url, count in duplicates.items():
                rprint(f"[red]URL: {url} 出现了 {count} 次[/red]")
        
        unique_urls = set(urls)
        rprint(f"[bold blue]从 {file_path} 读取到 {len(urls)} 个URL (去重后 {len(unique_urls)} 个)[/bold blue]")
        return unique_urls
    except Exception as e:
        rprint(f"[bold red]读取文件 {file_path} 时出错: {e}[/bold red]")
        return set()

def filter_urls(urls_a: Set[str], urls_b: Set[str]) -> Set[str]:
    """
    过滤出在A中但不包含B中任何URL的URL
    
    Args:
        urls_a: A文件中的URL集合
        urls_b: B文件中的URL集合
        
    Returns:
        过滤后的URL集合
    """
    filtered_urls = set()
    removed_urls = set()
    
    rprint("\n[bold cyan]开始过滤过程:[/bold cyan]")
    rprint(f"[cyan]文件A中共有 {len(urls_a)} 个唯一URL[/cyan]")
    rprint(f"[cyan]文件B中共有 {len(urls_b)} 个唯一URL[/cyan]")
    
    for url_a in urls_a:
        # 检查url_a是否包含任何url_b
        should_keep = True
        for url_b in urls_b:
            if url_b in url_a:  # 如果url_a包含了任何一个url_b
                should_keep = False
                rprint(f"[red]移除URL: {url_a}[/red]")
                rprint(f"[yellow]因为包含: {url_b}[/yellow]")
                removed_urls.add(url_a)
                break
        if should_keep:
            filtered_urls.add(url_a)
    
    rprint("\n[bold green]过滤统计:[/bold green]")
    rprint(f"[red]被移除的URL数量: {len(removed_urls)}[/red]")
    rprint(f"[green]保留的URL数量: {len(filtered_urls)}[/green]")
    
    return filtered_urls

def main():
    if len(sys.argv) != 4:
        print("用法: python url_filter.py 文件A.txt 文件B.txt 输出.txt")
        print("功能: 输出文件A中不包含文件B中URL的行")
        sys.exit(1)
    
    # 使用 Path 对象来处理文件路径，避免反斜杠问题
    file_a = Path(sys.argv[1])
    file_b = Path(sys.argv[2])
    output_file = Path(sys.argv[3])
    
    # 读取文件
    urls_a = read_urls(file_a)
    urls_b = read_urls(file_b)
    
    if not urls_a or not urls_b:
        print("错误：输入文件为空或无法读取")
        sys.exit(1)
    
    # 过滤URL
    filtered_urls = filter_urls(urls_a, urls_b)
    
    # 写入结果
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for url in sorted(filtered_urls):
                f.write(f"{url}\n")
        print(f"处理完成！共过滤出 {len(filtered_urls)} 个唯一URL")
        print(f"结果已保存到: {output_file}")
    except Exception as e:
        print(f"写入输出文件时出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
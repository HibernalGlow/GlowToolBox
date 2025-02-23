"""压缩包分组模块"""
import os
from pathlib import Path
from typing import Dict, List, Tuple

def clean_filename(filename: str) -> str:
    """清理文件名，只保留主文件名部分进行比较"""
    # 移除扩展名
    name = os.path.splitext(filename)[0]
    # 移除所有括号内容
    import re
    name = re.sub(r'\[([^\[\]]+)\]', '', name)  # 移除方括号
    name = re.sub(r'\(([^\(\)]+)\)', '', name)  # 移除圆括号
    name = re.sub(r'\{(.*?)\}', '', name)  # 移除花括号
    # 完全去除所有空格
    name = re.sub(r'\s+', '', name)
    return name.strip().lower()

def is_chinese_version(filename: str) -> bool:
    """判断是否为汉化版本"""
    CHINESE_KEYWORDS = ['汉化', '漢化', '翻译', '中文', '中国', 'Chinese']
    filename_lower = filename.lower()
    return any(keyword.lower() in filename_lower for keyword in CHINESE_KEYWORDS)

def group_archives(directory: str) -> Dict[str, Tuple[str, List[str]]]:
    """
    对目录中的压缩包进行分组
    
    Args:
        directory: 目录路径
        
    Returns:
        Dict[str, Tuple[str, List[str]]]: {文件名: (组类型, [相似文件列表])}
        组类型: 'single' - 单文件, 'multi_main' - 多文件主文件, 'multi_other' - 多文件其他
    """
    # 收集压缩包
    archives = []
    for root, _, files in os.walk(directory):
        if 'trash' in root or 'multi' in root:
            continue
        for file in files:
            if file.lower().endswith(('.zip', '.rar', '.7z', '.cbz', '.cbr')):
                rel_path = os.path.relpath(os.path.join(root, file), directory)
                archives.append(rel_path)
    
    # 按清理后的文件名分组
    groups: Dict[str, List[str]] = {}
    for archive in archives:
        clean_name = clean_filename(os.path.basename(archive))
        if clean_name not in groups:
            groups[clean_name] = []
        groups[clean_name].append(archive)
    
    # 确定每个文件的组类型
    result: Dict[str, Tuple[str, List[str]]] = {}
    for group_files in groups.values():
        if len(group_files) == 1:
            # 单文件组
            result[group_files[0]] = ('single', group_files)
        else:
            # 多文件组
            # 找出最大的文件（优先汉化版）
            chinese_versions = [f for f in group_files if is_chinese_version(f)]
            if chinese_versions:
                main_file = max(chinese_versions, 
                              key=lambda x: os.path.getsize(os.path.join(directory, x)))
            else:
                main_file = max(group_files, 
                              key=lambda x: os.path.getsize(os.path.join(directory, x)))
            
            # 标记主文件和其他文件
            result[main_file] = ('multi_main', group_files)
            for other in group_files:
                if other != main_file:
                    result[other] = ('multi_other', group_files)
    
    return result 
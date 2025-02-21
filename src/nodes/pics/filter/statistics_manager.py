"""
压缩包处理模块

功能：
1. 自动检测系统7z路径
2. 内存中直接处理压缩包内容
3. 支持多编码文件名自动识别
4. 提供同步/异步两种处理接口
"""

import sys
import subprocess
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Generator, AsyncGenerator
import platform
import asyncio
import shutil
import os
import time
from nodes.pics.filter.backup_handler import BackupHandler

class StatisticsManager:
    """Statistics"""
    processed_count = 0
    total_count = 0
    hash_duplicates_count = 0  # 哈希文件去重的数量
    normal_duplicates_count = 0  # 普通去重的数量
    small_images_count = 0  # 小图数量
    white_images_count = 0  # 白图数量

    @staticmethod
    def update_progress():
        """更新进度显示"""
        if StatisticsManager.total_count > 0:
            percentage = (StatisticsManager.processed_count / StatisticsManager.total_count) * 100
            # 更新总体统计信息
            stats_str = (
                f"处理进度: {StatisticsManager.processed_count}/{StatisticsManager.total_count}\n"
                f"哈希去重: {StatisticsManager.hash_duplicates_count} 张\n"
                f"普通去重: {StatisticsManager.normal_duplicates_count} 张\n"
                f"小图: {StatisticsManager.small_images_count} 张\n"
                f"白图: {StatisticsManager.white_images_count} 张"
            )
            logging.info(f"[#cur_stats]{stats_str}")
            
            # 使用进度条面板显示总体进度
            logging.info(f"[@cur_stats] 总体进度 {percentage:.1f}%")

    @staticmethod
    def increment():
        """增加处理计数并更新进度"""
        StatisticsManager.processed_count += 1
        StatisticsManager.update_progress()

    @staticmethod
    def set_total(total):
        """设置总数并重置所有计数"""
        StatisticsManager.total_count = total
        StatisticsManager.processed_count = 0
        StatisticsManager.hash_duplicates_count = 0
        StatisticsManager.normal_duplicates_count = 0
        StatisticsManager.small_images_count = 0
        StatisticsManager.white_images_count = 0
        StatisticsManager.update_progress()


    @staticmethod
    def update_counts(hash_duplicates=0, normal_duplicates=0, small_images=0, white_images=0):
        """更新各类型文件的计数"""
        StatisticsManager.hash_duplicates_count += hash_duplicates
        StatisticsManager.normal_duplicates_count += normal_duplicates
        StatisticsManager.small_images_count += small_images
        StatisticsManager.white_images_count += white_images
        StatisticsManager.update_progress()


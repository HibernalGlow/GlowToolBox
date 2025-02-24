"""
Multi文件分析器模块
提供对压缩包文件的宽度、页数和清晰度分析功能
"""

import os
import logging
from typing import List, Dict, Tuple, Union, Optional
from pathlib import Path
import zipfile
from PIL import Image
import cv2
import numpy as np
from io import BytesIO
import random
from concurrent.futures import ThreadPoolExecutor
from .calculate_hash_custom import ImageClarityEvaluator

logger = logging.getLogger(__name__)

class MultiAnalyzer:
    """Multi文件分析器，用于分析压缩包中图片的宽度、页数和清晰度"""
    
    def __init__(self, sample_count: int = 3):
        """
        初始化分析器
        
        Args:
            sample_count: 每个压缩包抽取的图片样本数量
        """
        self.sample_count = sample_count
        self.supported_extensions = {
            '.jpg', '.jpeg', '.png', '.webp', '.avif', 
            '.jxl', '.gif', '.bmp', '.tiff', '.tif', 
            '.heic', '.heif'
        }
    
    def get_archive_info(self, archive_path: str) -> List[Tuple[str, int]]:
        """获取压缩包中的文件信息"""
        try:
            image_files = []
            with zipfile.ZipFile(archive_path, 'r') as zf:
                for info in zf.infolist():
                    ext = os.path.splitext(info.filename.lower())[1]
                    if ext in self.supported_extensions:
                        image_files.append((info.filename, info.file_size))
            return image_files
        except Exception as e:
            logger.error(f"获取压缩包信息失败 {archive_path}: {str(e)}")
            return []

    def get_image_count(self, archive_path: str) -> int:
        """计算压缩包中的图片总数"""
        image_files = self.get_archive_info(archive_path)
        return len(image_files)

    def calculate_representative_width(self, archive_path: str) -> int:
        """计算压缩包中图片的代表宽度（使用抽样和中位数）"""
        try:
            # 检查文件扩展名
            ext = os.path.splitext(archive_path)[1].lower()
            if ext not in {'.zip', '.cbz'}:  # 只处理zip格式
                return 0

            # 获取压缩包中的文件信息
            image_files = []
            try:
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    for info in zf.infolist():
                        if os.path.splitext(info.filename.lower())[1] in self.supported_extensions:
                            image_files.append((info.filename, info.file_size))
            except zipfile.BadZipFile:
                logger.error(f"无效的ZIP文件: {archive_path}")
                return 0

            if not image_files:
                return 0

            # 按文件大小排序
            image_files.sort(key=lambda x: x[1], reverse=True)
            
            # 选择样本
            samples = []
            if image_files:
                samples.append(image_files[0][0])  # 最大的文件
                if len(image_files) > 2:
                    samples.append(image_files[len(image_files)//2][0])  # 中间的文件
                
                # 从前30%选择剩余样本
                top_30_percent = image_files[:max(3, len(image_files) // 3)]
                while len(samples) < self.sample_count and top_30_percent:
                    sample = random.choice(top_30_percent)[0]
                    if sample not in samples:
                        samples.append(sample)

            widths = []
            try:
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    for sample in samples:
                        try:
                            # 直接从zip读取到内存
                            with zf.open(sample) as file:
                                img_data = file.read()
                                with Image.open(BytesIO(img_data)) as img:
                                    widths.append(img.width)
                        except Exception as e:
                            logger.error(f"读取图片宽度失败 {sample}: {str(e)}")
                            continue
            except Exception as e:
                logger.error(f"打开ZIP文件失败: {str(e)}")
                return 0

            if not widths:
                return 0

            # 使用中位数作为代表宽度
            return int(sorted(widths)[len(widths)//2])

        except Exception as e:
            logger.error(f"计算代表宽度失败 {archive_path}: {str(e)}")
            return 0

    def calculate_clarity_score(self, archive_path: str) -> float:
        """计算压缩包中图片的清晰度评分"""
        try:
            # 获取压缩包中的文件信息
            image_files = self.get_archive_info(archive_path)
            if not image_files:
                return 0.0

            # 按文件大小排序并选择样本
            image_files.sort(key=lambda x: x[1], reverse=True)
            samples = []
            if image_files:
                samples.append(image_files[0][0])  # 最大的文件
                if len(image_files) > 2:
                    samples.append(image_files[len(image_files)//2][0])  # 中间的文件
                
                # 从前30%选择剩余样本
                top_30_percent = image_files[:max(3, len(image_files) // 3)]
                while len(samples) < self.sample_count and top_30_percent:
                    sample = random.choice(top_30_percent)[0]
                    if sample not in samples:
                        samples.append(sample)

            # 计算样本的清晰度评分
            scores = []
            with zipfile.ZipFile(archive_path, 'r') as zf:
                for sample in samples:
                    try:
                        with zf.open(sample) as f:
                            img_data = f.read()
                            score = ImageClarityEvaluator.calculate_definition(img_data)
                            scores.append(score)
                    except Exception as e:
                        logger.error(f"计算清晰度失败 {sample}: {str(e)}")
                        continue

            # 返回平均清晰度评分
            return sum(scores) / len(scores) if scores else 0.0

        except Exception as e:
            logger.error(f"计算清晰度评分失败 {archive_path}: {str(e)}")
            return 0.0

    def analyze_archive(self, archive_path: str) -> Dict[str, Union[int, float]]:
        """分析压缩包，返回宽度、页数和清晰度信息"""
        try:
            # 并行计算所有指标
            with ThreadPoolExecutor() as executor:
                width_future = executor.submit(self.calculate_representative_width, archive_path)
                count_future = executor.submit(self.get_image_count, archive_path)
                clarity_future = executor.submit(self.calculate_clarity_score, archive_path)

                # 获取结果
                width = width_future.result()
                count = count_future.result()
                clarity = clarity_future.result()

            return {
                'width': width,
                'page_count': count,
                'clarity_score': clarity
            }
        except Exception as e:
            logger.error(f"分析压缩包失败 {archive_path}: {str(e)}")
            return {
                'width': 0,
                'page_count': 0,
                'clarity_score': 0.0
            }

    def format_analysis_result(self, result: Dict[str, Union[int, float]]) -> str:
        """格式化分析结果为字符串"""
        width = result['width']
        count = result['page_count']
        clarity = result['clarity_score']
        
        parts = []
        if width > 0:
            parts.append(f"{width}@WD")
        if count > 0:
            parts.append(f"{count}@PX")
        if clarity > 0:
            parts.append(f"{int(clarity)}@DE")
            
        return "{" + ",".join(parts) + "}" if parts else "" 
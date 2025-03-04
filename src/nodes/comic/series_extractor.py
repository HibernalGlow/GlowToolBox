from typing import List, Dict, Tuple, Optional, Any
import os
import re
from difflib import SequenceMatcher
import functools
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)

class SeriesExtractor:
    """漫画系列提取器类"""
    
    def __init__(self, similarity_config: dict = None):
        """
        初始化系列提取器
        
        Args:
            similarity_config: 相似度配置字典，包含以下键：
                - similarity: 基本相似度阈值(0-100)
                - ratio: 完全匹配阈值(0-100)
                - partial: 部分匹配阈值(0-100)
                - token: 标记匹配阈值(0-100)
                - length_diff: 长度差异最大值(0-1)
        """
        # 设置默认配置
        default_config = {
            "similarity": 80,
            "ratio": 75,
            "partial": 85,
            "token": 80,
            "length_diff": 0.3
        }
        self.config = {**default_config, **(similarity_config or {})}
        
    def normalize_filename(self, filename: str) -> str:
        """标准化文件名"""
        # 移除扩展名
        filename = os.path.splitext(filename)[0]
        
        # 移除常见标记
        patterns = [
            r'\[.*?\]',  # 方括号内容
            r'\(.*?\)',  # 圆括号内容
            r'【.*?】',  # 中文方括号内容
            r'（.*?）',  # 中文圆括号内容
            r'第\d+(?:话|章|回|集|卷)',  # 章节标记
            r'vol\.\d+',  # 卷数标记
            r'ch\.\d+',   # 章节标记
            r'#\d+',      # 章节标记
            r'\d{2,4}年\d{1,2}月号?',  # 日期标记
        ]
        
        for pattern in patterns:
            filename = re.sub(pattern, '', filename, flags=re.IGNORECASE)
            
        # 移除特殊字符，保留中文、英文、数字
        filename = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', filename)
        
        return filename.strip()

    def get_base_filename(self, filename: str) -> str:
        """获取基础文件名（移除扩展名和序号）"""
        # 移除扩展名
        name = os.path.splitext(filename)[0]
        
        # 移除序号模式
        patterns = [
            r'\s*\d+(?:话|章|回|集|卷)?\s*$',  # 中文章节
            r'\s*(?:第|Ch\.|Chapter\s*)\d+\s*$',  # 带前缀的章节
            r'\s*#?\d+\s*$',  # 普通数字
            r'\s*\(\d+\)\s*$',  # 括号中的数字
            r'\s*\[\d+\]\s*$',  # 方括号中的数字
        ]
        
        for pattern in patterns:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)
        
        return name.strip()

    def is_essentially_same_file(self, file1: str, file2: str) -> bool:
        """判断两个文件是否本质上是同一个文件的不同版本"""
        base1 = self.get_base_filename(file1)
        base2 = self.get_base_filename(file2)
        
        if not base1 or not base2:
            return False
            
        # 如果完全相同
        if base1 == base2:
            return True
            
        # 计算相似度
        similarity = SequenceMatcher(None, base1, base2).ratio() * 100
        return similarity >= self.config["similarity"]

    def calculate_similarity(self, str1: str, str2: str) -> float:
        """计算两个字符串的相似度"""
        if not str1 or not str2:
            return 0.0
            
        # 标准化字符串
        str1 = self.normalize_filename(str1)
        str2 = self.normalize_filename(str2)
        
        if not str1 or not str2:
            return 0.0
            
        # 计算相似度
        similarity = SequenceMatcher(None, str1, str2).ratio() * 100
        
        logger.debug(f"计算相似度: {str1} vs {str2} = {similarity:.2f}%")
            
        return similarity

    def extract_keywords(self, filename: str) -> List[str]:
        """提取文件名中的关键词"""
        # 预处理文件名
        name = self.normalize_filename(filename)
        
        # 分割成单词（考虑中文和英文）
        words = []
        # 提取英文单词
        eng_words = re.findall(r'[a-zA-Z]+', name)
        words.extend(eng_words)
        
        # 移除英文单词，处理剩余的中文
        chinese_text = re.sub(r'[a-zA-Z]+', '', name)
        # 对于中文，每个字符作为一个关键词
        words.extend(list(chinese_text))
        
        return [w.lower() for w in words if len(w) > 0]

    def find_longest_common_keywords(self, keywords1: List[str], keywords2: List[str]) -> List[str]:
        """找出两组关键词中最长的公共部分"""
        if not keywords1 or not keywords2:
            return []
            
        # 使用集合找出公共关键词
        common = set(keywords1) & set(keywords2)
        return sorted(list(common), key=lambda x: (-len(x), x))

    def find_keyword_based_groups(self, files: List[str]) -> List[List[str]]:
        """基于关键词查找相似文件组"""
        if not files:
            return []
            
        # 预处理所有文件名的关键词
        file_keywords = {f: self.extract_keywords(f) for f in files}
        
        # 已处理的文件
        processed = set()
        groups = []
        
        def process_file_keywords(current_file: str) -> List[str]:
            """处理单个文件的关键词匹配"""
            if current_file in processed:
                return []
                
            current_keywords = file_keywords[current_file]
            if not current_keywords:
                return []
                
            group = [current_file]
            processed.add(current_file)
            
            # 查找相似文件
            for other_file in files:
                if other_file in processed:
                    continue
                    
                other_keywords = file_keywords[other_file]
                if not other_keywords:
                    continue
                    
                # 找出公共关键词
                common = self.find_longest_common_keywords(current_keywords, other_keywords)
                if not common:
                    continue
                    
                # 计算关键词匹配率
                match_ratio = len(common) / max(len(current_keywords), len(other_keywords)) * 100
                
                if match_ratio >= self.config["token"]:
                    group.append(other_file)
                    processed.add(other_file)
                    
            return group if len(group) > 1 else []
            
        # 使用线程池处理文件
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(process_file_keywords, f) for f in files]
            for future in as_completed(futures):
                group = future.result()
                if group:
                    groups.append(group)
                    
        return groups

    def find_series_groups(self, filenames: List[str]) -> List[List[str]]:
        """查找文件系列分组"""
        if not filenames:
            return []
            
        # 预处理文件名
        processed_names = [(f, self.normalize_filename(f)) for f in filenames]
        
        # 移除空的处理结果
        processed_names = [(f, n) for f, n in processed_names if n]
        
        if not processed_names:
            return []
            
        # 已处理的文件
        processed = set()
        groups = []
        
        for filename, normalized in processed_names:
            if filename in processed:
                continue
                
            current_group = [filename]
            processed.add(filename)
            
            # 查找相似文件
            for other_file, other_norm in processed_names:
                if other_file in processed:
                    continue
                    
                # 计算文件名相似度
                similarity = self.calculate_similarity(normalized, other_norm)
                
                # 根据不同的相似度阈值进行分组
                if similarity >= self.config["ratio"]:  # 完全匹配
                    current_group.append(other_file)
                    processed.add(other_file)
                elif similarity >= self.config["partial"]:  # 部分匹配
                    # 检查长度差异
                    len_diff = abs(len(normalized) - len(other_norm)) / max(len(normalized), len(other_norm))
                    if len_diff <= self.config["length_diff"]:
                        current_group.append(other_file)
                        processed.add(other_file)
                        
            if len(current_group) > 1:
                groups.append(current_group)
                
        # 如果还有未分组的文件，尝试使用关键词匹配
        remaining = [f for f in filenames if f not in processed]
        if remaining:
            keyword_groups = self.find_keyword_based_groups(remaining)
            groups.extend(keyword_groups)
            
        return groups

    def create_series_folders(self, directory_path: str, archives: List[str]) -> bool:
        """创建系列文件夹并移动文件"""
        if not archives:
            return False
            
        # 查找系列分组
        series_groups = self.find_series_groups(archives)
        if not series_groups:
            logger.info("未找到需要分组的系列")
            return False
            
        # 处理每个系列分组
        for group in series_groups:
            if len(group) < 2:
                continue
                
            # 获取系列名称
            base_name = self.get_base_filename(os.path.basename(group[0]))
            if not base_name:
                continue
                
            # 创建系列文件夹
            series_dir = os.path.join(directory_path, base_name)
            os.makedirs(series_dir, exist_ok=True)
            
            # 移动文件到系列文件夹
            for file_path in group:
                if not os.path.exists(file_path):
                    continue
                    
                target_path = os.path.join(series_dir, os.path.basename(file_path))
                try:
                    os.rename(file_path, target_path)
                    logger.info(f"移动文件到系列文件夹: {file_path} -> {target_path}")
                except Exception as e:
                    logger.error(f"移动文件失败: {e}")
                        
        return True 
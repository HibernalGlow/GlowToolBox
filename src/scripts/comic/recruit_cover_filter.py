from pathlib import Path
import sys
import os
import json
import logging
from typing import List, Dict, Set, Tuple
import time
import subprocess
import argparse
import pyperclip
from nodes.config.import_bundles import *
from nodes.record.logger_config import setup_logger

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from nodes.pics.calculate_hash_custom import ImageHashCalculator, PathURIGenerator
from nodes.pics.watermark_detector import WatermarkDetector

logger = logging.getLogger(__name__)

config = {
    'script_name': 'recruit_cover_filter',
    'console_enabled': False
}
logger, config_info = setup_logger(config)

# 初始化 TextualLoggerManager
HAS_TUI = True
USE_DEBUGGER = True

TEXTUAL_LAYOUT = {
    "cur_stats": {
        "ratio": 1,
        "title": "📊 总体进度",
        "style": "lightyellow"
    },
    "cur_progress": {
        "ratio": 1,
        "title": "🔄 当前进度",
        "style": "lightcyan"
    },
    "file_ops": {
        "ratio": 2,
        "title": "📂 文件操作",
        "style": "lightpink"
    },
    "ocr_results": {
        "ratio": 2,
        "title": "📝 OCR结果",
        "style": "lightgreen"
    },
    "update_log": {
        "ratio": 1,
        "title": "🔧 系统消息",
        "style": "lightwhite"
    }
}

def initialize_textual_logger():
    """初始化日志布局"""
    try:
        TextualLoggerManager.set_layout(TEXTUAL_LAYOUT, config_info['log_file'])
        logger.info("[#update_log]✅ 日志系统初始化完成")
    except Exception as e:
        print(f"❌ 日志系统初始化失败: {e}")

class RecruitCoverFilter:
    """封面图片过滤器"""
    
    def __init__(self, hash_file: str, cover_count: int = 3, hamming_threshold: int = 12):
        """
        初始化过滤器
        
        Args:
            hash_file: 哈希文件路径
            cover_count: 处理的封面图片数量
            hamming_threshold: 汉明距离阈值
        """
        self.hash_file = hash_file
        self.cover_count = cover_count
        self.hamming_threshold = hamming_threshold
        self.hash_cache = self._load_hash_file()
        self.watermark_detector = WatermarkDetector()
        
    def _load_hash_file(self) -> Dict:
        """加载哈希文件"""
        try:
            if os.path.exists(self.hash_file):
                with open(self.hash_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"[#file_ops]成功加载哈希文件: {self.hash_file}")
                return data.get('hashes', {})  # 适配新的哈希文件格式
            else:
                logger.error(f"[#file_ops]哈希文件不存在: {self.hash_file}")
                return {}
        except Exception as e:
            logger.error(f"[#file_ops]加载哈希文件失败: {e}")
            return {}
            
    def _get_image_hash(self, image_path: str) -> str:
        """获取图片哈希值，优先从缓存读取"""
        image_uri = PathURIGenerator.generate(image_path)
        
        # 从缓存中查找
        if image_uri in self.hash_cache:
            hash_data = self.hash_cache[image_uri]
            return hash_data.get('hash') if isinstance(hash_data, dict) else hash_data
            
        # 计算新的哈希值
        try:
            hash_value = ImageHashCalculator.calculate_phash(image_path)
            if hash_value:
                self.hash_cache[image_uri] = {'hash': hash_value}
                return hash_value
        except Exception as e:
            logger.error(f"[#file_ops]计算图片哈希值失败 {image_path}: {e}")
            
        return None
        
    def _find_similar_images(self, image_files: List[str]) -> List[List[str]]:
        """查找相似的图片组"""
        similar_groups = []
        processed = set()
        
        for i, img1 in enumerate(image_files):
            if img1 in processed:
                continue
                
            hash1 = self._get_image_hash(img1)
            if not hash1:
                continue
                
            current_group = [img1]
            
            for j, img2 in enumerate(image_files[i+1:], i+1):
                if img2 in processed:
                    continue
                    
                hash2 = self._get_image_hash(img2)
                if not hash2:
                    continue
                    
                # 计算汉明距离
                distance = ImageHashCalculator.calculate_hamming_distance(hash1, hash2)
                if distance <= self.hamming_threshold:
                    current_group.append(img2)
                    logger.info(f"[#file_ops]找到相似图片: {os.path.basename(img2)} (距离: {distance})")
                    
            if len(current_group) > 1:
                similar_groups.append(current_group)
                processed.update(current_group)
                logger.info(f"[#file_ops]找到相似图片组: {len(current_group)}张")
                
        return similar_groups
        
    def process_images(self, image_files: List[str]) -> Tuple[Set[str], Dict[str, List[str]]]:
        """
        处理图片列表，返回要删除的图片和删除原因
        
        Args:
            image_files: 图片文件路径列表
            
        Returns:
            Tuple[Set[str], Dict[str, List[str]]]: (要删除的文件集合, 删除原因字典)
        """
        # 排序并只取前N张
        sorted_files = sorted(image_files)
        cover_files = sorted_files[:self.cover_count]
        
        if not cover_files:
            return set(), {}
            
        logger.info(f"[#file_ops]处理前{self.cover_count}张图片")
        
        # 查找相似图片组
        similar_groups = self._find_similar_images(cover_files)
        
        # 处理每组相似图片
        to_delete = set()
        removal_reasons = {}
        
        for group in similar_groups:
            # 检测每张图片的水印
            watermark_results = {}
            for img_path in group:
                has_watermark, texts = self.watermark_detector.detect_watermark(img_path)
                watermark_results[img_path] = (has_watermark, texts)
                logger.info(f"[#ocr_results]图片 {os.path.basename(img_path)} OCR结果: {texts}")
            
            # 找出无水印的图片
            clean_images = [img for img, (has_mark, _) in watermark_results.items() 
                          if not has_mark]
            
            if clean_images:
                # 如果有无水印版本，删除其他版本
                keep_image = clean_images[0]
                logger.info(f"[#file_ops]保留无水印图片: {os.path.basename(keep_image)}")
                for img in group:
                    if img != keep_image:
                        to_delete.add(img)
                        removal_reasons[img] = {
                            'reason': 'recruit_cover',
                            'watermark_texts': watermark_results[img][1]
                        }
                        logger.info(f"[#file_ops]标记删除有水印图片: {os.path.basename(img)}")
            else:
                # 如果都有水印，保留第一个
                keep_image = group[0]
                logger.info(f"[#file_ops]保留第一张图片: {os.path.basename(keep_image)}")
                for img in group[1:]:
                    to_delete.add(img)
                    removal_reasons[img] = {
                        'reason': 'recruit_cover',
                        'watermark_texts': watermark_results[img][1]
                    }
                    logger.info(f"[#file_ops]标记删除重复图片: {os.path.basename(img)}")
        
        return to_delete, removal_reasons

    def process_archive(self, zip_path: str) -> bool:
        """处理单个压缩包"""
        try:
            logger.info(f"[#file_ops]开始处理压缩包: {zip_path}")
            
            # 创建临时目录
            temp_dir = os.path.join(os.path.dirname(zip_path), f'temp_{int(time.time())}')
            os.makedirs(temp_dir, exist_ok=True)
            
            # 解压文件
            cmd = ['7z', 'x', zip_path, f'-o{temp_dir}', '-y']
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"[#file_ops]解压失败: {result.stderr}")
                return False
                
            # 获取所有图片文件
            image_files = []
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                        image_files.append(os.path.join(root, file))
            
            if not image_files:
                logger.info("[#file_ops]未找到图片文件")
                shutil.rmtree(temp_dir)
                return False
                
            # 处理图片
            to_delete, removal_reasons = self.process_images(image_files)
            
            if not to_delete:
                logger.info("[#file_ops]没有需要删除的图片")
                shutil.rmtree(temp_dir)
                return False
                
            # 删除标记的文件
            for file_path in to_delete:
                try:
                    os.remove(file_path)
                    reason = removal_reasons[file_path]
                    logger.info(f"[#file_ops]删除文件: {os.path.basename(file_path)}")
                    logger.info(f"[#ocr_results]删除原因: {reason}")
                except Exception as e:
                    logger.error(f"[#file_ops]删除文件失败 {file_path}: {e}")
            
            # 创建新的压缩包
            new_zip = zip_path + '.new'
            cmd = ['7z', 'a', new_zip, os.path.join(temp_dir, '*')]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"[#file_ops]创建新压缩包失败: {result.stderr}")
                shutil.rmtree(temp_dir)
                return False
                
            # 备份原文件并替换
            backup_path = zip_path + '.bak'
            shutil.copy2(zip_path, backup_path)
            os.replace(new_zip, zip_path)
            
            # 清理临时文件
            shutil.rmtree(temp_dir)
            
            logger.info(f"[#file_ops]成功处理压缩包: {zip_path}")
            return True
            
        except Exception as e:
            logger.error(f"[#file_ops]处理压缩包失败 {zip_path}: {e}")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return False

class InputHandler:
    """输入处理类"""
    
    @staticmethod
    def parse_arguments():
        """解析命令行参数"""
        parser = argparse.ArgumentParser(description='招募封面图片过滤工具')
        parser.add_argument('--hash-file', '-hf', type=str, required=True,
                          help='哈希文件路径')
        parser.add_argument('--cover-count', '-cc', type=int, default=3,
                          help='处理的封面图片数量 (默认: 3)')
        parser.add_argument('--hamming-threshold', '-ht', type=int, default=12,
                          help='汉明距离阈值 (默认: 12)')
        parser.add_argument('--clipboard', '-c', action='store_true',
                          help='从剪贴板读取路径')
        parser.add_argument('path', nargs='*', help='要处理的文件或目录路径')
        return parser.parse_args()

    @staticmethod
    def get_input_paths(args):
        """获取输入路径"""
        paths = []
        
        # 从命令行参数获取路径
        if args.path:
            paths.extend(args.path)
            
        # 从剪贴板获取路径
        if args.clipboard:
            try:
                clipboard_content = pyperclip.paste()
                if clipboard_content:
                    paths.extend([p.strip() for p in clipboard_content.splitlines() if p.strip()])
            except Exception as e:
                logger.error(f"[#update_log]从剪贴板读取失败: {e}")
                
        # 如果没有路径，提示用户输入
        if not paths:
            print("请输入要处理的文件夹或压缩包路径（每行一个，输入空行结束）：")
            while True:
                line = input().strip()
                if not line:
                    break
                paths.append(line)
                
        return [p for p in paths if os.path.exists(p)]

class Application:
    """应用程序类"""
    
    def __init__(self):
        initialize_textual_logger()
        
    def process_directory(self, directory: str, filter_instance: RecruitCoverFilter):
        """处理目录"""
        try:
            if os.path.isfile(directory):
                if directory.lower().endswith('.zip'):
                    filter_instance.process_archive(directory)
            else:
                for root, _, files in os.walk(directory):
                    for file in files:
                        if file.lower().endswith('.zip'):
                            zip_path = os.path.join(root, file)
                            filter_instance.process_archive(zip_path)
        except Exception as e:
            logger.error(f"[#update_log]处理目录失败 {directory}: {e}")

    def main(self):
        """主函数"""
        try:
            args = InputHandler.parse_arguments()
            paths = InputHandler.get_input_paths(args)
            
            if not paths:
                logger.error("[#update_log]未提供任何有效路径")
                return
                
            filter_instance = RecruitCoverFilter(
                hash_file=args.hash_file,
                cover_count=args.cover_count,
                hamming_threshold=args.hamming_threshold
            )
            
            for path in paths:
                self.process_directory(path, filter_instance)
                
            logger.info("[#update_log]处理完成")
            
        except Exception as e:
            logger.error(f"[#update_log]程序执行失败: {e}")

if __name__ == '__main__':
    Application().main() 
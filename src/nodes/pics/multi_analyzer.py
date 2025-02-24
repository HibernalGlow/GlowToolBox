"""
Multi文件分析器模块
提供对压缩包文件的宽度、页数和清晰度分析功能
支持命令行单独运行
"""

import os
import logging
from typing import List, Dict, Tuple, Union, Optional
from pathlib import Path
import zipfile
from PIL import Image, ImageFile
import pillow_avif
import pillow_jxl
import warnings
import cv2
import numpy as np
from io import BytesIO
import random
from concurrent.futures import ThreadPoolExecutor
from nodes.pics.calculate_hash_custom import ImageClarityEvaluator
from nodes.utils.number_shortener import shorten_number_cn
import re
from nodes.pics.group_analyzer import GroupAnalyzer

# 抑制所有警告
warnings.filterwarnings('ignore')
# 允许截断的图像文件
ImageFile.LOAD_TRUNCATED_IMAGES = True
# 设置OpenCV的错误处理
 # 限制OpenCV线程数
 # 只显示错误日志

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

    def _safe_open_image(self, img_data: bytes) -> Optional[Image.Image]:
        """安全地打开图片，处理可能的解码错误
        
        Args:
            img_data: 图片二进制数据
            
        Returns:
            Optional[Image.Image]: 成功则返回PIL图像对象，失败则返回None
        """
        try:
            # 首先尝试用PIL直接打开
            img = Image.open(BytesIO(img_data))
            img.verify()  # 验证图像完整性
            return Image.open(BytesIO(img_data))  # 重新打开以便后续使用
        except Exception as e1:
            try:
                # 如果PIL验证失败，尝试用OpenCV打开
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is None:
                    raise ValueError("OpenCV无法解码图像")
                # 转换为RGB
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                return Image.fromarray(img_rgb)
            except Exception as e2:
                try:
                    # 最后尝试直接用PIL打开而不验证
                    return Image.open(BytesIO(img_data))
                except Exception as e3:
                    logger.debug(f"图像解码失败: PIL1={str(e1)}, CV2={str(e2)}, PIL2={str(e3)}")
                    return None

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
                            with zf.open(sample) as file:
                                img_data = file.read()
                                img = self._safe_open_image(img_data)
                                if img is not None:
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
                            # 直接传递二进制数据给清晰度计算函数
                            try:
                                score = ImageClarityEvaluator.calculate_definition(img_data)
                                if score and score > 0:  # 确保得到有效的分数
                                    scores.append(score)
                            except Exception as e:
                                logger.debug(f"清晰度计算失败 {sample}: {str(e)}")
                    except Exception as e:
                        logger.debug(f"处理图像失败 {sample}: {str(e)}")
                        continue

            # 返回平均清晰度评分
            return float(sum(scores) / len(scores)) if scores else 0.0

        except Exception as e:
            logger.error(f"计算清晰度评分失败 {archive_path}: {str(e)}")
            return 0.0

    def analyze_archive(self, archive_path: str) -> Dict[str, Union[int, float]]:
        """分析压缩包，返回宽度、页数和清晰度信息"""
        result = {
            'width': 0,
            'page_count': 0,
            'clarity_score': 0.0
        }
        
        try:
            # 分别计算各项指标，失败一项不影响其他项
            try:
                result['page_count'] = self.get_image_count(archive_path)
            except Exception as e:
                logger.error(f"计算页数失败 {archive_path}: {str(e)}")
                
            try:
                result['width'] = self.calculate_representative_width(archive_path)
            except Exception as e:
                logger.error(f"计算宽度失败 {archive_path}: {str(e)}")
                
            try:
                result['clarity_score'] = self.calculate_clarity_score(archive_path)
            except Exception as e:
                logger.error(f"计算清晰度失败 {archive_path}: {str(e)}")
            
            return result
            
        except Exception as e:
            logger.error(f"分析压缩包失败 {archive_path}: {str(e)}")
            return result

    def format_analysis_result(self, result: Dict[str, Union[int, float]]) -> str:
        """格式化分析结果为字符串"""
        width = result['width']
        count = result['page_count']
        clarity = result['clarity_score']
        
        parts = []
        if width > 0:
            width_str = shorten_number_cn(width, use_w=True)
            parts.append(f"{width_str}@WD")
        if count > 0:
            count_str = shorten_number_cn(count, use_w=True)
            parts.append(f"{count_str}@PX")
        if clarity > 0:
            clarity_int = int(clarity)
            clarity_str = shorten_number_cn(clarity_int, use_w=True)
            parts.append(f"{clarity_str}@DE")
            
        return "{" + ",".join(parts) + "}" if parts else ""

    def process_file_with_count(self, file_path: str, base_dir: str = "") -> Tuple[str, str, Dict[str, Union[int, float]]]:
        """处理单个文件，返回原始路径、新路径和分析结果
        
        Args:
            file_path: 文件路径
            base_dir: 基础目录（可选）
            
        Returns:
            Tuple[str, str, Dict]: 原始路径、新路径和分析结果的元组
        """
        # 获取完整路径
        full_path = os.path.join(base_dir, file_path) if base_dir else file_path
        dir_name = os.path.dirname(full_path)
        file_name = os.path.basename(full_path)
        name, ext = os.path.splitext(file_name)
        
        # 移除已有的标记
        name = re.sub(r'\{[^}]*@(?:PX|WD|DE)[^}]*\}', '', name)
        
        # 分析文件
        result = self.analyze_archive(full_path)
        
        # 构建新文件名
        formatted = self.format_analysis_result(result)
        if formatted:
            name = f"{name}{formatted}"
            
        # 构建新的完整路径
        new_name = f"{name}{ext}"
        new_path = os.path.join(dir_name, new_name) if dir_name else new_name
        
        return full_path, new_path, result

    def process_directory_with_rename(self, input_path: str, do_rename: bool = False) -> List[Dict[str, Union[str, Dict[str, Union[int, float]]]]]:
        """处理目录下的所有文件，可选择是否重命名"""
        results = []
        pending_renames = []  # 存储待重命名的文件信息
        group_analyzer = GroupAnalyzer()  # 创建组分析器实例
        
        # 用于存储文件组
        file_groups = {}
        
        # 第一步：收集所有文件并进行初始分析
        if os.path.isfile(input_path):
            if input_path.lower().endswith(('.zip', '.cbz')):
                orig_path, new_path, analysis = self.process_file_with_count(input_path)
                result = {
                    'file': os.path.basename(input_path),
                    'orig_path': orig_path,
                    'analysis': analysis,
                    'formatted': self.format_analysis_result(analysis)
                }
                results.append(result)
                
        elif os.path.isdir(input_path):
            for root, _, files in os.walk(input_path):
                if 'trash' in root or 'multi' in root:
                    continue
                for file in files:
                    if file.lower().endswith(('.zip', '.cbz')):
                        file_path = os.path.join(root, file)
                        try:
                            orig_path, new_path, analysis = self.process_file_with_count(file_path)
                            result = {
                                'file': os.path.relpath(file_path, input_path),
                                'orig_path': orig_path,
                                'analysis': analysis,
                                'formatted': self.format_analysis_result(analysis)
                            }
                            results.append(result)
                            
                            # 将文件添加到对应的组
                            clean_name = group_analyzer.clean_filename(file)
                            if clean_name not in file_groups:
                                file_groups[clean_name] = []
                            file_groups[clean_name].append(result)
                            
                        except Exception as e:
                            logger.error(f"处理文件失败 {file_path}: {str(e)}")
        
        # 第二步：处理每个文件组，找出最优指标
        for group_name, group_results in file_groups.items():
            if len(group_results) > 1:  # 只处理有多个文件的组
                logger.info(f"📦 处理文件组: {group_name}")
                
                # 找出最优指标
                best_metrics = {
                    'width': 0,  # 最大宽度
                    'page_count': float('inf'),  # 最小页数
                    'clarity_score': 0.0  # 最高清晰度
                }
                
                # 检查是否所有指标都相同
                metrics_same = {
                    'width': True,
                    'page_count': True,
                    'clarity_score': True
                }
                
                # 收集所有指标值
                all_metrics = {
                    'width': set(),
                    'page_count': set(),
                    'clarity_score': set()
                }
                
                # 第一轮：收集所有值并找出最优值
                for result in group_results:
                    analysis = result['analysis']
                    # 收集所有值
                    if analysis['width'] > 0:
                        all_metrics['width'].add(analysis['width'])
                    if analysis['page_count'] > 0:
                        all_metrics['page_count'].add(analysis['page_count'])
                    if analysis['clarity_score'] > 0:
                        all_metrics['clarity_score'].add(analysis['clarity_score'])
                    
                    # 更新最优值
                    best_metrics['width'] = max(best_metrics['width'], analysis['width'])
                    best_metrics['page_count'] = min(best_metrics['page_count'], analysis['page_count'])
                    best_metrics['clarity_score'] = max(best_metrics['clarity_score'], analysis['clarity_score'])
                
                # 检查每个指标是否都相同
                metrics_same['width'] = len(all_metrics['width']) <= 1
                metrics_same['page_count'] = len(all_metrics['page_count']) <= 1
                metrics_same['clarity_score'] = len(all_metrics['clarity_score']) <= 1
                
                # 记录最优指标
                best_metrics_info = {
                    'width': best_metrics['width'],
                    'page_count': best_metrics['page_count'] if best_metrics['page_count'] != float('inf') else 0,
                    'clarity_score': best_metrics['clarity_score']
                }
                
                logger.info(f"🏆 组最优指标: 宽度={best_metrics_info['width']}, 页数={best_metrics_info['page_count']}, 清晰度={best_metrics_info['clarity_score']}")
                
                # 为每个文件更新格式化指标
                for result in group_results:
                    analysis = result['analysis']
                    parts = []
                    
                    # 添加宽度（如果不是统一值且是最优值则添加表情）
                    if analysis['width'] > 0:
                        width_str = f"{analysis['width']}@WD"
                        if not metrics_same['width'] and analysis['width'] == best_metrics['width']:
                            width_str = f"📏{width_str}"
                        parts.append(width_str)
                    
                    # 添加页数（如果不是统一值且是最优值则添加表情）
                    if analysis['page_count'] > 0:
                        page_str = f"{analysis['page_count']}@PX"
                        if not metrics_same['page_count'] and analysis['page_count'] == best_metrics['page_count']:
                            page_str = f"📄{page_str}"
                        parts.append(page_str)
                    
                    # 添加清晰度（如果不是统一值且是最优值则添加表情）
                    if analysis['clarity_score'] > 0:
                        clarity_str = f"{int(analysis['clarity_score'])}@DE"
                        if not metrics_same['clarity_score'] and analysis['clarity_score'] == best_metrics['clarity_score']:
                            clarity_str = f"🔍{clarity_str}"
                        parts.append(clarity_str)
                    
                    result['formatted'] = "{" + ",".join(parts) + "}" if parts else ""
        
        # 第三步：准备重命名操作
        for result in results:
            orig_path = result['orig_path']
            dir_name = os.path.dirname(orig_path)
            file_name = os.path.basename(orig_path)
            name, ext = os.path.splitext(file_name)
            
            # 移除已有的标记
            name = re.sub(r'\{[^}]*@(?:PX|WD|DE)[^}]*\}', '', name)
            
            # 添加新的格式化指标
            if result['formatted']:
                name = f"{name}{result['formatted']}"
            
            # 构建新的完整路径
            new_name = f"{name}{ext}"
            new_path = os.path.join(dir_name, new_name) if dir_name else new_name
            result['new_name'] = os.path.basename(new_path)
            
            if do_rename and orig_path != new_path:
                pending_renames.append((orig_path, new_path, result))
        
        # 第四步：执行重命名操作
        if do_rename and pending_renames:
            print("\n开始重命名文件...")
            for orig_path, new_path, result in pending_renames:
                try:
                    if os.path.exists(orig_path):
                        os.rename(orig_path, new_path)
                        result['renamed'] = True
                        print(f"重命名成功: {os.path.basename(orig_path)} -> {os.path.basename(new_path)}")
                    else:
                        logger.error(f"文件不存在: {orig_path}")
                        result['renamed'] = False
                except Exception as e:
                    logger.error(f"重命名失败 {orig_path}: {str(e)}")
                    result['renamed'] = False
                    print(f"重命名失败: {os.path.basename(orig_path)} ({str(e)})")
                    
        return results

def main():
    """主函数，用于命令行运行"""
    import json
    
    # 配置日志
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("=== Multi文件分析器 ===")
    print("请输入要分析的文件或目录路径（输入q退出）：")
    
    while True:
        try:
            input_path = input("路径> ").strip()
            
            if input_path.lower() in ('q', 'quit', 'exit'):
                print("程序已退出")
                break
                
            if not input_path:
                print("请输入有效路径")
                continue
                
            if not os.path.exists(input_path):
                print(f"错误：路径 '{input_path}' 不存在")
                continue
            
            # 获取样本数量
            sample_count = 3  # 默认值
            try:
                count_input = input("请输入采样数量（直接回车使用默认值3）> ").strip()
                if count_input:
                    sample_count = int(count_input)
                    if sample_count < 1:
                        print("采样数量必须大于0，使用默认值3")
                        sample_count = 3
            except ValueError:
                print("无效的采样数量，使用默认值3")
            
            # 是否执行重命名
            do_rename = input("是否重命名文件？(y/N) ").strip().lower() == 'y'
            
            # 是否保存到文件
            save_to_file = input("是否保存结果到文件？(y/N) ").strip().lower() == 'y'
            output_file = None
            if save_to_file:
                output_file = input("请输入保存路径（直接回车使用默认路径 analysis_result.json）> ").strip()
                if not output_file:
                    output_file = "analysis_result.json"
            
            # 执行分析
            print("\n开始分析...")
            analyzer = MultiAnalyzer(sample_count=sample_count)
            results = analyzer.process_directory_with_rename(input_path, do_rename)
            
            # 输出结果
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                print(f"\n结果已保存到: {output_file}")
            
            # 总是在控制台显示结果
            print("\n分析结果:")
            for result in results:
                print(f"原文件: {result['file']}")
                if do_rename:
                    status = "成功" if result.get('renamed', False) else "失败"
                    print(f"新文件: {result['new_name']} (重命名{status})")
                print(f"分析结果: {result['formatted']}")
                print("-" * 50)
            
            print("\n分析完成！")
            print("\n请输入新的路径进行分析（输入q退出）：")
            
        except Exception as e:
            logger.error(f"处理过程中出错: {str(e)}")
            print(f"错误: {str(e)}")
            print("\n请输入新的路径进行分析（输入q退出）：")

if __name__ == '__main__':
    main() 
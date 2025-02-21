from pathlib import Path
import sys
import os
import json
from PIL import Image
import numpy as np
from typing import Tuple, List, Dict, Optional
import logging
import requests
import base64
from io import BytesIO

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WatermarkDetector:
    """水印检测器类"""
    
    def __init__(self, api_url: str = "http://127.0.0.1:1224/api/ocr"):
        """
        初始化水印检测器
        
        Args:
            api_url: UmiOCR HTTP API地址，默认为本地1224端口
        """
        self.api_url = api_url
        self.watermark_keywords = [
            "汉化", "翻译", "扫描", "嵌字", "翻译", "组", "漢化",
            "扫图", "嵌字", "校对", "翻译", "润色"
        ]
        
    def detect_watermark(self, image_path: str) -> Tuple[bool, List[str]]:
        """
        检测图片中是否存在水印
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            Tuple[bool, List[str]]: (是否存在水印, 检测到的水印文字列表)
        """
        try:
            # 调用UmiOCR进行文字识别
            ocr_result = self._run_ocr(image_path)
            
            # 解析OCR结果
            detected_texts = self._parse_ocr_result(ocr_result)
            
            # 检查是否包含水印关键词
            watermark_texts = []
            for text in detected_texts:
                if any(keyword in text for keyword in self.watermark_keywords):
                    watermark_texts.append(text)
                    
            return bool(watermark_texts), watermark_texts
            
        except Exception as e:
            logger.error(f"检测水印时出错: {e}")
            return False, []
            
    def _run_ocr(self, image_path: str) -> str:
        """
        运行OCR识别
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            str: OCR识别结果的JSON字符串
        """
        try:
            # 读取图片并转换为base64
            with Image.open(image_path) as img:
                # 转换为RGB模式（如果是RGBA，去掉alpha通道）
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                    
                # 将图片转换为base64
                buffered = BytesIO()
                img.save(buffered, format="JPEG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode()
            
            # 准备请求数据
            data = {
                "base64": img_base64,
                "options": {
                    "language": "zh",  # 设置为中文
                    "model": "fast"    # 使用快速模式
                }
            }
            
            # 发送POST请求到UmiOCR
            response = requests.post(self.api_url, json=data)
            
            if response.status_code != 200:
                raise RuntimeError(f"UmiOCR API请求失败: {response.text}")
                
            return response.text
            
        except Exception as e:
            logger.error(f"运行OCR时出错: {e}")
            raise
            
    def _parse_ocr_result(self, ocr_output: str) -> List[str]:
        """
        解析OCR输出结果
        
        Args:
            ocr_output: OCR输出的JSON字符串
            
        Returns:
            List[str]: 识别出的文本列表
        """
        try:
            result = json.loads(ocr_output)
            texts = []
            
            # 解析UmiOCR的返回格式
            if isinstance(result, dict):
                if "code" in result and result["code"] == 100:
                    # 成功的情况
                    for item in result.get("data", []):
                        if isinstance(item, dict) and "text" in item:
                            texts.append(item["text"])
                else:
                    logger.error(f"OCR识别失败: {result.get('message', '未知错误')}")
            
            return texts
            
        except json.JSONDecodeError:
            logger.error("解析OCR结果失败")
            return []
            
    def compare_images(self, image1_path: str, image2_path: str) -> Dict:
        """
        比较两张图片的水印情况
        
        Args:
            image1_path: 第一张图片的路径
            image2_path: 第二张图片的路径
            
        Returns:
            Dict: 比较结果，包含两张图片的水印检测结果
        """
        result = {
            "image1": {
                "path": image1_path,
                "has_watermark": False,
                "watermark_texts": []
            },
            "image2": {
                "path": image2_path,
                "has_watermark": False,
                "watermark_texts": []
            },
            "comparison": {
                "different_watermark": False,
                "watermarked_version": None
            }
        }
        
        # 检测两张图片
        result["image1"]["has_watermark"], result["image1"]["watermark_texts"] = self.detect_watermark(image1_path)
        result["image2"]["has_watermark"], result["image2"]["watermark_texts"] = self.detect_watermark(image2_path)
        
        # 判断是否一张有水印一张没有
        if result["image1"]["has_watermark"] != result["image2"]["has_watermark"]:
            result["comparison"]["different_watermark"] = True
            result["comparison"]["watermarked_version"] = "image1" if result["image1"]["has_watermark"] else "image2"
            
        return result

def test_watermark_detector():
    """测试水印检测功能"""
    # 创建检测器实例
    detector = WatermarkDetector()
    
    # 测试图片路径
    test_image1 = "path/to/test/image1.jpg"  # 有水印的图片
    test_image2 = "path/to/test/image2.jpg"  # 无水印的图片
    
    # 确保测试图片存在
    if not (os.path.exists(test_image1) and os.path.exists(test_image2)):
        logger.error("测试图片不存在")
        return
        
    # 比较两张图片
    result = detector.compare_images(test_image1, test_image2)
    
    # 打印结果
    logger.info("水印检测结果:")
    logger.info(json.dumps(result, indent=2, ensure_ascii=False))

def run_demo():
    """运行演示程序，自动在测试文件夹下检测和比较图片"""
    logger.info("开始运行水印检测演示程序...")
    
    # 获取脚本所在目录
    script_dir = Path(__file__).parent
    test_dir = script_dir / "test_images"
    
    # 确保测试目录存在
    test_dir.mkdir(exist_ok=True)
    
    # 检查测试目录中的图片
    image_files = []
    for ext in ('.jpg', '.jpeg', '.png', '.webp'):
        image_files.extend(test_dir.glob(f"*{ext}"))
    
    if not image_files:
        logger.error(f"测试目录 {test_dir} 中没有找到图片文件")
        logger.info("请将测试图片放在以下目录中：")
        logger.info(str(test_dir))
        return
    
    # 创建检测器实例
    detector = WatermarkDetector()
    
    # 对所有图片进行两两比较
    total_comparisons = 0
    watermark_pairs = []
    
    logger.info(f"找到 {len(image_files)} 个图片文件，开始进行比较...")
    
    for i, img1 in enumerate(image_files):
        for j, img2 in enumerate(image_files[i+1:], i+1):
            total_comparisons += 1
            logger.info(f"\n比较第 {total_comparisons} 组：")
            logger.info(f"图片1: {img1.name}")
            logger.info(f"图片2: {img2.name}")
            
            # 比较两张图片
            result = detector.compare_images(str(img1), str(img2))
            
            # 如果发现一张有水印一张没有的情况
            if result["comparison"]["different_watermark"]:
                watermark_pairs.append({
                    "watermarked": result["image1"] if result["comparison"]["watermarked_version"] == "image1" else result["image2"],
                    "clean": result["image2"] if result["comparison"]["watermarked_version"] == "image1" else result["image1"]
                })
                logger.info("✅ 发现水印差异！")
                logger.info(f"有水印版本: {watermark_pairs[-1]['watermarked']['path']}")
                logger.info(f"无水印版本: {watermark_pairs[-1]['clean']['path']}")
                logger.info(f"检测到的水印文字: {watermark_pairs[-1]['watermarked']['watermark_texts']}")
            else:
                logger.info("❌ 未发现水印差异")
    
    # 输出总结报告
    logger.info("\n=== 检测报告 ===")
    logger.info(f"总共比较了 {total_comparisons} 组图片")
    logger.info(f"发现 {len(watermark_pairs)} 组有水印差异的图片")
    
    if watermark_pairs:
        logger.info("\n详细结果:")
        for i, pair in enumerate(watermark_pairs, 1):
            logger.info(f"\n第 {i} 组:")
            logger.info(f"有水印文件: {Path(pair['watermarked']['path']).name}")
            logger.info(f"无水印文件: {Path(pair['clean']['path']).name}")
            logger.info(f"水印文字: {', '.join(pair['watermarked']['watermark_texts'])}")

if __name__ == "__main__":
    # test_watermark_detector()  # 注释掉原来的测试函数
    run_demo()  # 运行新的演示程序 
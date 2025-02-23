"""
对比新旧感知哈希算法的差异
"""

import os
import time
from pathlib import Path
from PIL import Image, ImageEnhance
import imagehash
import cv2
import numpy as np
from rich.console import Console
from rich.table import Table
from concurrent.futures import ThreadPoolExecutor
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HashCompare:
    def __init__(self, hash_size=10):
        self.hash_size = hash_size
        self.console = Console()

    def old_phash(self, image_path):
        """使用imagehash库的原始实现"""
        try:
            start_time = time.time()
            img = Image.open(image_path)
            hash_obj = imagehash.phash(img, hash_size=self.hash_size)
            hash_str = str(hash_obj)
            duration = time.time() - start_time
            return hash_str, duration
        except Exception as e:
            logger.error(f"旧算法计算失败: {e}")
            return None, 0

    def new_phash(self, image_path):
        """使用与imagehash库完全一致的pHash实现
        
        步骤：
        1. 将图像缩放为 hash_size*8 的灰度图
        2. 对图像进行DCT变换
        3. 取DCT的左上角hash_size*hash_size的低频部分
        4. 计算这些DCT系数的中值(不包括第一个直流分量)
        5. 将DCT系数与中值进行比较得到二进制哈希值
        """
        try:
            start_time = time.time()
            
            # 1. 图片预处理 - 缩放为hash_size*8并转换为灰度图
            img_size = self.hash_size * 8
            img = Image.open(image_path).convert('L').resize(
                (img_size, img_size), Image.Resampling.LANCZOS
            )
            
            # 2. 转换为NumPy数组并进行DCT变换
            pixels = np.asarray(img, dtype=np.float64)
            dct = cv2.dct(pixels)
            
            # 3. 取DCT的左上角hash_size*hash_size的低频部分
            dct_low = dct[:self.hash_size, :self.hash_size]
            
            # 4. 计算中值 (不包括第一个直流分量)
            # 注意：imagehash使用中值而不是均值
            dct_flat = dct_low[1:].flatten()  # 排除直流分量
            med = np.median(dct_flat)
            
            # 5. 生成哈希值
            # 将大于中值的设为1，小于等于中值的设为0
            hash_bits = (dct_low > med)
            
            # 6. 转换为十六进制字符串
            hash_int = 0
            for bit in hash_bits.flatten():
                hash_int = (hash_int << 1) | int(bit)
            
            # 生成与hash_size对应的十六进制字符串
            bits_length = self.hash_size * self.hash_size
            hex_length = (bits_length + 3) // 4
            hex_str = format(hash_int, f'0{hex_length}x')
            
            duration = time.time() - start_time
            return hex_str, duration
        except Exception as e:
            logger.error(f"新算法计算失败: {e}")
            return None, 0

    def calculate_hamming_distance(self, hash1, hash2):
        """计算两个哈希值的汉明距离"""
        try:
            # 使用实际的哈希位数
            bits_length = self.hash_size * self.hash_size
            bin1 = bin(int(hash1, 16))[2:].zfill(bits_length)
            bin2 = bin(int(hash2, 16))[2:].zfill(bits_length)
            return sum(b1 != b2 for b1, b2 in zip(bin1, bin2))
        except Exception as e:
            logger.error(f"计算汉明距离失败: {e}")
            return -1

    def compare_similar_images(self, image_paths):
        """比较相似图片的哈希值差异"""
        table = Table(title="相似图片哈希值对比")
        table.add_column("图片", style="cyan")
        table.add_column("旧算法哈希", style="magenta")
        table.add_column("新算法哈希", style="green")
        table.add_column("汉明距离", style="yellow")
        table.add_column("旧算法耗时(ms)", style="blue")
        table.add_column("新算法耗时(ms)", style="blue")
        
        for path in image_paths:
            if not os.path.exists(path):
                continue
                
            old_hash, old_time = self.old_phash(path)
            new_hash, new_time = self.new_phash(path)
            
            if old_hash and new_hash:
                distance = self.calculate_hamming_distance(old_hash, new_hash)
                table.add_row(
                    os.path.basename(path),
                    old_hash,
                    new_hash,
                    str(distance),
                    f"{old_time*1000:.2f}",
                    f"{new_time*1000:.2f}"
                )
        
        self.console.print(table)

    def batch_process_test(self, image_dir, batch_size=100):
        """批量处理性能测试"""
        image_files = []
        for ext in ('*.jpg', '*.jpeg', '*.png', '*.webp'):
            image_files.extend(Path(image_dir).glob(f"**/{ext}"))
        image_files = image_files[:batch_size]
        
        if not image_files:
            self.console.print("[red]未找到图片文件[/]")
            return
            
        self.console.print(f"\n[bold cyan]=== 批量处理性能测试 ({len(image_files)}张图片) ===[/]")
        
        # 测试旧算法
        start_time = time.time()
        with ThreadPoolExecutor() as executor:
            old_results = list(executor.map(self.old_phash, image_files))
        old_time = time.time() - start_time
        
        # 测试新算法
        start_time = time.time()
        with ThreadPoolExecutor() as executor:
            new_results = list(executor.map(self.new_phash, image_files))
        new_time = time.time() - start_time
        
        # 统计结果
        total_distance = 0
        valid_count = 0
        for (old_hash, _), (new_hash, _) in zip(old_results, new_results):
            if old_hash and new_hash:
                distance = self.calculate_hamming_distance(old_hash, new_hash)
                if distance >= 0:
                    total_distance += distance
                    valid_count += 1
        
        avg_distance = total_distance / valid_count if valid_count > 0 else -1
        
        # 打印结果
        table = Table(title="批量处理性能对比")
        table.add_column("指标", style="cyan")
        table.add_column("旧算法", style="magenta")
        table.add_column("新算法", style="green")
        
        table.add_row(
            "总处理时间(秒)",
            f"{old_time:.2f}",
            f"{new_time:.2f}"
        )
        table.add_row(
            "平均每张耗时(ms)",
            f"{(old_time/len(image_files))*1000:.2f}",
            f"{(new_time/len(image_files))*1000:.2f}"
        )
        table.add_row(
            "平均汉明距离",
            f"{avg_distance:.2f}",
            "-"
        )
        
        self.console.print(table)

def main():
    # 测试文件路径
    test_files = [
        r"D:\1VSCODE\1ehv\pics\test\0.jpg",  # 替换为实际的测试图片路径
        r"D:\1VSCODE\1ehv\pics\test\1.jpg",
        r"D:\1VSCODE\1ehv\pics\test\2.jpg"
    ]
    
    # 批量测试目录
    test_dir = r"D:\1VSCODE\1ehv\pics\test"  # 替换为实际的测试目录
    
    # 创建比较器实例
    hash_compare = HashCompare(hash_size=10)
    
    # 运行单图片对比测试
    hash_compare.console.print("\n[bold cyan]=== 单图片哈希值对比 ===[/]")
    hash_compare.compare_similar_images(test_files)
    
    # 运行批量处理测试
    hash_compare.batch_process_test(test_dir, batch_size=100)

if __name__ == "__main__":
    main() 
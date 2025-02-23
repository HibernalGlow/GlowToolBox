import os
import time
import imagehash
from PIL import Image
from pathlib import Path
import argparse
import pillow_jxl
import pillow_avif
from wand.image import Image as WandImage

vipshome = Path(r'D:\1VSCODE\1ehv\other\vips\bin')
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(str(vipshome))
os.environ['PATH'] = str(vipshome) + ';' + os.environ['PATH']
import pyvips
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from rich.progress import Progress
import numpy as np

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def calculate_dct_hash(img_data):
    """优化的DCT哈希计算方法"""
    # 确保输入是灰度图数据
    if len(img_data.shape) > 2:
        raise ValueError("Input must be grayscale image")
        
    # 确保输入尺寸为256x256
    if img_data.shape != (256, 256):
        raise ValueError("Input must be 256x256")
    
    # 使用float32而不是float64，提高性能
    float_data = img_data.astype(np.float32)
    
    # 使用快速傅里叶变换计算DCT
    dct = np.fft.fft2(float_data)
    dct_low = np.abs(dct[:32, :32])  # 使用32x32的低频区域
    
    # 使用快速的numpy操作计算中值和比较
    med = np.median(dct_low)
    hash_bits = (dct_low.ravel() > med)
    
    # 使用更快的方法生成二进制字符串
    hash_str = np.packbits(hash_bits).tobytes().hex()
    return format(int(hash_str, 16), '0256b')[:64]  # 保持64位输出兼容性

def calculate_hash_pil(image_path):
    """使用PIL计算图片哈希"""
    try:
        start_time = time.time()
        with Image.open(image_path) as img:
            # 转换为灰度图
            img = img.convert('L')
            # 调整大小到256x256，使用BICUBIC以保持更好的图像质量
            img = img.resize((256, 256), Image.Resampling.BICUBIC)
            # 转换为numpy数组并优化数据类型
            img_data = np.asarray(img, dtype=np.uint8)
            # 计算哈希
            hash_str = calculate_dct_hash(img_data)
        
        end_time = time.time()
        return hash_str, end_time - start_time
    except Exception as e:
        logger.error(f"PIL处理失败 {image_path}: {e}")
        return None, 0

def calculate_hash_vips(image_path):
    """使用pyvips计算图片哈希"""
    try:
        start_time = time.time()
        
        # 加载图片并预处理
        image = pyvips.Image.new_from_file(image_path)
        
        # 转换为灰度图
        if image.bands > 1:
            image = image.colourspace('b-w')
            
        # 调整大小到256x256，使用BICUBIC插值
        image = image.thumbnail_image(256, height=256, size=pyvips.Size.FORCE)
        
        # 获取图像数据并优化
        img_data = np.frombuffer(image.write_to_memory(), dtype=np.uint8).reshape(256, 256)
        
        # 计算哈希
        hash_str = calculate_dct_hash(img_data)
        
        end_time = time.time()
        return hash_str, end_time - start_time
        
    except Exception as e:
        logger.error(f"Vips处理失败 {image_path}: {e}")
        return None, 0

def calculate_hash_magick(image_path):
    """使用ImageMagick计算图片哈希"""
    try:
        start_time = time.time()
        
        with WandImage(filename=image_path) as img:
            # 转换为灰度图
            img.type = 'grayscale'
            # 调整大小到256x256
            img.resize(256, 256, 'lanczos')  # 使用Lanczos算法进行缩放
            # 获取图像数据并优化
            img_data = np.array(img.export_pixels(channel_map='I'), dtype=np.uint8).reshape(256, 256)
            # 计算哈希
            hash_str = calculate_dct_hash(img_data)
        
        end_time = time.time()
        return hash_str, end_time - start_time
        
    except Exception as e:
        logger.error(f"ImageMagick处理失败 {image_path}: {e}")
        return None, 0

def compare_hashes(hash1, hash2, max_diff=2):
    """比较两个哈希值的汉明距离"""
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return False
    diff = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
    logger.debug(f"Hash difference: {diff} bits")
    return diff <= max_diff

def test_performance(image_paths, num_threads=4):
    """测试性能"""
    pil_results = []
    vips_results = []
    magick_results = []
    successful_tests = 0
    failed_tests = 0
    
    with Progress() as progress:
        task = progress.add_task("测试进度", total=len(image_paths) * 3)  # 3种方法
        
        # 测试PIL
        logger.info("开始PIL测试...")
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for img_path in image_paths:
                futures.append(executor.submit(calculate_hash_pil, img_path))
            
            for future, img_path in zip(as_completed(futures), image_paths):
                hash_value, process_time = future.result()
                if hash_value is not None:
                    pil_results.append((hash_value, process_time, img_path))
                    successful_tests += 1
                else:
                    failed_tests += 1
                progress.advance(task)
                
        # 测试Vips
        logger.info("开始Vips测试...")
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for img_path in image_paths:
                futures.append(executor.submit(calculate_hash_vips, img_path))
            
            for future, img_path in zip(as_completed(futures), image_paths):
                hash_value, process_time = future.result()
                if hash_value is not None:
                    vips_results.append((hash_value, process_time, img_path))
                progress.advance(task)
                
        # 测试ImageMagick
        logger.info("开始ImageMagick测试...")
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for img_path in image_paths:
                futures.append(executor.submit(calculate_hash_magick, img_path))
            
            for future, img_path in zip(as_completed(futures), image_paths):
                hash_value, process_time = future.result()
                if hash_value is not None:
                    magick_results.append((hash_value, process_time, img_path))
                progress.advance(task)
    
    # 计算统计数据
    pil_times = [t for _, t, _ in pil_results]
    vips_times = [t for _, t, _ in vips_results]
    magick_times = [t for _, t, _ in magick_results]
    
    # 验证哈希值一致性
    print("\n哈希值一致性检查:")
    
    # PIL vs VIPS
    pil_vips_matches = 0
    if len(pil_results) == len(vips_results):
        for (pil_hash, _, img_path), (vips_hash, _, _) in zip(pil_results, vips_results):
            if compare_hashes(pil_hash, vips_hash):
                pil_vips_matches += 1
            else:
                logger.debug(f"PIL vs VIPS mismatch for {img_path}:")
                logger.debug(f"PIL hash:  {pil_hash}")
                logger.debug(f"VIPS hash: {vips_hash}")
    
    # PIL vs ImageMagick
    pil_magick_matches = 0
    if len(pil_results) == len(magick_results):
        for (pil_hash, _, img_path), (magick_hash, _, _) in zip(pil_results, magick_results):
            if compare_hashes(pil_hash, magick_hash):
                pil_magick_matches += 1
            else:
                logger.debug(f"PIL vs ImageMagick mismatch for {img_path}:")
                logger.debug(f"PIL hash:    {pil_hash}")
                logger.debug(f"Magick hash: {magick_hash}")
    
    # 输出结果
    print("\n性能测试结果:")
    print(f"成功测试: {successful_tests} 张图片")
    print(f"失败测试: {failed_tests} 张图片")
    
    if pil_results:
        total = len(pil_results)
        print(f"\n哈希值匹配率:")
        print(f"PIL vs VIPS:      {pil_vips_matches}/{total} ({pil_vips_matches/total*100:.1f}%)")
        print(f"PIL vs ImageMagick: {pil_magick_matches}/{total} ({pil_magick_matches/total*100:.1f}%)")
    
    if pil_times:
        print("\nPIL性能:")
        print(f"  平均时间: {sum(pil_times)/len(pil_times):.4f} 秒")
        print(f"  最小时间: {min(pil_times):.4f} 秒")
        print(f"  最大时间: {max(pil_times):.4f} 秒")
        
    if vips_times:
        print("\nVips性能:")
        print(f"  平均时间: {sum(vips_times)/len(vips_times):.4f} 秒")
        print(f"  最小时间: {min(vips_times):.4f} 秒")
        print(f"  最大时间: {max(vips_times):.4f} 秒")
        
    if magick_times:
        print("\nImageMagick性能:")
        print(f"  平均时间: {sum(magick_times)/len(magick_times):.4f} 秒")
        print(f"  最小时间: {min(magick_times):.4f} 秒")
        print(f"  最大时间: {max(magick_times):.4f} 秒")
        
    # 计算性能提升
    if pil_times:
        pil_avg = sum(pil_times)/len(pil_times)
        if vips_times:
            vips_avg = sum(vips_times)/len(vips_times)
            print(f"\nVips相对PIL的速度提升: {pil_avg/vips_avg:.2f}x")
        if magick_times:
            magick_avg = sum(magick_times)/len(magick_times)
            print(f"ImageMagick相对PIL的速度提升: {pil_avg/magick_avg:.2f}x")

def collect_test_images(directory, max_images=100):
    """收集测试用的图片"""
    image_paths = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.jxl', '.avif', '.bmp')):
                image_paths.append(os.path.join(root, file))
                if len(image_paths) >= max_images:
                    return image_paths
    return image_paths

def main():
    # 添加命令行参数解析
    parser = argparse.ArgumentParser(description="图片哈希性能测试工具")
    parser.add_argument('-d', '--dir', help='测试图片目录路径')
    parser.add_argument('-n', '--num', type=int, default=100, help='测试图片数量 (默认: 100)')
    parser.add_argument('-t', '--threads', type=int, default=4, help='线程数 (默认: 4)')
    args = parser.parse_args()

    print("图片哈希性能测试工具")
    print("===================")
    
    # 获取测试目录
    test_dir = args.dir
    while not test_dir or not os.path.isdir(test_dir):
        test_dir = input("\n请输入包含测试图片的目录路径: ").strip().strip('"')
        if not os.path.isdir(test_dir):
            print("无效的目录路径，请重试")
    
    # 使用命令行参数或默认值
    max_images = args.num
    num_threads = args.threads
    
    # 收集测试图片
    print(f"\n正在收集测试图片...")
    image_paths = collect_test_images(test_dir, max_images)
    
    if not image_paths:
        print("未找到可用的测试图片")
        return
        
    print(f"找到 {len(image_paths)} 张测试图片")
    print(f"使用 {num_threads} 个线程进行测试")
    
    # 运行测试
    print("\n开始性能测试...")
    test_performance(image_paths, num_threads)

if __name__ == "__main__":
    main() 
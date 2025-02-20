import os
from PIL import Image
import numpy as np
import pillow_avif
import pillow_jxl
from tqdm import tqdm
import warnings
from PIL import Image, ImageFile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import zipfile  # 添加新的导入
from io import BytesIO
import logging
import shutil  # 添加用于移动文件

# 修改日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dark_images_detection.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
# 关闭解压炸弹警告
warnings.filterwarnings('ignore', category=Image.DecompressionBombWarning)
# 允许处理截断的图片
ImageFile.LOAD_TRUNCATED_IMAGES = True

# 创建线程锁用于同步输出
print_lock = threading.Lock()
processed_folders = set()
results = []

def is_abnormal_dark(image_path, threshold=0.5, thumbnail_size=(200, 200), image_data=None, archive_info=None, pbar=None):
    """
    检查图片是否为异常黑图（使用缩略图加快计算）
    :param image_path: 图片路径
    :param threshold: 纯黑像素占比阈值，默认0.5
    :param thumbnail_size: 缩略图大小
    :param image_data: 图片数据（用于处理压缩包内的图片）
    :param archive_info: 压缩包信息（用于处理压缩包内的图片）
    :param pbar: 进度条对象
    :return: 是否异常黑图
    """
    try:
        # 使用\r在同一行更新信息
        if archive_info and pbar:
            pbar.set_description(f"正在处理: {archive_info}")
        elif image_path and pbar:
            pbar.set_description(f"正在处理: {image_path}")
        
        # 根据输入类型打开图片
        if image_data:
            img = Image.open(image_data)
        else:
            img = Image.open(image_path)
            
        # 创建缩略图
        img.thumbnail(thumbnail_size)
        # 转换为灰度图
        img = img.convert('L')
        # 转换为numpy数组
        img_array = np.array(img)
        
        # 计算纯黑像素比例
        black_pixels = np.sum(img_array == 0)
        total_pixels = img_array.size
        black_ratio = black_pixels / total_pixels
        
        # 如果不是全黑但纯黑像素比例超过阈值，则判定为异常
        return 0.95 > black_ratio >= threshold
        
    except Exception as e:
        with print_lock:
            print(f"处理图片 {image_path} 时出错: {str(e)}")
        return False

def process_folder(args):
    """
    处理单个文件夹中的图片
    """
    global results
    dirpath, filenames, root_path, image_extensions, pbar = args
    dark_images = []
    
    for filename in filenames:
        if os.path.splitext(filename)[1].lower() in image_extensions:
            full_path = os.path.join(dirpath, filename)
            if is_abnormal_dark(full_path, pbar=pbar):
                dark_images.append(filename)
            pbar.update(1)
    
    # 如果发现异常图片，输出结果
    if dark_images and dirpath not in processed_folders:
        with print_lock:
            if dirpath not in processed_folders:
                processed_folders.add(dirpath)
                rel_path = os.path.relpath(dirpath, root_path)
                
                # 保存结果
                result_text = f"\n## {rel_path}\n\n"
                result_text += "异常图片：\n"
                for img in dark_images:
                    result_text += f"- {img}\n"
                results.append(result_text)
                
                # 控制台输出
                pbar.clear()
                print(f"\n发现异常文件夹: {rel_path}")
                print("包含以下异常图片：")
                for img in dark_images:
                    print(f"- {img}")
                print("-" * 50)
                pbar.refresh()

def find_dark_images(root_path, check_path, max_workers=None):
    """
    查找目录下的异常黑图
    :param root_path: 根目录路径
    :param check_path: 异常文件移动目标路径
    :param max_workers: 最大线程数，默认为None（由系统决定）
    """
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.avif', '.jxl'}
    archive_extensions = {'.zip', '.cbz'}  # 添加压缩包扩展名
    results = []
    
    folders_to_process = []
    archives_to_process = []  # 新增：收集需要处理的压缩包
    total_files = 0
    
    # 收集所有需要处理的文件夹和压缩包
    for dirpath, dirnames, filenames in os.walk(root_path):
        # 处理普通图片文件
        image_files = [f for f in filenames if os.path.splitext(f)[1].lower() in image_extensions]
        if image_files:
            folders_to_process.append((dirpath, image_files))
            total_files += len(image_files)
            
        # 处理压缩包文件
        archive_files = [f for f in filenames if os.path.splitext(f)[1].lower() in archive_extensions]
        if archive_files:
            archives_to_process.extend((dirpath, f) for f in archive_files)
            total_files += len(archive_files)  # 暂时将每个压缩包计为1个文件
    
    # 创建进度条
    pbar = tqdm(total=total_files, desc="检查图片中", dynamic_ncols=True)
    
    # 创建Markdown文件头部
    with open("异常黑图检测结果.md", "w", encoding="utf-8") as f:
        f.write("# 异常黑图检测结果\n\n")
        f.write(f"检测时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"检测路径：{root_path}\n\n")
    
    # 处理普通文件夹
    thread_args = [(dirpath, filenames, root_path, image_extensions, pbar) 
                  for dirpath, filenames in folders_to_process]
    
    # 使用线程池处理文件夹
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(process_folder, thread_args)
        
        # 处理压缩包
        for dirpath, archive_file in archives_to_process:
            process_archive(dirpath, archive_file, root_path, image_extensions, pbar, check_path)
    
    pbar.close()
    
    # 写入Markdown文件
    if results:
        output_path = os.path.join(os.path.dirname(root_path), "异常黑图检测结果.md")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# 异常黑图检测结果\n\n")
            f.write(f"检测时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"检测路径：{root_path}\n\n")
            
            def write_result(result_text):
                with open(output_path, 'a', encoding='utf-8') as f:
                    f.write(result_text)
                    f.flush()  # 确保立即写入磁盘
            
            # 在发现异常时立即写入
            if dark_images:
                result_text = f"\n## {rel_path}\n\n"
                result_text += "异常图片：\n"
                for img in dark_images:
                    result_text += f"- {img}\n"
                write_result(result_text)
        print(f"\n结果已保存至：{output_path}")

def process_images_in_directory(temp_dir, params):
    """处理目录中的图片"""
    try:
        # 获取所有图片文件
        image_files = get_image_files(temp_dir)
        if not image_files:
            logger.warning(f"未找到图片文件")
            return set()
            
        logger.info(f"找到 {len(image_files)} 个图片文件")
        
        # 处理图片
        dark_images = []
        processed_files = set()
        
        for img_data, file_name in image_files:
            try:
                # 检查是否为异常黑图
                if is_abnormal_dark(None, image_data=BytesIO(img_data)):
                    dark_images.append(file_name)
                    processed_files.add(os.path.join(temp_dir, file_name))
                    logger.debug(f"发现异常黑图: {file_name}")
            except Exception as e:
                logger.error(f"处理图片出错 {file_name}: {e}")
                continue
        
        # 如果发现异常黑图，记录到日志
        if dark_images:
            logger.info(f"发现 {len(dark_images)} 张异常黑图")
            for img in dark_images:
                logger.info(f"- {img}")
        
        return processed_files
        
    except Exception as e:
        logger.error(f"处理目录中的图片时出错: {e}")
        return set()
def get_image_files(directory):
    """获取目录中的所有图片文件"""
    image_files = []
    valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.avif', '.jxl'}
    
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in valid_extensions):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'rb') as f:
                        image_data = f.read()
                    image_files.append((image_data, file))
                except Exception as e:
                    logger.error(f"读取图片文件失败 {file_path}: {e}")
    
    return image_files

def process_archive(dirpath, archive_file, root_path, image_extensions, pbar, check_path):
    """处理压缩包内的图片"""
    try:
        archive_path = os.path.join(dirpath, archive_file)
        rel_path = os.path.relpath(archive_path, root_path)
        logger.info(f"开始处理压缩包: {rel_path}")
        
        dark_images = []
        with zipfile.ZipFile(archive_path, 'r') as zf:
            for file_info in zf.infolist():
                if any(file_info.filename.lower().endswith(ext) for ext in image_extensions):
                    try:
                        with zf.open(file_info) as image_file:
                            archive_info = f"{rel_path} -> {file_info.filename}"
                            if is_abnormal_dark(None, image_data=BytesIO(image_file.read()), 
                                             archive_info=archive_info, pbar=pbar):
                                dark_images.append(file_info.filename)
                                logger.info(f"在压缩包中发现异常图片: {archive_path} -> {file_info.filename}")
                    except Exception as e:
                        logger.error(f"处理压缩包内图片失败 {archive_path} -> {file_info.filename}: {str(e)}")
            
            # 如果发现异常图片，添加到结果中
            if dark_images:
                with print_lock:
                    result_text = f"\n## {archive_path}\n\n"
                    result_text += "异常图片：\n"
                    for img in dark_images:
                        result_text += f"- {img}\n"
                    results.append(result_text)
                    
                    # 如果黑图数量超过5张，移动压缩包
                    if len(dark_images) >= 4:
                        # 创建目标目录
                        rel_dir = os.path.relpath(dirpath, root_path)
                        target_dir = os.path.join(check_path, rel_dir)
                        os.makedirs(target_dir, exist_ok=True)
                        
                        # 移动文件
                        target_path = os.path.join(target_dir, archive_file)
                        shutil.move(archive_path, target_path)
                        logger.warning(f"发现超过5张黑图的压缩包，已移动到: {target_path}")
                        
                    # 实时写入Markdown文件
                    with open("异常黑图检测结果.md", "a", encoding="utf-8") as f:
                        f.write(result_text)
                        f.flush()
                    
    except Exception as e:
        logger.error(f"处理压缩包失败 {archive_file}: {str(e)}")

if __name__ == "__main__":
    target_path = r"D:\8EHV"
    check_path = r"E:\7EHV_CHECK"  # 添加检查路径
    print(f"开始检查目录: {target_path}")
    max_workers = os.cpu_count() * 2
    find_dark_images(target_path, check_path, max_workers)
    print("\n检查完成！")

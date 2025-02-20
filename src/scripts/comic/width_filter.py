import os
import logging
from pathlib import Path
from PIL import Image, ImageFile
import shutil
from tqdm import tqdm
import pillow_avif
import pillow_jxl
import zipfile
import io
from concurrent.futures import ThreadPoolExecutor
import sys
import warnings
import subprocess
from dotenv import load_dotenv

# 基础设置
warnings.filterwarnings('ignore', category=Image.DecompressionBombWarning)
Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True

# 加载环境变量并初始化日志记录器
load_dotenv()
from nodes.record.logger_config import setup_logger

# 创建全局日志记录器
logger, _ = setup_logger({
    'script_name': '012-低于指定宽度',
})

class ImageProcessor:
    def __init__(self, source_dir, target_dir, min_width=1800, cut_mode=False, max_workers=16, 
                 compare_larger=False, threshold_count=1):
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.min_width = min_width
        self.cut_mode = cut_mode
        self.max_workers = max_workers
        self.compare_larger = compare_larger
        self.threshold_count = threshold_count
        self.logger = logger  # 使用全局logger
        
        # 添加排除关键词列表
        self.exclude_paths = [
            '画集', '日原版', 'pixiv', '图集', '作品集', 'FANTIA', 'cg', 'multi', 'trash'
        ]
        # 将所有排除路径转换为小写，并确保是独立的词
        self.exclude_paths = [path.lower().strip() for path in self.exclude_paths]
        # 添加需要排除的文件格式
        self.exclude_formats = {'.avif', '.jxl', '.gif', '.mp4', '.webm', '.mkv', '.avi', '.mov'}
        # 添加7z路径
        self.seven_zip_path = r"C:\Program Files\7-Zip\7z.exe"

    def should_exclude_path(self, path_str):
        """检查路径是否应该被排除"""
        path_str = path_str.lower()
        path_parts = path_str.replace('\\', '/').split('/')
        
        # 检查路径的每一部分
        for part in path_parts:
            # 移除常见的分隔符
            clean_part = part.replace('-', ' ').replace('_', ' ').replace('.', ' ')
            words = set(clean_part.split())
            
            # 检查每个排除关键词
            for keyword in self.exclude_paths:
                # 如果关键词作为独立的词出现
                if keyword in words:
                    self.logger.info(f"排除文件 {path_str} 因为包含关键词: {keyword}")
                    return True
                # 或者作为路径的一部分完整出现
                if keyword in part:
                    self.logger.info(f"排除文件 {path_str} 因为包含关键词: {keyword}")
                    return True
        return False

    def get_image_width_from_zip(self, zip_file, image_path):
        try:
            with zip_file.open(image_path) as file:
                img_data = io.BytesIO(file.read())
                with Image.open(img_data) as img:
                    return img.size[0]
        except Exception as e:
            self.logger.error(f"读取图片出错 {image_path}: {str(e)}")
            return 0

    def get_zip_images_info(self, zip_path):
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                image_files = [f for f in zf.namelist() if f.lower().endswith(
                    ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.avif', '.jxl'))]
                
                if not image_files:
                    self.logger.warning(f"ZIP文件 {zip_path} 中没有找到图片")
                    return 0, 0
                
                # 改进的抽样算法
                image_files.sort()  # 确保文件顺序一致
                total_images = len(image_files)
                
                # 计算抽样间隔
                sample_size = min(20, total_images)  # 最多抽样20张图片
                if total_images <= sample_size:
                    sampled_files = image_files  # 如果图片数量较少，使用所有图片
                else:
                    # 确保抽样包含：
                    # 1. 开头的几张图片
                    # 2. 结尾的几张图片
                    # 3. 均匀分布的中间图片
                    head_count = min(3, total_images)  # 开头取3张
                    tail_count = min(3, total_images)  # 结尾取3张
                    middle_count = sample_size - head_count - tail_count  # 中间的图片数量
                    
                    # 获取头部图片
                    head_files = image_files[:head_count]
                    # 获取尾部图片
                    tail_files = image_files[-tail_count:]
                    # 获取中间的图片
                    if middle_count > 0:
                        step = (total_images - head_count - tail_count) // (middle_count + 1)
                        middle_indices = range(head_count, total_images - tail_count, step)
                        middle_files = [image_files[i] for i in middle_indices[:middle_count]]
                    else:
                        middle_files = []
                    
                    sampled_files = head_files + middle_files + tail_files
                    self.logger.debug(f"抽样数量: {len(sampled_files)}/{total_images} (头部:{len(head_files)}, 中间:{len(middle_files)}, 尾部:{len(tail_files)})")

                match_count = 0
                large_image_count = 0
                min_width = float('inf')
                
                for img in sampled_files:
                    width = self.get_image_width_from_zip(zf, img)
                    if width > 0:
                        min_width = min(min_width, width)
                        
                        # 检查是否大于1800
                        if width >= 1800:
                            large_image_count += 1
                            if large_image_count > 3:  # 如果超过3张图片宽度大于1800，提前返回
                                self.logger.info(f"ZIP文件 {zip_path} 超过3张图片宽度大于1800px")
                                return min_width if min_width != float('inf') else 0, 0
                        
                        matches_condition = (self.compare_larger and width >= self.min_width) or \
                                         (not self.compare_larger and width < self.min_width)
                        if matches_condition:
                            match_count += 1
                            self.logger.debug(f"图片 {img} 符合条件: {width}px")
                        
                        # 如果已经达到阈值，可以提前返回
                        if match_count >= self.threshold_count:
                            self.logger.info(f"ZIP文件 {zip_path} 已达到阈值 ({match_count}/{self.threshold_count})")
                            return min_width if min_width != float('inf') else 0, match_count

                final_width = min_width if min_width != float('inf') else 0
                self.logger.info(f"ZIP文件 {zip_path} - 最小宽度: {final_width}px, 符合条件数量: {match_count}/{self.threshold_count}, "
                               f"大于1800px的图片数量: {large_image_count}, 总图片: {total_images}, 抽样: {len(sampled_files)}")
                return final_width, match_count
                
        except Exception as e:
            self.logger.error(f"处理ZIP文件出错 {zip_path}: {str(e)}")
            return 0, 0

    def should_process_zip(self, width, match_count, zip_path):
        if width == 0:
            self.logger.warning(f"跳过处理 {zip_path}: 无效的宽度")
            return False
        
        should_process = match_count >= self.threshold_count
        
        self.logger.info(f"文件 {zip_path} - 宽度: {width}px, 符合条件数量: {match_count}/{self.threshold_count}, "
                        f"{'大于等于' if self.compare_larger else '小于'}模式, "
                        f"结果: {'处理' if should_process else '跳过'}")
        return should_process

    def process_single_zip(self, zip_path):
        """处理单个压缩包，返回是否需要处理"""
        try:
            # 1. 首先检查是否包含排除格式
            if self.has_excluded_formats(zip_path):
                self.logger.info(f"跳过包含排除格式的文件: {zip_path}")
                return zip_path, False
            
            # 2. 只有不包含排除格式的文件才检查宽度
            width, match_count = self.get_zip_images_info(zip_path)
            should_process = self.should_process_zip(width, match_count, zip_path)
            
            return zip_path, should_process
            
        except Exception as e:
            self.logger.error(f"处理压缩包时出错 {zip_path}: {str(e)}")
            return zip_path, False

    def run_7z_command(self, command, zip_path, operation="", additional_args=None):
        """
        执行7z命令的通用函数
        
        Args:
            command: 主命令 (如 'a', 'x', 'l' 等)
            zip_path: 压缩包路径
            operation: 操作描述（用于日志）
            additional_args: 额外的命令行参数
        """
        try:
            cmd = ['7z', command, str(zip_path)]
            if additional_args:
                cmd.extend(additional_args)
            
            result = subprocess.run(cmd, capture_output=True, text=False)  # 使用二进制模式
            
            if result.returncode == 0:
                try:
                    # 尝试用cp932解码（适用于Windows日文系统）
                    output = result.stdout.decode('cp932')
                except UnicodeDecodeError:
                    try:
                        # 如果cp932失败，尝试用utf-8解码
                        output = result.stdout.decode('utf-8')
                    except UnicodeDecodeError:
                        # 如果两种编码都失败，使用errors='replace'
                        output = result.stdout.decode('utf-8', errors='replace')
            
                return True, output
            else:
                error_output = result.stderr
                try:
                    error_text = error_output.decode('cp932')
                except UnicodeDecodeError:
                    try:
                        error_text = error_output.decode('utf-8')
                    except UnicodeDecodeError:
                        error_text = error_output.decode('utf-8', errors='replace')
                    
                self.logger.error(f"7z {operation}失败: {zip_path}\n错误: {error_text}")
                return False, error_text
            
        except Exception as e:
            self.logger.error(f"执行7z命令出错: {e}")
            return False, str(e)

    def check_7z_contents(self, zip_path):
        """使用7z检查压缩包内容"""
        try:
            success, output = self.run_7z_command('l', zip_path, "列出内容")
            if not success:
                return True  # 如果出错，保守起见返回True
            
            # 检查输出中是否包含排除的格式
            output = output.lower()
            for ext in self.exclude_formats:
                if ext in output:
                    self.logger.info(f"跳过压缩包 {zip_path.name} 因为包含排除格式: {ext}")
                    return True
            return False
            
        except Exception as e:
            self.logger.error(f"检查压缩包格式时出错 {zip_path}: {str(e)}")
            return True

    def has_excluded_formats(self, zip_path):
        """检查压缩包中是否包含需要排除的文件格式"""
        return self.check_7z_contents(zip_path)

    def process(self):
        # 获取目标目录中所有zip文件的名称（不区分大小写）
        existing_files = {f.name.lower() for f in self.target_dir.rglob("*.zip")}
        
        # 收集需要处理的文件
        zip_files = []
        for f in self.source_dir.rglob("*.zip"):
            if f.name.lower() in existing_files or self.should_exclude_path(str(f)):
                continue
            zip_files.append(f)

        if not zip_files:
            self.logger.info("没有找到需要处理的文件")
            return

        self.logger.info(f"开始处理 {len(zip_files)} 个文件")
        self.logger.info(f"已排除包含关键词的路径: {', '.join(self.exclude_paths)}")
        self.logger.info(f"模式: {'大于等于' if self.compare_larger else '小于'} {self.min_width}px")
        self.logger.info(f"操作: {'移动' if self.cut_mode else '复制'}")
        
        processed_folders = set()
        processed_count = 0

        # 处理文件
        operation = "移动" if self.cut_mode else "复制"
        moved_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for zip_path, should_process in tqdm(
                executor.map(self.process_single_zip, zip_files),
                total=len(zip_files),
                desc="处理文件"
            ):
                if should_process:
                    processed_folders.add(zip_path.parent)
                    processed_count += 1
                    
                    # 处理文件
                    rel_path = zip_path.relative_to(self.source_dir)
                    new_folder = self.target_dir / rel_path.parent
                    new_folder.mkdir(parents=True, exist_ok=True)

                    try:
                        if self.cut_mode:
                            shutil.move(str(zip_path), str(new_folder / zip_path.name))
                        else:
                            shutil.copy2(str(zip_path), str(new_folder / zip_path.name))
                        moved_count += 1
                        self.logger.info(f"成功{operation}: {zip_path.name}")
                    except Exception as e:
                        self.logger.error(f"{operation}失败 {zip_path}: {str(e)}")

        # 如果是移动模式，清理空文件夹
        if self.cut_mode:
            for folder in processed_folders:
                if not any(folder.iterdir()):
                    try:
                        folder.rmdir()
                        self.logger.info(f"删除空文件夹: {folder}")
                    except Exception as e:
                        self.logger.error(f"删除文件夹失败 {folder}: {str(e)}")

        self.logger.info(f"处理完成: 成功{operation} {moved_count} 个文件")

def main():
    # 配置参数
    config = {
        "source_dir": r"E:\999EHV",
        "target_dir": r"E:\7EHV",
        "min_width": 1800,
        "cut_mode": False,
        "max_workers": 16,
        "compare_larger": False,
        "threshold_count": 3
    }

    try:
        processor = ImageProcessor(**config)
        processor.process()
    except Exception as e:
        logger.exception("程序执行出错")  # 使用全局logger

if __name__ == "__main__":
    # Windows长路径支持
    if os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem", 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "LongPathsEnabled", 0, winreg.REG_DWORD, 1)
        except Exception as e:
            logger.error(f"无法启用长路径支持: {e}")  # 使用全局logger
    
    main() 
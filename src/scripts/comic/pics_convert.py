from nodes.config.import_bundles import *

import fsspec

import importlib.util
import tempfile
# ----
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "performance_config",
    # os.path.join(os.path.dirname(__file__), "configs/performance_config.py")
    r"D:\1VSCODE\GlowToolBox\src\nodes\config\performance_config.py"
)
performance_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(performance_config)
from nodes.config.performance_config import *
# ---
ConfigGUI = performance_config.ConfigGUI
from nodes.tui.textual_logger import TextualLoggerManager
vipshome = Path(r'D:\1VSCODE\1ehv\other\vips\bin')
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(str(vipshome))
os.environ['PATH'] = str(vipshome) + ';' + os.environ['PATH']
import pyvips
# 全局配置
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(str(vipshome))
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
# 在全局配置部分添加以下内容
# ================= 日志配置 =================
from nodes.record.logger_config import setup_logger

config = {
    'script_name': 'pics_convert',
    'console_enabled': False
}
logger, config_info = setup_logger(config)

# 全局变量
verbose_logging = True
use_direct_path_mode = True
restore_enabled = False
use_multithreading = True
filter_height_enabled = False
filter_white_enabled = False
handle_artbooks = False
add_processed_comment_enabled = False
add_processed_log_enabled = True
backup_removed_files_enabled = False
ignore_yaml_log = True
ignore_processed_log = True
wrap_log_lines = True  # 控制是否对日志进行折行处理
processed_files_yaml = 'E:\\1EHV\\processed_files.yaml'
artbook_keywords = []
exclude_paths = []
min_size = 639
white_threshold = 8
white_score_threshold = 0.92
threshold = 1
max_workers = min(4, os.cpu_count() or 4)

# 全局常量
INCLUDED_KEYWORDS = ['汉化', '官方', '中文', '漢化', '掃', '修正', '制', '譯', '个人', '翻', '製', '嵌', '訳', '淫书馆']
PERFORMANCE_CONFIG_PATH = r"D:\1VSCODE\1ehv\archive\config\performance_config.py"
ENCRYPTION_KEY = 'HibernalGlow'
FILENAME_MAPPING_FILE = 'filename_mapping.json'

# 图片转换配置
IMAGE_CONVERSION_CONFIG = {
    'source_formats': {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.avif', '.jxl'},
    'target_format': '.avif',
    'webp_config': {
        'quality': 90,
        'method': 4,
        'lossless': False,
        'strip': True
    },
    'avif_config': {
        'quality': 90,
        'speed': 7,
        'chroma_quality': 100,
        'lossless': False,
        'strip': True
    },
    'jxl_config': {
        'quality': 90,
        'effort': 7,
        'lossless': False,
        'modular': False,
        'jpeg_recompression': False,
        'jpeg_lossless': False,
        'strip': True
    },
    'jpeg_config': {
        'quality': 90,
        'optimize': True,
        'strip': True
    },
    'png_config': {
        'optimize': True,
        'compress_level': 6,
        'strip': True
    }
}

# 文件格式配置
SUPPORTED_ARCHIVE_FORMATS = {'.zip', '.cbz'}
VIDEO_FORMATS = {'.mp4', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.mov', '.m4v', '.mpg', '.mpeg', '.3gp', '.rmvb'}
AUDIO_FORMATS = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac', '.wma', '.opus', '.ape', '.alac'}
EXCLUDED_IMAGE_FORMATS = {'.jxl', '.avif', '.webp', '.gif', '.psd', '.ai', '.cdr', '.eps', '.svg', '.raw', '.cr2', '.nef', '.arw', '.dng', '.tif', '.tiff'}

# 效率检查配置
EFFICIENCY_CHECK_CONFIG = {
    'min_files_to_check': 3,
    'min_efficiency_threshold': 10,
    'max_inefficient_files': 3
}

# 添加cjxl路径到全局配置
CJXL_PATH = Path(r'D:\1VSCODE\1ehv\exe\jxl\cjxl.exe')
DJXL_PATH = Path(r'D:\1VSCODE\1ehv\exe\jxl\djxl.exe')

# 更新布局配置
LAYOUT_CONFIG = {
    "status": {
        "ratio": 1,
        "title": "🏭 总体进度",
        "style": "lightblue"
    },
    "progress": {
        "ratio": 1,
        "title": "🔄 当前进度",
        "style": "lightgreen"
    },
    "performance": {
        "ratio": 1,
        "title": "⚡ 性能配置",
        "style": "lightyellow"
    },
    "image": {
        "ratio": 2,
        "title": "🖼️ 图片转换",
        "style": "lightsalmon"
    },   
    "archive": {
        "ratio": 2,
        "title": "📦 压缩包处理",
        "style": "lightpink"
    },
    "file": {
        "ratio": 2,
        "title": "📂 文件操作",
        "style": "lightcyan"
    },

}

def init_layout():
    TextualLoggerManager.set_layout(LAYOUT_CONFIG, config_info['log_file'])
    # logger.info(f"[#performance]初始化性能配置面板")
    # logger.info(f"[#file]初始化文件操作面板")
    # logger.info(f"[#archive]初始化压缩包处理面板")


class FileSystem:
    """文件系统操作类"""

    def __init__(self):
        self.path_handler = PathHandler()
        self.fs = fsspec.filesystem('file')

    def ensure_directory_exists(self, directory):
        """确保目录存在，如果不存在则创建"""
        try:
            if not self.fs.exists(directory):
                self.fs.makedirs(directory)
                logger.info(f"[#file]创建目录: {directory}")
            return True
        except Exception as e:
            logger.info(f"[#file]创建目录失败 {directory}: {e}")
            return False

    def safe_delete_file(self, file_path):
        """安全删除文件"""
        try:
            if self.fs.exists(file_path):
                self.fs.delete(file_path)
                logger.info(f"[#file]删除文件: {file_path}")
                return True
            return False
        except Exception as e:
            logger.info(f"[#file]删除文件失败 {file_path}: {e}")
            return False

    def safe_move_file(self, src_path, dst_path):
        """安全移动文件"""
        try:
            if not self.fs.exists(src_path):
                logger.info(f"[#file]源文件不存在: {src_path}")
                return False
            if self.fs.exists(dst_path):
                logger.info(f"[#file]目标文件已存在: {dst_path}")
                return False
            self.fs.move(src_path, dst_path)
            logger.info(f"[#file]移动文件: {src_path} -> {dst_path}")
            return True
        except Exception as e:
            logger.info(f"[#file]移动文件失败 {src_path} -> {dst_path}: {e}")
            return False

    def safe_copy_file(self, src_path, dst_path):
        """安全复制文件"""
        try:
            if not self.fs.exists(src_path):
                logger.info(f"[#file]源文件不存在: {src_path}")
                return False
            if self.fs.exists(dst_path):
                logger.info(f"[#file]目标文件已存在: {dst_path}")
                return False
            with self.fs.open(src_path, 'rb') as src, self.fs.open(dst_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            logger.info(f"[#file]复制文件: {src_path} -> {dst_path}")
            return True
        except Exception as e:
            logger.info(f"[#file]复制文件失败 {src_path} -> {dst_path}: {e}")
            return False

    def get_file_size(self, file_path):
        """获取文件大小"""
        try:
            return self.fs.info(file_path)['size']
        except Exception as e:
            logger.info(f"[#file]获取文件大小失败 {file_path}: {e}")
            return 0

    def list_files(self, directory, pattern=None):
        """列出目录中的文件"""
        try:
            files = []
            for root, _, filenames in self.fs.walk(directory):
                for filename in filenames:
                    if pattern is None or any(filename.lower().endswith(ext) for ext in pattern):
                        files.append(os.path.join(root, filename))
            return files
        except Exception as e:
            logger.info(f"[#file]列出文件失败 {directory}: {e}")
            return []

class PathHandler:
    """路径处理类"""
    

    @staticmethod
    def ensure_long_path(path):
        """为路径添加Windows长路径前缀，返回Path对象"""
        try:
            abs_path = Path(path).resolve()
            path_str = str(abs_path)
            if len(path_str) > 260 or any((ord(c) > 127 for c in path_str)):
                if not path_str.startswith('\\\\?\\'):
                    return Path('\\\\?\\' + path_str)
            return abs_path
        except Exception as e:
            logger.info(f"[#file]处理长路径时出错: {e}")
            return Path(path)

    def create_temp_directory(self, file_path):
        """为每个压缩包创建唯一的临时目录，支持长路径"""
        try:
            fs = fsspec.filesystem('file')
            base_path = Path(file_path).resolve()
            temp_dir = base_path.parent / f'temp_{base_path.stem}_{int(time.time())}'
            safe_temp_dir = PathHandler.ensure_long_path(temp_dir)
            fs.makedirs(str(safe_temp_dir), exist_ok=True)
            logger.info(f"[#file]创建临时目录: {safe_temp_dir}")  
            return safe_temp_dir
        except Exception as e:
            logger.info(f"[#file]创建临时目录失败: {e}")
            raise

    def cleanup_temp_files(self, temp_dir, new_zip_path, backup_file_path):
        """清理临时文件和目录，支持长路径"""
        try:
            fs = fsspec.filesystem('file')
            if temp_dir:
                safe_temp = PathHandler.ensure_long_path(temp_dir)
                if fs.exists(str(safe_temp)):
                    fs.delete(str(safe_temp), recursive=True)
                    logger.info(f"[#file]已删除临时目录: {safe_temp}")  
            if new_zip_path:
                safe_new = PathHandler.ensure_long_path(new_zip_path)
                if fs.exists(str(safe_new)):
                    fs.delete(str(safe_new))
                    logger.info(f"[#file]已删除临时压缩包: {safe_new}")  
            if backup_file_path:
                safe_backup = PathHandler.ensure_long_path(backup_file_path)
                if fs.exists(str(safe_backup)):
                    fs.delete(str(safe_backup))
                    logger.info(f"[#file]已删除备份文件: {safe_backup}")  
        except Exception as e:
            logger.info(f"[#file]清理临时文件时出错: {e}")

    def wrapper(self, path, *args, **kwargs):
        """路径处理包装器"""
        try:
            long_path = self.ensure_long_path(path)
            return self.func(long_path, *args, **kwargs)
        except OSError as e:
            if e.winerror == 3:
                logger.info(f"[#file]路径超长或无效: {path}")
            else:
                raise

class DirectoryHandler:
    """目录处理类"""

    def flatten_single_subfolder(self, directory, exclude_keywords):
        """如果目录中只有一个子文件夹，将其内容移动到父目录"""
        try:
            contents = os.listdir(directory)
            if len(contents) != 1:
                return
            subdir = os.path.join(directory, contents[0])
            if not os.path.isdir(subdir):
                return
            if any((keyword in os.path.basename(subdir).lower() for keyword in exclude_keywords)):
                return
            for item in os.listdir(subdir):
                src = os.path.join(subdir, item)
                dst = os.path.join(directory, item)
                shutil.move(src, dst)
            os.rmdir(subdir)
            logger.info(f"[#file]已展平子文件夹: {subdir}")
        except Exception as e:
            logger.info(f"[#file]展平子文件夹时出错: {e}")

    def remove_empty_directories(self, directory):
        """删除指定目录下的所有空文件夹"""
        removed_count = 0
        for root, dirs, _ in os.walk(directory, topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                try:
                    if not os.listdir(dir_path):
                        subprocess.run(['cmd', '/c', 'rd', '/s', '/q', dir_path], check=True)
                        removed_count += 1
                        logger.info(f"[#file]已删除空文件夹: {dir_path}")
                except Exception as e:
                    logger.info(f"[#file]删除空文件夹失败 {dir_path}: {e}")
        return removed_count



class Converter:
    """图片转换类"""

    def __init__(self):
        self.path_handler = PathHandler()

    def convert_with_cjxl(self, input_path, output_path, is_jpeg=False):
        """使用cjxl进行转换
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径 
            is_jpeg: 是否是JPEG文件
        """
        try:
            if not CJXL_PATH.exists():
                logger.info(f"[#file]cjxl.exe不存在: {CJXL_PATH}")
                return False
                
            # 构建命令
            if is_jpeg:
                # JPEG无损模式
                cmd = [
                    str(CJXL_PATH),
                    '-e', '7',  # effort level
                    '--lossless_jpeg=1',  # 启用JPEG无损
                    str(input_path),
                    str(output_path)
                ]
            else:
                # 普通无损模式
                cmd = [
                    str(CJXL_PATH), 
                    '-e', '7',
                    '-d', '0',  # 无损模式
                    str(input_path),
                    str(output_path)
                ]
            
            # 执行转换
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"[#file]cjxl转换成功: {input_path}")
                return True
            else:
                logger.info(f"[#file]cjxl转换失败: {input_path}\n错误: {result.stderr}")
                return False
                
        except Exception as e:
            logger.info(f"[#file]cjxl转换出错: {e}")
            return False

    def process_single_image(self, file_path, params):
        """处理单个图片文件"""
        try:
            fs = fsspec.filesystem('file')
            target_ext = IMAGE_CONVERSION_CONFIG['target_format'].lower()
            
            if file_path.lower().endswith(target_ext):
                return False
                
            base_path = os.path.splitext(file_path)[0]
            new_file_path = base_path + target_ext
            counter = 1
            while fs.exists(new_file_path):
                new_file_path = f'{base_path}_{counter}{target_ext}'
                counter += 1
                
            original_size = fs.info(file_path)['size'] / 1024
            
            # 只在JXL无损模式下使用cjxl
            if target_ext == '.jxl' and params.get('use_cjxl', False):
                is_jpeg = file_path.lower().endswith(('.jpg', '.jpeg'))
                logger.info(f"[#image]✅ 使用cjxl转换: {file_path}")
                if not self.convert_with_cjxl(file_path, new_file_path, is_jpeg):
                    return False
            else:
                # 其他情况使用原有转换方式
                with fs.open(file_path, 'rb') as f:
                    image = pyvips.Image.new_from_buffer(f.read(), '')
                format_config = IMAGE_CONVERSION_CONFIG[f'{target_ext[1:]}_config']
                params = {
                    'Q': format_config['quality'],
                    'strip': format_config.get('strip', True),
                    'lossless': format_config.get('lossless', False)
                }
                safe_new_path = self.path_handler.ensure_long_path(new_file_path)
                image.write_to_file(str(safe_new_path), **params)
                # logger.info(f"[#image]✅ 使用libvip转换: {file_path}")
            if fs.exists(new_file_path):
                new_size = fs.info(new_file_path)['size'] / 1024
                size_reduction = original_size - new_size
                compression_ratio = size_reduction / original_size * 100
                # status_message = f'{os.path.basename(file_path)}: {original_size:.0f}KB -> {new_size:.0f}KB (-{size_reduction:.0f}KB, -{compression_ratio:.1f}%)'
                # logger.info(f"[#file]{status_message}")
                try:
                    image = None
                    fs.delete(file_path)
                    return (True, original_size, new_size)
                except Exception as e:
                    error_msg = f'删除原文件失败 {file_path}: {e}'
                    logger.info(f"[#image]{error_msg}")
                    return False
            return False
        except Exception as e:
            error_msg = f'处理图片失败 {file_path}: {e}'
            logger.info(f"[#image]{error_msg}")
            return False

    def process_image_in_memory(self, image_data, min_size=640, min_width=0):
        """处理单个图片数据"""
        try:
            with BytesIO(image_data) as bio:
                with Image.open(bio) as img:
                    original_format = img.format.lower()
                    original_size = len(image_data) / 1024
                    original_dimensions = f'{img.width}x{img.height}'
                    width_info = ''
                    if min_width > 0:
                        width_info = f', 最小宽度要求={min_width}px'
                    logger.info(f"[#image]处理图片: 格式={original_format}, 尺寸={original_dimensions}{width_info}, 大小={original_size:.2f}KB")
                    if min_width > 0:
                        if img.width < min_width:
                            logger.info(f"[#image][宽度过小] 图片宽度 {img.width}px 小于指定的最小宽度 {min_width}px，跳过处理")
                            return (image_data, 'width_too_small')
                        else:
                            logger.info(f"[#image][宽度符合] 图片宽度 {img.width}px 大于指定的最小宽度 {min_width}px，继续处理")
                    cur_format = img.format.lower()
                    target_format = IMAGE_CONVERSION_CONFIG['target_format'][1:].lower()
                    if cur_format == target_format:
                        logger.info(f"[#image]图片已经是目标格式 {target_format}，跳过转换")
                        return (image_data, None)
            image = pyvips.Image.new_from_buffer(image_data, '')
            config = IMAGE_CONVERSION_CONFIG[f'{target_format}_config']
            logger.info(f"[#image]转换配置: 目标格式={target_format}, 参数={config}")
            if target_format == 'avif':
                params = {'Q': config['quality'], 'speed': config.get('speed', 7), 'strip': config.get('strip', True), 'lossless': config.get('lossless', False)}
            elif target_format == 'webp':
                params = {'Q': config['quality'], 'strip': config.get('strip', True), 'lossless': config.get('lossless', False), 'reduction_effort': config.get('method', 4)}
            elif target_format == 'jxl':
                params = {'Q': config['quality'], 'strip': config.get('strip', True), 'lossless': config.get('lossless', False), 'effort': config.get('effort', 7), 'modular': config.get('modular', False), 'jpeg_recompression': config.get('jpeg_recompression', False), 'jpeg_lossless': config.get('jpeg_lossless', False)}
            elif target_format == 'jpg' or target_format == 'jpeg':
                params = {'Q': config['quality'], 'strip': config.get('strip', True), 'optimize_coding': config.get('optimize', True)}
            else:
                params = {'strip': config.get('strip', True), 'compression': config.get('compress_level', 6)}
            output_buffer = image.write_to_buffer(f'.{target_format}', **params)
            converted_size = len(output_buffer) / 1024
            size_change = original_size - converted_size
            logger.info(f"[#image]转换完成: 新大小={converted_size:.2f}KB, 减少={size_change:.2f}KB ({size_change / original_size * 100:.1f}%)")
            return (output_buffer, None)
        except Exception as e:
            logger.info(f"[#image]图片转换错误: {str(e)}")
            return (None, 'processing_error')

    def has_processed_comment(self, zip_path, comment='Processed'):
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                return zip_ref.comment.decode('utf-8') == comment
        except Exception as e:
            logger.info(f"[#file]Error checking comment in {zip_path}: {e}")
            return False

    def add_processed_comment(self, zip_path, comment='Processed'):
        try:
            with zipfile.ZipFile(zip_path, 'a') as zip_ref:
                zip_ref.comment = comment.encode('utf-8')
            logger.info(f"[#archive]Added comment '{comment}' to {zip_path}")
        except Exception as e:
            logger.info(f"[#archive]Error adding comment to {zip_path}: {e}")

class BatchProcessor:
    """批量处理类"""
    def __init__(self):
        self.converter = Converter()
        self.efficiency_tracker = EfficiencyTracker()

    def _collect_image_files(self, temp_dir):
        """收集目录中的图片文件"""
        image_files = []
        for root, _, files in os.walk(temp_dir):
            for file in files:
                if any((file.lower().endswith(ext) for ext in IMAGE_CONVERSION_CONFIG['source_formats'])):
                    file_path = os.path.join(root, file)
                    image_files.append(file_path)
        image_files.sort()
        return image_files

    def _write_log_header(self, log_file, initial_count, archive_path):
        """写入日志文件头部"""
        log_file.write('# 图片转换日志\n\n')
        log_file.write(f'## 基本信息\n\n')
        log_file.write(f"- **转换时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n")
        if archive_path:
            log_file.write(f'- **压缩包路径**: `{archive_path}`\n')
            log_file.write(f'- **压缩包名称**: `{os.path.basename(archive_path)}`\n')
        log_file.write(f'- **图片总数**: `{initial_count}`\n\n')
        
        # 同时更新到面板
        logger.info(f"[#archive]📝 开始处理压缩包: {os.path.basename(archive_path) if archive_path else '未知'}")
    def _write_conversion_params(self, log_file):
        """写入转换参数"""
        log_file.write('## 转换参数\n\n')
        log_file.write(f"- **目标格式**: `{IMAGE_CONVERSION_CONFIG['target_format']}`\n")
        format_config = IMAGE_CONVERSION_CONFIG[f"{IMAGE_CONVERSION_CONFIG['target_format'][1:]}_config"]
        log_file.write(f"- **质量设置**: `{format_config['quality']}`\n")
        
        # 同时更新到面板
        params_text = f"🎯 目标格式: {IMAGE_CONVERSION_CONFIG['target_format']}, 质量: {format_config['quality']}"
        
        if IMAGE_CONVERSION_CONFIG['target_format'] == '.jxl':
            log_file.write(f"- **编码效果(effort)**: `{format_config.get('effort', 7)}`\n")
            log_file.write(f"- **无损模式**: `{format_config.get('lossless', False)}`\n")
            log_file.write(f"- **JPEG重压缩**: `{format_config.get('jpeg_recompression', False)}`\n")
            log_file.write(f"- **JPEG无损**: `{format_config.get('jpeg_lossless', False)}`\n")
            params_text += f", effort: {format_config.get('effort', 7)}"
            if format_config.get('lossless', False):
                params_text += ", 无损模式"
        elif IMAGE_CONVERSION_CONFIG['target_format'] == '.avif':
            log_file.write(f"- **速度设置**: `{format_config.get('speed', 7)}`\n")
            log_file.write(f"- **色度质量**: `{format_config.get('chroma_quality', 100)}`\n")
            params_text += f", 速度: {format_config.get('speed', 7)}"
        elif IMAGE_CONVERSION_CONFIG['target_format'] == '.webp':
            log_file.write(f"- **压缩方法**: `{format_config.get('method', 4)}`\n")
            params_text += f", 方法: {format_config.get('method', 4)}"
            
        logger.info(f"[#image]{params_text}")

    def _write_log_summary(self, log_file, processed_files, total_time, total_original_size, total_converted_size):
        """写入日志总结"""
        if not processed_files:
            return
            
        avg_time = total_time / len(processed_files) if processed_files else 0
        total_compression_ratio = ((total_original_size - total_converted_size) / total_original_size * 100) if total_original_size > 0 else 0
        
        # 写入文件
        log_file.write(f"\n## 总结\n\n")
        log_file.write(f"- **总处理文件数**: `{len(processed_files)}`\n")
        log_file.write(f"- **总处理耗时**: `{total_time:.1f}秒`\n")
        log_file.write(f"- **平均单张耗时**: `{avg_time:.1f}秒`\n")
        log_file.write(f"- **总原始大小**: `{total_original_size/1024:.1f}MB`\n")
        log_file.write(f"- **总转换后大小**: `{total_converted_size/1024:.1f}MB`\n")
        log_file.write(f"- **总体压缩率**: `{total_compression_ratio:.1f}%`\n")
        log_file.write(f"- **处理完成时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n")
        
        # 更新到面板
        summary_text = (
            f"✨ 处理完成 📊 总文件数: {len(processed_files)} ⏱️ 总耗时: {total_time:.1f}秒 (平均 {avg_time:.1f}秒/张) 📦 总大小: {total_original_size/1024:.1f}MB -> {total_converted_size/1024:.1f}MB 📈 压缩率: {total_compression_ratio:.1f}"
        )
        logger.info(f"[#archive]{summary_text}")

    def _process_image_batch(self, batch, params, processed_files, log_file_path, temp_dir, total_status):
        """处理一批图片文件"""
        futures = []
        current_threads = get_thread_count()
        batch_size = get_batch_size()
        logger.info(f"[#performance]当前线程数: {current_threads}, 当前批处理大小: {batch_size}")
     
        with ThreadPoolExecutor(max_workers=current_threads) as executor:
            for file_path in batch:
                future = executor.submit(self.converter.process_single_image, file_path, params)
                futures.append((future, file_path))
                
            for future, file_path in futures:
                try:
                    result = future.result()
                    if isinstance(result, tuple) and result[0]:
                        processed_files.add(file_path)
                        original_size, new_size = result[1], result[2]
                        total_status['original_size'] += original_size
                        total_status['converted_size'] += new_size
                        size_reduction = original_size - new_size
                        compression_ratio = size_reduction / original_size * 100
                        
                        message = f"{os.path.relpath(file_path, temp_dir)} ({original_size:.0f}KB -> {new_size:.0f}KB, 减少{size_reduction:.0f}KB, 压缩率{compression_ratio:.1f})"
                        logger.info(f"[#image]✅ {message}")
                        archive_status=len(processed_files)/total_status['initial_count']*100
                        archive_ratio= str(len(processed_files))+'/'+str(total_status['initial_count'])
                        logger.info(f"[@progress] 当前进度: {archive_ratio} {archive_status:.1f}%")
                        
                        with open(log_file_path, 'a', encoding='utf-8') as f:
                            f.write(f"| `{os.path.relpath(file_path, temp_dir)}` | {original_size:.0f}KB | {new_size:.0f}KB | {size_reduction:.0f}KB | {compression_ratio:.1f}% |\n")
                except Exception as e:
                    logger.info(f"[#file]❌ 处理图片失败 {os.path.relpath(file_path, temp_dir)}: {e}")
                    with open(log_file_path, 'a', encoding='utf-8') as f:
                        f.write(f"\n> ⚠️ 处理失败: `{os.path.relpath(file_path, temp_dir)}` - {str(e)}\n")

    def process_images_in_directory(self, temp_dir, params, archive_path=None):
        """处理目录中的图片"""
        try:
            start_time = time.time()
            total_status = {
                'original_size': 0,
                'converted_size': 0
            }
            
            # 收集图片文件
            image_files = self._collect_image_files(temp_dir)
            total_status['initial_count'] = len(image_files)
            
            if not image_files:
                logger.info(f"[#file]未找到图片文件在目录: {temp_dir}")
                return set()
                
            # 创建并初始化日志文件
            log_file_path = os.path.join(temp_dir, 'conversion.md')
            with open(log_file_path, 'w', encoding='utf-8') as f:
                self._write_log_header(f, total_status['initial_count'], archive_path)
                self._write_conversion_params(f)
                f.write('\n## 转换详情\n\n')
                f.write('| 文件名 | 原始大小 | 转换后大小 | 减少大小 | 压缩率 |\n')
                f.write('|--------|----------|------------|----------|--------|\n')
            
            # 处理图片文件
            processed_files = set()
            batch_size = get_batch_size()
            for i in range(0, len(image_files), batch_size):
                batch = image_files[i:i + batch_size]
                self._process_image_batch(batch, params, processed_files, 
                                       log_file_path, temp_dir, total_status)
            
            # 写入总结
            with open(log_file_path, 'a', encoding='utf-8') as f:
                self._write_log_summary(f, processed_files, time.time() - start_time,
                                      total_status['original_size'], total_status['converted_size'])
            
            return processed_files
            
        except Exception as e:
            logger.info(f"[#file]处理目录的图片时出错: {e}")
            return set()

class ArchiveHandler:
    """处理压缩包的类"""
    def __init__(self):
        self.path_handler = PathHandler()

    def _validate_archive(self, file_path: Path, params: dict) -> tuple[bool, int]:
        """验证压缩包是否需要处理"""
        if not file_path.exists():
            logger.info(f"[#file]文件不存在: {file_path}")
            return False, 0
            
        if not self.should_process_file(file_path, params):
            logger.info(f"[#archive]根据过滤条件跳过文件: {file_path}")
            logger.info(f"[#archive]跳过: {file_path.name} - 不符合关键词要求")
            return False, 0
            
        logger.info(f"[#archive]🔄 正在处理: {file_path.name}")
            
        needs_processing, image_count = self.check_archive_contents(str(file_path), params.get('min_width', 0))
        
        if needs_processing is None:
            logger.info(f"[#archive]文件被占用，将添加到重试队列: {file_path}")
            return False, 0
        elif needs_processing is False:
            logger.info(f"[#archive]压缩包 {file_path} 无需处理")
            return False, 0
        elif image_count == 0:
            logger.info(f"[#archive]压缩包 {file_path} 不包含图片文件")
            return False, 0
            
        return True, image_count

    def _prepare_paths(self, file_path: Path) -> tuple[Path, Path, Path]:
        """准备处理所需的临时路径"""
        temp_dir = self.path_handler.create_temp_directory(file_path)
        new_zip_path = file_path.parent / f'{file_path.name}.{int(time.time())}.new'
        backup_file_path = file_path.parent / f'{file_path.name}.{int(time.time())}.bak'
        
        # 创建备份
        shutil.copy2(file_path, backup_file_path)
        logger.info(f"[#file]创建备份: {backup_file_path}")
        
        return temp_dir, new_zip_path, backup_file_path

    def _process_archive_contents(self, file_path: Path, temp_dir: Path, params: dict, 
                                image_count: int) -> tuple[set, dict]:
        """处理压缩包内容"""
        if not self.extract_archive(file_path, temp_dir):
            logger.info(f"[#file]解压失败: {file_path}")
            return set(), {}
            
        logger.info(f"[#image]正在处理图片: {file_path.name}")
        processed_files = BatchProcessor().process_images_in_directory(
            temp_dir, params, archive_path=file_path
        )
            
        return processed_files, {}

    def _finalize_archive(self, file_path: Path, temp_dir: Path, new_zip_path: Path,
                         backup_file_path: Path, processed_files: set, skipped_files: dict,
                         image_count: int) -> list:
        """完成压缩包处理"""
        processed_archives = []
        
        if any((reason == '连续低效率转换' for reason in skipped_files.values())):
            logger.info(f"[#archive]压缩包 {file_path} 因连续低效率转换被跳过")
            logger.info(f"[#archive]跳过: {file_path.name} - 连续低效率转换")
            return []
            
        if not processed_files:
            logger.info(f"[#archive]没有需要处理的图片: {file_path}")
            return []
            
        logger.info(f"[#archive]正在创建新压缩包: {file_path.name}")
            
        if not ArchiveContent().cleanup_and_compress(temp_dir, processed_files, skipped_files, new_zip_path):
            logger.info(f"[#archive]清理和压缩失败: {file_path}")
            logger.info(f"[#archive]错误: {file_path.name} - 清理和压缩失败")
            return []
            
        success, size_change = self.handle_size_comparison(file_path, new_zip_path, backup_file_path)
        if success:
            result = {
                'file_path': str(file_path),
                'processed_images': len(processed_files),
                'skipped_images': len(skipped_files),
                'size_reduction_mb': size_change
            }
            processed_archives.append(result)
            logger.info(f"[#archive]完成: {file_path.name} - 减少了 {size_change:.2f}MB")
        else:
            logger.info(f"[#archive]跳过: {file_path.name} - 新文件大小未减小")

                
        return processed_archives

    def process_single_archive(self, file_path, params):
        """处理单个压缩包文件"""
        try:
            file_path = Path(file_path)
            logger.info(f"[#file]开始处理文件: {file_path}")
            
            # 验证压缩包
            is_valid, image_count = self._validate_archive(file_path, params)
            if not is_valid:
                return []
                
            # 准备路径
            temp_dir = None
            new_zip_path = None
            backup_file_path = None
            try:
                temp_dir, new_zip_path, backup_file_path = self._prepare_paths(file_path)
                
                # 设置rename_cbr属性
                self.rename_cbr = params.get('rename_cbr', False)
                
                # 处理内容
                processed_files, skipped_files = self._process_archive_contents(
                    file_path, temp_dir, params, image_count
                )
                
                # 完成处理
                return self._finalize_archive(
                    file_path, temp_dir, new_zip_path, backup_file_path,
                    processed_files, skipped_files, image_count
                )
            finally:
                self.path_handler.cleanup_temp_files(temp_dir, new_zip_path, backup_file_path)
                
        except Exception as e:
            logger.info(f"[#archive]处理压缩包时出错 {file_path}: {e}")
            logger.info(f"[#archive]错误: {file_path.name} - {str(e)}")
            return []

    def prepare_archive(self, file_path):
        """准备压缩包处理环境"""
        temp_dir = PathHandler.create_temp_directory(file_path)
        backup_file_path = file_path + '.bak'
        new_zip_path = file_path + '.new'
        try:
            shutil.copy(file_path, backup_file_path)
            logger.info(f"[#file]创建备份: {backup_file_path}")
            try:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                    logger.info(f"[#file]成功解压文件到: {temp_dir}")
                    return (temp_dir, backup_file_path, new_zip_path, file_path)
            except zipfile.BadZipFile:
                logger.info(f"[#file]无效的压缩包格式: {file_path}")
                PathHandler.cleanup_temp_files(temp_dir, new_zip_path, backup_file_path)
                return (None, None, None, None)
        except Exception as e:
            logger.info(f"[#file]准备环境失败 {file_path}: {e}")
            PathHandler.cleanup_temp_files(temp_dir, new_zip_path, backup_file_path)
            return (None, None, None, None)

    def run_7z_command(self, command, zip_path, operation='', additional_args=None):
        """
        执行7z命令的通用函数
        
        Args:
            command: 主命令 (如 'a', 'x', 'l' 等)
            zip_path: 压缩包路径
            operation: 操作描述（用于日志）
            additional_args: 额外的命令行参数
        """
        try:
            cmd = ['7z', command, zip_path]
            if additional_args:
                cmd.extend(additional_args)
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"[#file]成功执行7z {operation}: {zip_path}")
                return (True, result.stdout)
            else:
                logger.info(f"[#file]7z {operation}失败: {zip_path}\n错误: {result.stderr}")
                return (False, result.stderr)
        except Exception as e:
            logger.info(f"[#file]执行7z命令出错: {e}")
            return (False, str(e))

    def create_new_archive(self, temp_dir, new_zip_path):
        """创建新的压缩包，支持长路径"""
        try:
            safe_temp = PathHandler.ensure_long_path(temp_dir)
            safe_zip = PathHandler.ensure_long_path(new_zip_path)
            cmd = ['7z', 'a', '-tzip', str(safe_zip), os.path.join(str(safe_temp), '*')]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.info(f"[#file]创建压缩包失败: {safe_zip}\n错误: {result.stderr}")
                return False
            fs = fsspec.filesystem('file')
            if not fs.exists(str(safe_zip)):
                logger.info(f"[#file]压缩包创建失败，文件不存在: {safe_zip}")
                return False
            logger.info(f"[#file]成功创建新压缩包: {safe_zip}")
            return True
        except Exception as e:
            logger.info(f"[#file]创建压缩包时出错: {e}")
            return False

    def check_archive_contents(self, file_path, min_width=0):
        """
        使用zipfile检查压缩包内容
        
        Returns:
            (needs_processing, image_count): (是否需要处理, 图片文件数)
            如果返回 (False, 0)，表示压缩包不需要处理（可能包含视频/音频/排除格式或为空）
            如果返回 (None, 0)，表示文件被占用
        """
        try:
            try:
                with open(file_path, 'rb') as f:
                    f.read(1)
            except (IOError, PermissionError):
                logger.info(f"[#file]文件正在被占用，稍后重试: {file_path}")
                return (None, 0)
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                if not file_list:
                    logger.info(f"[#file]压缩包为空: {file_path}")
                    return (False, 0)
                target_ext = IMAGE_CONVERSION_CONFIG['target_format'].lower()
                image_count = 0
                needs_processing = False
                has_video = False
                has_audio = False
                has_excluded_format = False
                temp_dir = None
                if min_width > 0:
                    temp_dir = tempfile.mkdtemp()
                try:
                    for file_name in file_list:
                        if file_name.endswith('/'):
                            continue
                        file_ext = os.path.splitext(file_name.lower())[1]
                        if file_ext in VIDEO_FORMATS:
                            has_video = True
                            logger.info(f"[#file]发现视频文件: {file_name}")
                            return (False, 0)
                        elif file_ext in AUDIO_FORMATS:
                            has_audio = True
                            logger.info(f"[#file]发现音频文件: {file_name}")
                            return (False, 0)
                        elif file_ext in EXCLUDED_IMAGE_FORMATS:
                            has_excluded_format = True
                            logger.info(f"[#file]发现排除格式图片: {file_name}")
                            return (False, 0)
                        if any((file_ext == ext for ext in IMAGE_CONVERSION_CONFIG['source_formats'])):
                            image_count += 1
                            if file_ext != target_ext:
                                needs_processing = True
                                if min_width > 0 and temp_dir:
                                    try:
                                        zip_ref.extract(file_name, temp_dir)
                                        img_path = os.path.join(temp_dir, file_name)
                                        with Image.open(img_path) as img:
                                            if img.width < min_width:
                                                logger.info(f"[#image]发现宽度不足的图片: {file_name} (宽度: {img.width}px < {min_width}px)")
                                                return (False, 0)
                                    except Exception as e:
                                        logger.info(f"[#file]检查图片宽度时出错 {file_name}: {e}")
                                        continue
                                    finally:
                                        try:
                                            if os.path.exists(img_path):
                                                os.remove(img_path)
                                        except:
                                            pass
                finally:
                    if temp_dir and os.path.exists(temp_dir):
                        try:
                            shutil.rmtree(temp_dir)
                        except:
                            pass
                if needs_processing:
                    logger.info(f"[#file]压缩包 {file_path} 包含 {image_count} 个图片文件，需要处理")
                return (needs_processing, image_count)
        except zipfile.BadZipFile:
            logger.info(f"[#file]无效的压缩包格式: {file_path}")
            return (False, 0)
        except Exception as e:
            logger.info(f"[#file]检查压缩包内容时出错 {file_path}: {e}")
            if '另一个程序正在使用此文件' in str(e) or 'being used by another process' in str(e):
                return (None, 0)
            return (False, 0)

    def should_process_file(self, file_path, params):
        """判断文件是否需要处理"""
        if params.get('exclude_paths'):
            is_excluded = any((exclude_path in str(file_path) for exclude_path in params['exclude_paths']))
            if is_excluded:
                logger.info(f"[#file]文件在排除路径中，跳过: {file_path}")
                return False
        if params.get('keywords'):
            file_name = os.path.basename(str(file_path)).lower()
            if params['keywords'] == 'internal':
                has_keyword = any((keyword.lower() in file_name for keyword in INCLUDED_KEYWORDS))
                if not has_keyword:
                    logger.info(f"[#file]文件名不包含内置关键词，跳过: {file_path}")
                    return False
                logger.info(f"[#file]文件名包含内置关键词，继续处理: {file_path}")
            elif isinstance(params['keywords'], list):
                has_keyword = any((keyword.lower() in file_name for keyword in params['keywords']))
                if not has_keyword:
                    logger.info(f"[#file]文件名不包含指定关键词，跳过: {file_path}")
                    return False
                logger.info(f"[#file]文件名包含指定关键词，继续处理: {file_path}")
        is_art = self.is_artbook(str(file_path), params['artbook_keywords'])
        if params['handle_artbooks']:
            return is_art
        else:
            return not is_art

    def extract_archive(self, file_path, temp_dir):
        """
        解压文件，支持多种解压方案
        
        Args:
            file_path: 压缩包路径
            temp_dir: 解压目标目录
            
        Returns:
            bool: 是否成功解压
        """
        try:
            safe_src = PathHandler.ensure_long_path(file_path)
            safe_dest = PathHandler.ensure_long_path(temp_dir)
            logger.info(f"[#file]开始解压: {safe_src} ")
            try:
                # 使用 7z x 命令，保持目录结构
                cmd = ['7z', 'x', str(safe_src), f'-o{str(safe_dest)}', '-y']
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info(f"[#file]使用7z成功解压: {safe_src}")
                    return True
                else:
                    logger.info(f"[#file]7z解压失败，尝试备用方案: {result.stderr}")
                    
                # 如果 x 命令失败，尝试使用 e 命令（不保持目录结构）
                # cmd = ['7z', 'e', str(safe_src), f'-o{str(safe_dest)}', '-y']
                # result = subprocess.run(cmd, capture_output=True, text=True)
                # if result.returncode == 0:
                #     logger.info(f"[#file]使用7z (e)成功解压: {safe_src}")
                #     return True
                # else:
                #     logger.info(f"[#file]7z (e)解压也失败，尝试其他方案: {result.stderr}")
            except Exception as e:
                logger.info(f"[#file]7z解压出错，尝试备用方案: {e}")
                
            # 尝试使用 zipfile
            try:
                with zipfile.ZipFile(str(safe_src), 'r') as zip_ref:
                    file_list = zip_ref.namelist()
                    if not file_list:
                        logger.info(f"[#file]压缩包为空: {safe_src}")
                        return False
                    for file_name in file_list:
                        decoded_name = file_name
                        try:
                            decoded_name = file_name.encode('cp437').decode('gbk', errors='ignore')
                        except UnicodeError:
                            pass
                        target_path = safe_dest / decoded_name
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        if not file_name.endswith('/'):
                            with zip_ref.open(file_name) as source, open(str(target_path), 'wb') as target:
                                shutil.copyfileobj(source, target)
                    logger.info(f"[#file]使用zipfile成功解压: {safe_src}")
                    return True
            except zipfile.BadZipFile:
                logger.info(f"[#file]zipfile解压失败: {safe_src}")
            except Exception as e:
                logger.info(f"[#file]zipfile解压出错: {e}")
                
            logger.info(f"[#file]所有解压方案都失败: {safe_src}")
            return False
        except Exception as e:
            logger.info(f"[#file]解压文件时出错: {e}")
            return False

    def handle_size_comparison(self, file_path, new_zip_path, backup_file_path):
        """比较新旧文件大小并处理替换，支持长路径"""
        try:
            fs = fsspec.filesystem('file')
            safe_file = PathHandler.ensure_long_path(file_path)
            safe_new = PathHandler.ensure_long_path(new_zip_path)
            safe_backup = PathHandler.ensure_long_path(backup_file_path)
            if not fs.exists(str(safe_new)):
                logger.info(f"[#file]新压缩包不存在: {safe_new}")
                return (False, 0)
            original_size = fs.info(str(safe_file))['size']
            new_size = fs.info(str(safe_new))['size']
            # 如果新文件大小超过原文件的80%，认为压缩效果不理想
            SIZE_THRESHOLD_RATIO = 0.8  # 80%
            if new_size >= original_size * SIZE_THRESHOLD_RATIO:
                logger.info(f"[#file]新压缩包 ({new_size / 1024 / 1024:.2f}MB) 大小超过原始文件 ({original_size / 1024 / 1024:.2f}MB) 的{SIZE_THRESHOLD_RATIO*100}%，压缩效果不理想")
                fs.delete(str(safe_new))
                if fs.exists(str(safe_backup)):
                    fs.move(str(safe_backup), str(safe_file))
                    # 只有在启用了rename_cbr选项时才重命名为CBR
                    if hasattr(self, 'rename_cbr') and self.rename_cbr:
                        new_name = safe_file.with_suffix('.cbr')
                        fs.move(str(safe_file), str(new_name))
                        logger.info(f"[#file]已将文件改为CBR: {new_name}")
                return (False, 0)
            try:
                with fs.open(str(safe_file), 'rb') as f:
                    f.read(1)
            except Exception as e:
                logger.info(f"[#file]无法访问目标文件，可能正在被使用: {safe_file}")
                return (False, 0)
            try:
                fs.delete(str(safe_file))
                fs.move(str(safe_new), str(safe_file))
            except Exception as e:
                logger.info(f"[#file]替换文件时出错: {e}")
                if fs.exists(str(safe_backup)):
                    try:
                        fs.move(str(safe_backup), str(safe_file))
                        logger.info("[#file]已还原原始文件")
                    except Exception as restore_error:
                        logger.info(f"[#file]还原文件失败: {restore_error}")
                return (False, 0)
            if fs.exists(str(safe_backup)):
                try:
                    fs.delete(str(safe_backup))
                    logger.info(f"[#file]已删除备份文件: {safe_backup}")
                except Exception as e:
                    logger.info(f"[#file]删除备份文件失败: {e}")
            size_change = (original_size - new_size) / (1024 * 1024)
            logger.info(f"[#file]更新压缩包: {safe_file} (减少 {size_change:.2f}MB)")
            return (True, size_change)
        except Exception as e:
            logger.info(f"[#file]比较文件大小时出错: {e}")
            if fs.exists(str(safe_backup)):
                try:
                    fs.move(str(safe_backup), str(safe_file))
                    logger.info("[#file]已还原原始文件")
                except Exception as restore_error:
                    logger.info(f"[#file]还原文件失败: {restore_error}")
            if fs.exists(str(safe_new)):
                try:
                    fs.delete(str(safe_new))
                except Exception as remove_error:
                    logger.info(f"[#file]删除新文件失败: {remove_error}")
            return (False, 0)

    def is_artbook(self, file_path, artbook_keywords):
        """检查是否为画集"""
        file_path_str = str(file_path)
        file_name = os.path.basename(file_path_str).lower()
        return any((keyword.lower() in file_name or keyword.lower() in file_path_str.lower() for keyword in artbook_keywords))


class ArchiveContent:
    """压缩包内容处理类"""

    def __init__(self):
        self.directory_handler = DirectoryHandler()

    def cleanup_and_compress(self, temp_dir, processed_files, skipped_files, new_zip_path):
        """清理文件并创建新压缩包"""
        try:
            logger.info(f"[#file]处理了 {len(processed_files)} 张图片，跳过了 {len(skipped_files)} 张图片")
            if backup_removed_files_enabled:
                self.backup_removed_files(new_zip_path, processed_files, skipped_files)
            removed_count = 0
            for file_path in processed_files:
                try:
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                        removed_count += 1
                        logger.info(f"[#file]已删除文件: {file_path}")
                except Exception as e:
                    logger.info(f"[#file]删除文件失败 {file_path}: {e}")
                    continue
            logger.info(f"[#file]已删除 {removed_count} 个文件")
            empty_dirs_removed = self.directory_handler.remove_empty_directories(temp_dir)
            if empty_dirs_removed != 0:
                logger.info(f"[#file]已删除 {empty_dirs_removed} 个空文件夹")
            self.directory_handler.flatten_single_subfolder(temp_dir, [])
            if not os.path.exists(temp_dir):
                logger.info(f"[#file]临时目录不存在: {temp_dir}")
                return False
            if not any(os.scandir(temp_dir)):
                logger.info(f"[#file]临时目录为空: {temp_dir}")
                return False
            try:
                with zipfile.ZipFile(new_zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
                    for root, _, files in os.walk(temp_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, temp_dir)
                            zip_ref.write(file_path, arcname)
                if not os.path.exists(new_zip_path):
                    logger.info(f"[#archive]压缩包创建失败: {new_zip_path}")
                    return False
                logger.info(f"[#archive]成功创建新压缩包: {new_zip_path}")
                return True
            except Exception as e:
                logger.info(f"[#archive]创建压缩包失败: {e}")
                return False
        except Exception as e:
            logger.info(f"[#archive]清理和压缩时出错: {e}")
            return False

    def create_new_zip(self, zip_path, temp_dir):
        """从临时目录创建新的压缩包"""
        try:
            if not any(os.scandir(temp_dir)):
                logger.info(f"[#file]临时目录为空: {temp_dir}")
                return False
            cmd = ['7z', 'a', '-tzip', zip_path, os.path.join(temp_dir, '*')]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                if not os.path.exists(zip_path):
                    logger.info(f"[#archive]压缩包创建失败: {zip_path}")
                    return False
                logger.info(f"[#archive]成功创建新压缩包: {zip_path} ({os.path.getsize(zip_path) / 1024 / 1024:.2f} MB)")
                return True
            else:
                logger.info(f"[#archive]创建压缩包失败: {result.stderr}")
                return False
        except Exception as e:
            logger.info(f"[#file]创建压缩包时出错: {e}")
            return False

    def read_zip_contents(self, zip_path):
        """读取压缩包中的文件列表"""
        try:
            cmd = ['7z', 'l', '-slt', zip_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.info(f"[#file]读取压缩包失败: {zip_path}\n错误: {result.stderr}")
                return []
            files = []
            cur_file = None
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line.startswith('Path = '):
                    cur_file = line[7:]
                    if cur_file and (not cur_file.endswith('/')):
                        files.append(cur_file)
            logger.info(f"[#file]Found {len(files)} files in archive: {zip_path}")
            return files
        except Exception as e:
            logger.info(f"[#file]读取压缩包内容时出错 {zip_path}: {e}")
            return []

    def extract_file_from_zip(self, zip_path, file_name, temp_dir):
        """从压缩包中提取单个文件"""
        extract_path = os.path.join(temp_dir, file_name)
        success, _ = ArchiveHandler().run_7z_command('e', zip_path, '提取文件', [f'-o{temp_dir}', file_name, '-y'])
        if success and os.path.exists(extract_path):
            with open(extract_path, 'rb') as f:
                data = f.read()
            os.remove(extract_path)
            return data
        return None

    def delete_backup_if_successful(self, backup_path):
        """如果处理成功则删除备份文件"""
        if os.path.exists(backup_path) and backup_path.endswith('.bak'):
            try:
                logger.info(f"[#file]将备份文件移至回收站: {backup_path}")
                send2trash(backup_path)
            except Exception as e:
                logger.info(f"[#file]移动备份文件到回收站失败: {backup_path} - {e}")

    def backup_removed_files(self, zip_path, removed_files, duplicate_files):
        """将删除的文件备份到trash文件夹中，保持原始目录结构"""
        try:
            if not removed_files and (not duplicate_files):
                return
            zip_name = os.path.splitext(os.path.basename(zip_path))[0]
            trash_dir = os.path.join(os.path.dirname(zip_path), f'{zip_name}.trash')
            os.makedirs(trash_dir, exist_ok=True)
            for file_path in removed_files:
                rel_path = os.path.relpath(file_path, os.path.dirname(zip_path))
                dest_path = os.path.join(trash_dir, 'removed', rel_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(file_path, dest_path)
            for file_path in duplicate_files:
                rel_path = os.path.relpath(file_path, os.path.dirname(zip_path))
                dest_path = os.path.join(trash_dir, 'duplicates', rel_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(file_path, dest_path)
            logger.info(f"[#file]已备份删除的文件到: {trash_dir}")
        except Exception as e:
            logger.info(f"[#file]备份删除文件时出错: {e}")


class Performance:
    """
    类描述
    """

    def get_optimal_thread_count(self, image_count):
        """根据图片数量获取最优线程数"""
        if image_count <= 10:
            return 2
        elif image_count <= 50:
            return min(4, os.cpu_count() or 4)
        else:
            return min(8, os.cpu_count() or 4)

# 更新 PerformanceConfig 类
class PerformanceConfig:
    """性能配置管理类"""
    
    def __init__(self, config_path=None):
        self.config_path = config_path or PERFORMANCE_CONFIG_PATH
        self._load_config()

    def _load_config(self):
        """加载性能配置"""
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("performance_config", self.config_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.get_thread_count = module.get_thread_count
            self.get_batch_size = module.get_batch_size
            return True
        except Exception as e:
            logger.info(f"[#file]加载性能配置文件失败: {e}")
            self.get_thread_count = self.default_thread_count
            self.get_batch_size = self.default_batch_size
            return False

    @staticmethod
    def default_batch_size():
        """获取默认批处理大小"""
        return 10

    @staticmethod
    def default_thread_count():
        """获取默认线程数"""
        return min(4, os.cpu_count() or 4)

    def set_performance_config_path(self, path):
        """设置性能配置文件路径"""
        if os.path.exists(path):
            self.config_path = path
            success = self._load_config()
            if success:
                logger.info(f"[#file]已设置性能配置文件路径: {path}")
            return success
        else:
            logger.info(f"[#file]性能配置文件不存在: {path}")
            return False

    def get_optimal_thread_count(self, image_count):
        """根据图片数量获取最优线程数"""
        if image_count <= 10:
            return 2
        elif image_count <= 50:
            return min(4, os.cpu_count() or 4)
        else:
            return min(8, os.cpu_count() or 4)

class EfficiencyTracker:
    """效率跟踪类"""

    def __init__(self, config=None):
        self.config = config or EFFICIENCY_CHECK_CONFIG
        self.processed_files = []
        self.inefficient_count = 0

    def add_result(self, original_size, new_size):
        """添加一个转换结果"""
        if original_size <= 0:
            return False
        reduction_percent = (original_size - new_size) / original_size * 100
        self.processed_files.append(reduction_percent)
        if len(self.processed_files) >= self.config['min_files_to_check']:
            if reduction_percent < self.config['min_efficiency_threshold']:
                self.inefficient_count += 1
        return self.should_continue()

    def reset(self):
        """重置跟踪器"""
        self.processed_files = []
        self.inefficient_count = 0

    def get_average_efficiency(self):
        """获取平均效率"""
        if not self.processed_files:
            return 0
        return sum(self.processed_files) / len(self.processed_files)

    def should_continue(self):
        """判断是否应该继续处理"""
        return self.inefficient_count < self.config['max_inefficient_files']



class Monitor:
    """监控类"""
    def __init__(self):
        """初始化监控类"""
        self.total_files = 0
        self.processed_files = 0
        self.skipped_files = 0  # 添加跳过文件计数
        self.cur_file = ""
        self.start_time = None
        self.last_config = (0, 0)
        self.current_batch_size = get_batch_size()  # 初始化批处理大小
    def handle_config_update(self, new_threads: int, new_batch: int):
        """统一处理配置更新"""
        if (new_threads, new_batch) == self.last_config:
            return  # 无变化时跳过
        
        logger.info(f"[#config] 应用新配置: 线程数={new_threads} 批处理={new_batch}")
        
        # 更新线程池
        global executor
        executor.shutdown(wait=False)
        executor = ThreadPoolExecutor(max_workers=new_threads)
        
        # 更新批处理大小
        self.current_batch_size = new_batch
        self.last_config = (new_threads, new_batch)
        logger.info(f"[#runtime] 配置已生效 | 线程: {new_threads} | 批次: {new_batch}")
    def _update_executor(self, new_threads: int, new_batch: int):
        """动态更新线程池的实例方法"""
        global executor
        executor.shutdown(wait=False)
        executor = ThreadPoolExecutor(max_workers=new_threads)
        # logger.info(f"[#performance] 线程池已更新至{new_threads} workers")

    @staticmethod
    def update_performance_info():
        """更新性能面板信息（单次更新）"""
        thread_count = get_thread_count()
        batch_size = get_batch_size()
        logger.info(f"[#performance]线程数: {thread_count} 批处理大小: {batch_size} ")

    def auto_run_process(self, directories, params, interval_minutes=10, infinite_mode=False):
        """自动运行处理过程"""
        try:
            # 初始化布局
            self.start_time = time.time()
            
            self._run_process_loop(directories, params, interval_minutes, infinite_mode)
        except KeyboardInterrupt:
            logger.info("[#file]⚠️ 用户中断处理")
        except Exception as e:
            logger.info(f"[#file]❌ 处理过程出错: {e}")

    def _update_status(self):
        """更新统计信息"""
        if self.total_files > 0:
            total_processed = self.processed_files + self.skipped_files  # 包含已处理和跳过的文件
            progress = total_processed / self.total_files * 100
            logger.info(f"[#status]总进度: (✅{self.processed_files}+⏭️{self.skipped_files}/{self.total_files}) {progress:.1f}%")

    def _run_process_loop(self, directories, params, interval_minutes, infinite_mode):
        """处理循环的具体实现"""
        round_count = 0
        processed_files = set()
        skipped_files = {}
        occupied_files = set()
        
        while True:
            try:
                round_count += 1
                logger.info(f"[#file]🔄 开始第 {round_count} 轮处理...")
                
                # 获取要处理的文件列表
                files_to_process = self._get_files_to_process(directories, processed_files, skipped_files, occupied_files)
                
                if not files_to_process:
                    if infinite_mode:
                        logger.info("[#file]⏸️ 当前没有需要处理的文件，继续监控...")
                        self._wait_next_round(interval_minutes)
                        continue
                    else:
                        logger.info("[#file]✅ 所有文件已处理完成")
                        break
                
                # 更新总文件数
                self.total_files = len(files_to_process)
                self._update_status()
                
                # 处理文件
                self._process_files(files_to_process, params, processed_files, skipped_files, occupied_files)
                
                # 等待下一轮
                if infinite_mode or occupied_files or len(processed_files) > 0 or len(skipped_files) > 0:
                    wait_minutes = min(round_count, 10)
                    logger.info(f"[#file]⏸️ 等待 {wait_minutes} 分钟后开始下一轮...")
                    self._wait_next_round(wait_minutes)
                    continue
                else:
                    break
                    
            except Exception as e:
                logger.info(f"[#file]❌ 处理过程出错: {e}")
                if infinite_mode:
                    logger.info(f"[#file]⚠️ 处理出错: {e}，等待下一轮...")
                    self._wait_next_round(interval_minutes)
                    continue
                else:
                    break

    def _wait_next_round(self, minutes):
        """等待下一轮处理"""
        total_seconds = minutes * 60
        for remaining in range(total_seconds, 0, -1):
            logger.info(f"[#status]⏳ 等待下一轮 剩余时间: {remaining // 60}分{remaining % 60}秒")
            logger.info(f"[@status] 等待下一轮{remaining / total_seconds * 100:.1f}%")
            
            time.sleep(1)


    def _process_files(self, files, params, processed_files, skipped_files, occupied_files):
        """处理文件列表"""
        if not files:
            return
            
        for index, file_path in enumerate(files, 1):
            try:
                file_name = os.path.basename(file_path)

                
                # 检查文件是否被占用
                if self._is_file_locked(file_path):
                    occupied_files.add(file_path)
                    logger.info(f"[#file]⚠️ 文件被占用: {file_name}")
                    continue
                
                # 处理单个文件
                result = ArchiveHandler().process_single_archive(file_path, params)
                
                if result:
                    processed_files.add(file_path)
                    self.processed_files += 1
                    self._update_status()
                    logger.info(f"[#file]✅ 处理完成: {file_name}")
                else:
                    reason = skipped_files.get(file_path, "未知原因")
                    if file_path in skipped_files:
                        logger.info(f"[#file]⚠️ 跳过文件: {file_name} - {reason}")
                        self.skipped_files += 1  # 增加跳过文件计数
                    else:
                        logger.info(f"[#file]⚠️ 跳过文件: {file_name} - 处理失败或不需要处理")
                    
            except Exception as e:
                logger.info(f"[#file]❌ 处理文件出错 {file_path}: {e}")


    def _get_files_to_process(self, directories, processed_files, skipped_files, occupied_files):
        """获取需要处理的文件列表"""
        files_to_process = []
        for directory in directories:
            if os.path.isfile(directory):
                if any(directory.lower().endswith(ext) for ext in SUPPORTED_ARCHIVE_FORMATS):
                    if directory not in processed_files and directory not in skipped_files:
                        files_to_process.append(directory)
            else:
                for root, _, files in os.walk(directory):
                    for file in files:
                        if any(file.lower().endswith(ext) for ext in SUPPORTED_ARCHIVE_FORMATS):
                            file_path = os.path.join(root, file)
                            if file_path not in processed_files and file_path not in skipped_files:
                                files_to_process.append(file_path)
        
        # 检查并移除被占用的文件
        files_to_process = [f for f in files_to_process if not self._is_file_locked(f)]
        
        if files_to_process:
            logger.info(f"[#file]📝 找到 {len(files_to_process)} 个待处理文件")
        
        return files_to_process

    def _is_file_locked(self, file_path):
        """检查文件是否被锁定"""
        try:
            with open(file_path, 'rb') as f:
                f.read(1)
            return False
        except (IOError, PermissionError):
            return True

class InputHandler:
    """输入处理类"""

    def parse_arguments(self):
        """解析命令行参数"""
        parser = argparse.ArgumentParser(description='图片压缩包转换工具')
        parser.add_argument('--clipboard', '-c', action='store_true', help='从剪贴板读取路径')
        parser.add_argument('--format', '-f', choices=['avif', 'webp', 'jxl', 'jpg', 'png'], default='avif', help='指定转换的目标格式 (默认: avif)')
        parser.add_argument('--quality', '-q', type=int, default=90, help='指定压缩质量 (1-100, 默认: 90)')
        parser.add_argument('--lossless', '-l', action='store_true', help='使用无损压缩模式')
        parser.add_argument('--jxl-jpeg-lossless', '-j', action='store_true', help='使用 JXL 的 JPEG 无损转换模式（仅在格式为 jxl 时有效）')
        parser.add_argument('--interval', '-i', type=int, default=10, help='自动运行的时间间隔（分钟，默认10分钟）')
        parser.add_argument('--min-width', '-w', type=int, default=0, help='只处理宽度大于指定值的图片（像素，默认0表示不限制）')
        parser.add_argument('--keywords', '-k', action='store_true', help='使用内置关键词列表过滤压缩包')
        parser.add_argument('--performance-config', '-p', type=str, help='指定性能配置文件的路径')
        parser.add_argument('--infinite', '-inf', action='store_true', help='启用无限循环模式，即使没有变化也继续监控')
        parser.add_argument('--rename-cbr', '-r', action='store_true', help='启用低压缩率文件重命名为CBR功能')
        return parser.parse_args()

    def get_paths_from_clipboard(self):
        """从剪贴板读取多行路径"""
        try:
            clipboard_content = pyperclip.paste()
            if not clipboard_content:
                return []
            paths = [path.strip().strip('"') for path in clipboard_content.splitlines() if path.strip()]
            valid_paths = [path for path in paths if os.path.exists(path)]
            if valid_paths:
                logger.info(f"[#file]从剪贴板读取到 {len(valid_paths)} 个有效路径")
            else:
                logger.info(f"[#file]剪贴板中没有有效路径")
            return valid_paths
        except ImportError:
            logger.info(f"[#file]未安装 pyperclip 模块，无法读取剪贴板")
            return []
        except Exception as e:
            logger.info(f"[#file]读取剪贴板时出错: {e}")
            return []




class ProcessingQueue:
    """文件处理队列管理类"""
    
    def __init__(self):
        self.pending_files = set()
        self.processing_files = set()
        self.processing_lock = threading.Lock()
        self.last_check_time = time.time()
        self.check_interval = 10

class FileWatcher:
    """文件监控类"""
    
    def __init__(self, processing_queue):
        self.processing_queue = processing_queue
    
    def on_created(self, event):
        """处理新文件创建事件"""
        if event.is_directory:
            return
        file_path = event.src_path
        if not any((file_path.lower().endswith(ext) for ext in SUPPORTED_ARCHIVE_FORMATS)):
            return
        with self.processing_queue.processing_lock:
            self.processing_queue.pending_files.add(file_path)
            logger.info(f"[#file]添加文件到待处理列表: {file_path}")
            self.processing_queue.last_check_time = 0
            self.check_pending_files()

    def check_pending_files(self):
        """检查待处理文件是否可以处理"""
        cur_time = time.time()
        if cur_time - self.processing_queue.last_check_time < self.processing_queue.check_interval:
            return
            
        self.processing_queue.last_check_time = cur_time
        
        with self.processing_queue.processing_lock:
            files_to_remove = set()
            files_to_process = set()
            
            for file_path in self.processing_queue.pending_files:
                try:
                    if not os.path.exists(file_path):
                        files_to_remove.add(file_path)
                        continue
                        
                    try:
                        with open(file_path, 'rb') as f:
                            f.read(1)
                    except (IOError, PermissionError):
                        logger.info(f"[#file]文件被占用，跳过: {file_path}")
                        files_to_remove.add(file_path)
                        continue
                        
                    files_to_process.add(file_path)
                    
                except Exception as e:
                    logger.info(f"[#file]检查文件时出错 {file_path}: {e}")
                    files_to_remove.add(file_path)
            
            self.processing_queue.pending_files -= files_to_remove
            self.processing_queue.pending_files -= files_to_process
            
            for file_path in files_to_process:
                if file_path not in self.processing_queue.processing_files:
                    self.processing_queue.processing_files.add(file_path)
                    threading.Thread(
                        target=self._process_file,
                        args=(file_path,)
                    ).start()

    def _process_file(self, file_path):
        """处理单个文件的线程函数"""
        try:
            ArchiveHandler().process_single_archive(file_path, {})
        except Exception as e:
            logger.info(f"[#file]处理文件时出错 {file_path}: {e}")
        finally:
            with self.processing_queue.processing_lock:
                self.processing_queue.processing_files.remove(file_path)

# def parse_arguments():
#     """解析命令行参数"""
#     parser = argparse.ArgumentParser(description='图片压缩包转换工具')
#     parser.add_argument('--clipboard', '-c', action='store_true', help='从剪贴板读取路径')
#     parser.add_argument('--format', '-f', choices=['avif', 'webp', 'jxl', 'jpg', 'png'], default='avif', help='指定转换的目标格式 (默认: avif)')
#     parser.add_argument('--quality', '-q', type=int, default=90, help='指定压缩质量 (1-100, 默认: 90)')
#     parser.add_argument('--lossless', '-l', action='store_true', help='使用无损压缩模式')
#     parser.add_argument('--jxl-jpeg-lossless', '-j', action='store_true', help='使用 JXL 的 JPEG 无损转换模式（仅在格式为 jxl 时有效）')
#     parser.add_argument('--interval', '-i', type=int, default=10, help='自动运行的时间间隔（分钟，默认10分钟）')
#     parser.add_argument('--min-width', '-w', type=int, default=0, help='只处理宽度大于指定值的图片（像素，默认0表示不限制）')
#     parser.add_argument('--keywords', '-k', action='store_true', help='使用内置关键词列表过滤压缩包')
#     parser.add_argument('--performance-config', '-p', type=str, help='指定性能配置文件的路径')
#     parser.add_argument('--infinite', '-inf', action='store_true', help='启用无限循环模式，即使没有变化也继续监控')
#     return parser.parse_args()

class ErrorHandler:
    """错误处理类"""
    
    @staticmethod
    def handle_file_error(e, file_path, operation):
        """处理文件操作错误"""
        if isinstance(e, PermissionError):
            logger.info(f"[#file]{operation}失败(权限不足): {file_path}")
        elif isinstance(e, FileNotFoundError):
            logger.info(f"[#file]{operation}失败(文件不存在): {file_path}")
        else:
            logger.info(f"[#file]{operation}失败: {file_path} - {str(e)}")

    @staticmethod
    def handle_archive_error(e, archive_path):
        """处理压缩包错误"""
        if isinstance(e, zipfile.BadZipFile):
            logger.info(f"[#file]无效的压缩包格式: {archive_path}")
        elif isinstance(e, PermissionError):
            logger.info(f"[#file]压缩包访问权限不足: {archive_path}")
        else:
            logger.info(f"[#file]处理压缩包时出错: {archive_path} - {str(e)}")

    @staticmethod
    def handle_image_error(e, image_path):
        """处理图片错误"""
        if isinstance(e, Image.DecompressionBombError):
            logger.info(f"[#file]图片过大: {image_path}")
        elif isinstance(e, Image.UnidentifiedImageError):
            logger.info(f"[#file]无法识别的图片格式: {image_path}")
        else:
            logger.info(f"[#file]处理图片时出错: {image_path} - {str(e)}")

class ConfigManager:
    """配置管理类"""
    
    def __init__(self):
        self.config = {}
        self.config_file = None
        
    def load_config(self, config_file):
        """加载配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
                self.config_file = config_file
            return True
        except Exception as e:
            logger.info(f"[#file]加载配置文件失败: {e}")
            return False

    def save_config(self):
        """保存配置到文件"""
        if not self.config_file:
            logger.info(f"[#file]未指定配置文件路径")
            return False
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(self.config, f, allow_unicode=True)
            return True
        except Exception as e:
            logger.info(f"[#file]保存配置文件失败: {e}")
            return False

    def get_value(self, key, default=None):
        """获取配置值"""
        return self.config.get(key, default)

    def set_value(self, key, value):
        """设置配置值"""
        self.config[key] = value

class PerformanceMonitor:
    """性能监控类"""
    
    def __init__(self):
        self.start_time = time.time()
        self.metrics = {}
        self.checkpoints = {}
        
    def record_metric(self, name, value):
        """记录性能指标"""
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(value)

    def start_checkpoint(self, name):
        """开始检查点计时"""
        self.checkpoints[name] = time.time()

    def end_checkpoint(self, name):
        """结束检查点计时并记录耗时"""
        if name in self.checkpoints:
            duration = time.time() - self.checkpoints[name]
            self.record_metric(f'{name}_duration', duration)
            del self.checkpoints[name]
            return duration
        return None

    def get_average_metric(self, name):
        """获取指标平均值"""
        if name in self.metrics and self.metrics[name]:
            return sum(self.metrics[name]) / len(self.metrics[name])
        return None

    def get_summary(self):
        """获取性能监控摘要"""
        summary = {
            'total_duration': time.time() - self.start_time,
            'metrics': {}
        }
        for name, values in self.metrics.items():
            summary['metrics'][name] = {
                'average': sum(values) / len(values),
                'min': min(values),
                'max': max(values),
                'count': len(values)
            }
        return summary

def init_performance_config(args):
    """初始化性能配置"""
    if args.performance_config:
        performance_config = PerformanceConfig(args.performance_config)
        if not performance_config.load_config():
            logger.info(f"[#file]使用默认性能配置")

def init_keywords(args):
    """初始化关键词设置"""
    if args.keywords:
        keywords = 'internal'
        logger.info(f"[#file]将使用内置关键词列表: {INCLUDED_KEYWORDS}")
    else:
        keywords = None
        logger.info("[#file]未启用关键词过滤")
    return keywords

def configure_image_conversion(args):
    """配置图像转换参数"""
    target_format = f'.{args.format}'
    IMAGE_CONVERSION_CONFIG['target_format'] = target_format
    quality = args.quality
    
    # 创建参数字典
    params = {}
    
    # 更新各格式的质量设置
    for format_config in ['webp_config', 'avif_config', 'jxl_config', 'jpeg_config']:
        IMAGE_CONVERSION_CONFIG[format_config]['quality'] = quality
    
    # 处理特殊格式设置
    if args.format == 'jxl' and args.jxl_jpeg_lossless:
        params['use_cjxl'] = True  # 添加标志以启用CJXL
        logger.info("[#file]已启用 CJXL 的 JPEG 无损转换模式")
    elif args.lossless:
        configure_lossless_mode()
        
    return params  # 返回参数字典

def configure_lossless_mode():
    """配置无损模式参数"""
    IMAGE_CONVERSION_CONFIG['webp_config'].update({'lossless': True, 'quality': 100})
    IMAGE_CONVERSION_CONFIG['avif_config'].update({'lossless': True, 'quality': 100, 'speed': 6})
    IMAGE_CONVERSION_CONFIG['jxl_config'].update({
        'lossless': True,
        'quality': 100,
        'effort': 7,
        'jpeg_recompression': False,
        'jpeg_lossless': False
    })
    IMAGE_CONVERSION_CONFIG['jpeg_config']['quality'] = 100
    IMAGE_CONVERSION_CONFIG['png_config'].update({'optimize': True, 'compress_level': 9})
    logger.info("[#file]已启用普通无损压缩模式")

def process_directories(use_clipboard, input_handler):
    """处理目录输入"""
    directories = []
    if use_clipboard:
        directories = input_handler.get_paths_from_clipboard()
    if not directories:
        # 使用富文本输入界面获取路径
        print("请输入要处理的文件夹或压缩包路径（每行一个，输入空行结束）:")

        
        for i, line in enumerate(directories):
            directory = line.strip().strip('"').strip("'")
            if os.path.exists(directory):
                directories.append(directory)
                progress = (i+1)/len(directories)*100
                logger.info(f"[#file]✅ 已添加路径: {directory}")
            else:
                logger.info(f"[#file]路径不存在: {directory}")
    return directories

def run_with_args(args):
    """供TUI界面调用的函数"""
    # 初始化配置
    init_layout()

    init_performance_config(args)
    keywords = init_keywords(args)
    params = configure_image_conversion(args)

    directories = process_directories(args.clipboard, InputHandler())
    if directories:
        params.update({
            'min_size': min_size,
            'white_threshold': white_threshold,
            'white_score_threshold': white_score_threshold,
            'threshold': threshold,
            'filter_height_enabled': filter_height_enabled,
            'filter_white_enabled': filter_white_enabled,
            'max_workers': get_thread_count(),
            'handle_artbooks': handle_artbooks,
            'artbook_keywords': artbook_keywords,
            'exclude_paths': exclude_paths,
            'ignore_processed_log': ignore_processed_log,
            'ignore_yaml_log': ignore_yaml_log,
            'min_width': args.min_width,
            'keywords': keywords,
            'rename_cbr': args.rename_cbr,
            'batch_size': get_batch_size()
        })
        
        # 初始化面板布局

        # 启动性能配置GUI
        config_gui_thread = threading.Thread(target=lambda: ConfigGUI().run(), daemon=True)
        config_gui_thread.start()
        logger.info("[#file]🔧 已启动性能配置调整器")
        
        logger.info(f"[#file]🚀 启动{('无限循环' if args.infinite else '自动运行')}模式，每 {args.interval} 分钟运行一次...")
        monitor = Monitor()
        monitor.auto_run_process(directories, params, args.interval, args.infinite)


def main():
    """主函数"""

    # 检查是否有命令行参数
    if len(sys.argv) > 1:
        input_handler = InputHandler()
        args = input_handler.parse_arguments()
        run_with_args(args)
    else:
        # 没有命令行参数时启动TUI界面


        # 定义复选框选项
        checkbox_options = [
            ("从剪贴板读取路径", "clipboard", "--clipboard", True),
            ("内置关键词过滤", "keywords", "--keywords", False),
            ("无限循环inf", "infinite", "--infinite", False),
            ("JXL的JPEG无损转换", "jxl_jpeg_lossless", "--jxl-jpeg-lossless", False),
            ("无损压缩", "lossless", "--lossless", False),
            ("低压缩率重命名CBR", "rename_cbr", "--rename-cbr", False),
        ]

        # 定义输入框选项
        input_options = [
            ("目标格式", "format", "--format", "avif", "avif/webp/jxl/jpg/png"),
            ("压缩质量", "quality", "--quality", "90", "1-100"),
            ("监控间隔(分钟)", "interval", "--interval", "10", "分钟"),
            ("最小宽度(像素)", "min_width", "--min-width", "0", "像素"),
            ("性能配置文件", "performance_config", "--performance-config", "", "配置文件路径"),
            ("待处理路径", "path", "-p", "", "输入待处理文件夹路径"),
        ]

        # 预设配置
        preset_configs = {
            "AVIF-90-inf": {
                "description": "AVIF格式 90质量 无限模式",
                "checkbox_options": ["infinite","clipboard","rename_cbr"],
                "input_values": {
                    "format": "avif",
                    "quality": "90",
                    "interval": "10",
                    "min_width": "0"
                }
            },
            "JXL-CJXL": {  # 添加新的预设
                "description": "JXL格式 CJXL无损转换",
                "checkbox_options": ["clipboard", "jxl_jpeg_lossless"],  # 启用JPEG无损
                "input_values": {
                    "format": "jxl",
                    "quality": "100",  # 无损模式
                    "interval": "10",
                    "min_width": "0"
                }
            },
            "JXL-90": {
                "description": "JXL格式 90质量",
                "checkbox_options": ["clipboard"],
                "input_values": {
                    "format": "jxl",
                    "quality": "90",
                    "interval": "10",
                    "min_width": "0"
                }
            },
            "JXL-75": {
                "description": "JXL格式 75质量",
                "checkbox_options": ["clipboard"],
                "input_values": {
                    "format": "jxl",
                    "quality": "75",
                    "interval": "10",
                    "min_width": "0"
                }
            },
            "AVIF-90-1800": {
                "description": "AVIF格式 90质量 1800宽度过滤",
                "checkbox_options": ["clipboard","rename_cbr"],
                "input_values": {
                    "format": "avif",
                    "quality": "90",
                    "interval": "10",
                    "min_width": "1800"
                }
            },
            "AVIF-90-1800-kw": {
                "description": "AVIF格式 90质量 1800宽度 关键词过滤",
                "checkbox_options": ["keywords","clipboard","rename_cbr"],
                "input_values": {
                    "format": "avif",
                    "quality": "90",
                    "interval": "10",
                    "min_width": "1800"
                }
            }
        }

        # 创建配置界面
        app = create_config_app(
            program=__file__,
            checkbox_options=checkbox_options,
            input_options=input_options,
            title="图片压缩配置",
            preset_configs=preset_configs
        )
        
        app.run()



if __name__ == '__main__':
    main()




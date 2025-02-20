from nodes.config.import_bundles import *

# 导入日志配置
from nodes.logs.logger_config import setup_logger

config = {
    'script_name': 'comic_img_filter',
    'console_enabled': False
}
logger = setup_logger(config)
# 初始化 TextualLoggerManager
HAS_TUI = True
USE_DEBUGGER = False

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
    "file_ops": {  # 新增文件操作面板
        "ratio": 2,
        "title": "📂 文件操作",
        "style": "lightpink"
    },
    "hash_calc": {  # 新增哈希操作面板
        "ratio": 3,
        "title": "🔢 哈希计算",
        "style": "lightblue"
    },
    "update_log": {
        "ratio": 1,
        "title": "🔧 系统消息",
        "style": "lightwhite"
    }
}


# 全局配置
GLOBAL_HASH_CACHE = os.path.expanduser(r"E:\1EHV\image_hashes_global.json")
HASH_COLLECTION_FILE = os.path.expanduser(r"E:\1EHV\image_hashes_collection.json")  # 修改为collection
HASH_FILES_LIST = os.path.expanduser(r"E:\1EHV\hash_files_list.txt")

# TUI布局配置
def initialize_textual_logger():
    """初始化日志布局，确保在所有模式下都能正确初始化"""
    try:
        TextualLoggerManager.set_layout(TEXTUAL_LAYOUT)
        logger.info("[#update_log]✅ 日志系统初始化完成")  # 添加面板标识
    except Exception as e:
        print(f"❌ 日志系统初始化失败: {e}")

class PathManager:
    """
    类描述
    """
    @staticmethod
    def create_temp_directory(file_path):
        """
        为每个压缩包创建唯一的临时目录，使用压缩包原名+时间戳
        
        Args:
            file_path: 源文件路径（压缩包路径）
        """
        original_dir = os.path.dirname(file_path)
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        temp_dir = os.path.join(original_dir, f'{file_name}_{timestamp}')
        os.makedirs(temp_dir, exist_ok=True)
        logger.info( f'[#file_ops]临时目录: {temp_dir}')
        return temp_dir

    @staticmethod
    def cleanup_temp_files(temp_dir, new_zip_path, backup_file_path):
        """清理临时文件和目录，但不处理备份文件"""
        try:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info( f'[#file_ops]已删除临时目录: {temp_dir}')
            if new_zip_path and os.path.exists(new_zip_path):
                os.remove(new_zip_path)
                logger.info( f'[#file_ops]已删除临时压缩包: {new_zip_path}')
            # 不处理备份文件，让BackupHandler.handle_bak_file来处理
        except Exception as e:
            logger.info( f'[#file_ops]❌ 清理临时文件时出错: {e}')

class ImageProcessor:
    """
    类描述
    """
    def __init__(self):
        """初始化图片处理器"""
        self.grayscale_detector = GrayscaleDetector()
        self.global_hashes = {}  # 初始化为空字典
        self.temp_hashes = {}  # 临时存储当前压缩包的哈希值

    def set_global_hashes(self, hashes):
        """设置全局哈希缓存"""
        self.global_hashes = hashes

    @staticmethod
    def calculate_phash(image_path_or_data):
        """使用感知哈希算法计算图片哈希值
        
        Args:
            image_path_or_data: 可以是图片路径(str/Path)或BytesIO对象
            
        Returns:
            str: 16进制格式的感知哈希值，失败时返回None
        """
        try:
            hash_value = ImageHashCalculator.calculate_phash(image_path_or_data)
            if isinstance(image_path_or_data, (str, Path)):
                logger.info( f"[#hash_calc]计算图片哈希值: {os.path.basename(str(image_path_or_data))} -> {hash_value}")
            return hash_value
        except Exception as e:
            logger.info(f"[#hash_calc]计算图片哈希值失败: {e}")
            return None

    def process_images_in_directory(self, temp_dir, params):
        """处理目录中的图片"""
        try:
            # 清空临时哈希存储
            self.temp_hashes.clear()
            
            image_files = ArchiveExtractor.get_image_files(temp_dir)
            if not image_files:
                logger.info( f"⚠️ 未找到图片文件")
                return (set(), set())
            removed_files = set()
            duplicate_files = set()
            lock = threading.Lock()
            existing_file_names = set()
            with ThreadPoolExecutor(max_workers=params['max_workers']) as executor:
                futures = []
                for file_path in image_files:
                    rel_path = os.path.relpath(file_path, os.path.dirname(file_path))
                    future = executor.submit(self.process_single_image, file_path, rel_path, existing_file_names, params, lock)
                    futures.append((future, file_path))
                image_hashes = []
                for future, file_path in futures:
                    try:
                        img_hash, img_data, rel_path, reason = future.result()
                        if reason in ['small_image', 'white_image']:
                            removed_files.add(file_path)
                        elif img_hash is not None:
                            image_hashes.append((img_hash, img_data, file_path, reason))
                    except Exception as e:
                        logger.info( f"❌ 处理图片失败 {file_path}: {e}")
            if params['remove_duplicates'] and image_hashes:
                unique_images, _, removal_reasons = DuplicateDetector.remove_duplicates_in_memory(image_hashes, params)
                processed_files = {img[2] for img in unique_images}
                for img_hash, _, file_path, _ in image_hashes:
                    if file_path not in processed_files:
                        duplicate_files.add(file_path)
                        
                # # 处理完成后，将临时哈希更新到全局哈希
                # if self.temp_hashes:
                #     with lock:
                #         self.global_hashes.update(self.temp_hashes)
                #         logger.info(f"[#hash_calc]已批量添加 {len(self.temp_hashes)} 个哈希到全局缓存")
                #         # 清空临时存储
                #         self.temp_hashes.clear()
                        
            return (removed_files, duplicate_files)
        except Exception as e:
            logger.info( f"❌ 处理目录中的图片时出错: {e}")
            return (set(), set())

    def process_single_image(self, file_path, rel_path, existing_file_names, params, lock): 
        """处理单个图片文件"""
        try:
            if not file_path or not os.path.exists(file_path):
                logger.info(f"[#file_ops]❌ 文件不存在: {file_path}")
                return (None, None, None, 'file_not_found')
                            
            try:
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                    logger.info(f"[#file_ops]📷读图: {file_path}")  # 添加面板标识
            except (IOError, OSError) as e:
                logger.info(f"[#file_ops]❌ 图片文件损坏或无法读取 {rel_path}: {e}")
                return (None, None, None, 'corrupted_image')
            except Exception as e:
                logger.info(f"[#file_ops]❌ 读取文件失败 {rel_path}: {e}")
                return (None, None, None, 'read_error')
                
            if file_path.lower().endswith(('png', 'webp', 'jxl', 'avif', 'jpg', 'jpeg', 'bmp', 'tiff', 'tif', 'heic', 'heif', 'bmp')):
                # === 独立处理步骤 ===
                processed_data = file_data
                removal_reason = None

                # 步骤1: 小图检测 (独立判断)
                if params.get('filter_height_enabled', False):
                    logger.info(f"[#image_processing]🖼️ 正在检测小图: {os.path.basename(file_path)}")
                    processed_data, removal_reason = self.detect_small_image(processed_data, params)
                    if removal_reason:
                        return (None, file_data, file_path, removal_reason)

                # 步骤2: 白图检测 (独立判断)
                if params.get('remove_grayscale', False):
                    logger.info(f"[#image_processing]🎨 正在检测白图: {os.path.basename(file_path)}")
                    processed_data, removal_reason = self.detect_grayscale_image(processed_data)
                    if removal_reason:
                        return (None, file_data, file_path, removal_reason)

                # 步骤3: 重复检测 - 直接计算哈希,不检查全局匹配
                if params.get('remove_duplicates', False):
                    img_hash = self.handle_duplicate_detection(file_path, rel_path, params, lock, processed_data)
                    if not img_hash:
                        return (None, file_data, file_path, 'hash_error')
                    return (img_hash, file_data, file_path, None)

                return (None, file_data, file_path, None)
            else:
                return (None, file_data, file_path, 'non_image_file')
        except Exception as e:
            logger.info(f"[#file_ops]❌ 处理文件时出错 {rel_path}: {e}")
            return (None, None, None, 'processing_error')

       # 修改后的独立小图检测方法
    def detect_small_image(self, image_data, params):
        """独立的小图检测"""
        try:
            # 如果是PIL图像对象，先转换为字节数据
            if isinstance(image_data, Image.Image):
                img_byte_arr = BytesIO()
                image_data.save(img_byte_arr, format=image_data.format)
                img_data = img_byte_arr.getvalue()
            else:
                img_data = image_data
                
            img = Image.open(BytesIO(img_data))
            width, height = img.size
            if height < params.get('min_size', 631):
                logger.info(f"[#image_processing]🖼️ 图片尺寸: {width}x{height} 小于最小尺寸")
                return None, 'small_image'
            logger.info(f"[#image_processing]🖼️ 图片尺寸: {width}x{height} 大于最小尺寸")
            return img_data, None
        except Exception as e:
            return None, 'size_detection_error'

    def detect_grayscale_image(self, image_data):
        """独立的白图检测"""
        white_keywords = ['pure_white', 'white', 'pure_black', 'grayscale']
        try:
            result = self.grayscale_detector.analyze_image(image_data)
            if result is None:
                logger.info( f"灰度分析返回None")
                return (None, 'grayscale_detection_error')
                
            # 详细记录分析结果
            # logger.info( f"灰度分析结果: {result}")
            
            if hasattr(result, 'removal_reason') and result.removal_reason:
                logger.info( f"检测到移除原因: {result.removal_reason}")
                
                # 检查是否匹配任何关键字
                matched_keywords = [keyword for keyword in white_keywords 
                                  if keyword in result.removal_reason]
                if matched_keywords:
                    logger.info( f"匹配到白图关键字: {matched_keywords}")
                    return (None, 'white_image')
                    
                # 如果有removal_reason但不匹配关键字，记录这种情况
                logger.info( f"未匹配关键字的移除原因: {result.removal_reason}")
                return (None, result.removal_reason)
                
            return (image_data, None)
            
        except ValueError as ve:
            logger.info( f"灰度检测发生ValueError: {str(ve)}")
            return (None, 'grayscale_detection_error')
        except Exception as e:
            logger.info( f"灰度检测发生错误: {str(e)}")
            return None, 'grayscale_detection_error'

    def handle_duplicate_detection(self, file_path, rel_path, params, lock, image_data):
        """处理重复检测 - 只计算哈希"""
        try:
            # 计算新的哈希值
            img_hash = ImageHashCalculator.calculate_phash(image_data)
            if img_hash:
                # 获取压缩包路径并构建URI
                zip_path = params.get('zip_path')
                if zip_path:
                    img_uri = PathURIGenerator.generate(f"{zip_path}!{rel_path}")
                    # 添加哈希操作面板标识
                    logger.info(f"[#hash_calc]计算哈希值: {img_uri} -> {img_hash['hash']}")  
            return img_hash
            
        except Exception as e:
            # 错误日志也指向哈希操作面板
            logger.info(f"[#hash_calc]❌ 计算哈希值失败: {str(e)}")  
            return None

class DuplicateDetector:
    """
    类描述
    """
    @staticmethod
    def _compare_with_reference_hashes(image_hashes, ref_hashes, hash_to_uri, params):
        """与参考哈希进行比较的公共逻辑"""
        remaining_images = []
        hash_duplicates = 0
        removal_reasons = {}

        for i, (hash1, img_data1, file_path1, reason) in enumerate(image_hashes):
            if hash1 is None:
                continue

            # 与参考哈希值比较
            found, similar_hash, similar_uri = HashFileHandler.find_similar_hash(
                hash1, ref_hashes, hash_to_uri, params['ref_hamming_distance']
            )

            if found:
                hash_duplicates += 1
                StatisticsManager.update_counts(hash_duplicates=1)
                removal_reasons[file_path1] = 'hash_duplicate'

                # 记录相似性
                hamming_distance = ImageHashCalculator.calculate_hamming_distance(hash1, similar_hash)
                # 添加哈希操作面板标识
                logger.info(f"[#hash_calc]汉明距离: {hamming_distance}<{params['ref_hamming_distance']}")  
                HashFileHandler.record_similarity(file_path1, similar_uri, hamming_distance)
                # 使用新的日志格式
                logger.info(f"[#hash_calc]处理文件: {os.path.basename(file_path1)}")
                logger.info(f"[#hash_calc]发现哈希重复，将删除: {os.path.basename(file_path1)}")  # 修改面板标识
            else:
                remaining_images.append((hash1, img_data1, file_path1, reason))

        return remaining_images, hash_duplicates, removal_reasons

    @staticmethod
    def _process_internal_duplicates(remaining_images, hamming_threshold, removal_reasons):  # 添加removal_reasons参数
        """处理内部重复的公共逻辑"""
        final_images = []
        processed_indices = set()
        normal_duplicates = 0
        internal_removal_reasons = {}  # 新增内部removal_reasons

        # 构建内部哈希集合
        internal_hashes = []
        hash_to_image = {}
        for i, (hash1, img_data1, file_path1, reason) in enumerate(remaining_images):
            # 统一哈希格式为字符串
            hash_str = hash1['hash'] if isinstance(hash1, dict) else hash1
            internal_hashes.append(hash_str)
            hash_to_image[hash_str] = (i, img_data1, file_path1, reason)

        # 对哈希值进行排序
        internal_hashes.sort()

        # 对每个图片进行比较
        for i, (hash1, img_data1, file_path1, reason) in enumerate(remaining_images):
            if i in processed_indices:
                continue
            
            # 统一哈希格式为字符串 第一个哈希值是字典格式（因为是新计算的），而其他的是字符串格式（因为是从缓存加载的）。
            hash_str = hash1['hash'] if isinstance(hash1, dict) else hash1
            logger.info(f"[#cur_progress]分析文件: {os.path.basename(file_path1)}")
            similar_images = [(i, hash_str, img_data1, file_path1)]  # 使用统一的hash_str
            target_int = int(hash_str, 16)  # 使用统一的hash_str
            max_diff = 2 ** hamming_threshold

            # 遍历所有哈希值进行比较
            for current_hash in internal_hashes:
                if current_hash == hash_str:  # 使用统一的hash_str比较
                    continue

                current_idx, current_data, current_path, current_reason = hash_to_image[current_hash]
                if current_idx in processed_indices:
                    continue

                hamming_distance = ImageHashCalculator.calculate_hamming_distance(hash_str, current_hash)  # 使用统一的hash_str
                if hamming_distance <= hamming_threshold:
                    similar_images.append((current_idx, current_hash, current_data, current_path))  # 移除current_reason

            # 处理相似图片组
            if len(similar_images) > 1:
                image_sizes = []
                for sim_img in similar_images:
                    idx, hash_val, img_data, file_path = sim_img  # 现在所有元组都是4元组
                    image_sizes.append((len(img_data), idx, img_data, file_path))
                
                image_sizes.sort(reverse=True)

                kept_idx = image_sizes[0][1]
                kept_image = next(x for x in similar_images if x[0] == kept_idx)
                final_images.append(remaining_images[kept_idx])
                processed_indices.add(kept_idx)

                # 记录相似性关系
                for size, idx, _, file_path in image_sizes[1:]:
                    processed_indices.add(idx)
                    normal_duplicates += 1
                    StatisticsManager.update_counts(normal_duplicates=1)
                    
                    # 获取要比较的两个哈希值
                    current_hash = remaining_images[idx][0]
                    kept_hash = remaining_images[kept_idx][0]
                    
                    # 统一转换为字符串格式
                    current_hash_str = current_hash['hash'] if isinstance(current_hash, dict) else current_hash
                    kept_hash_str = kept_hash['hash'] if isinstance(kept_hash, dict) else kept_hash
                    
                    # 计算汉明距离
                    hamming_distance = ImageHashCalculator.calculate_hamming_distance(
                        current_hash_str,
                        kept_hash_str
                    )
                    
                    HashFileHandler.record_similarity(file_path, kept_image[3], hamming_distance)
                    internal_removal_reasons[file_path] = 'normal_duplicate'
                    logger.info(f"[#hash_calc]发现重复图片，将删除: {os.path.basename(file_path)}, 距离: {hamming_distance}")  
                    logger.info(f"[#hash_calc]重复详情 - 源: {os.path.basename(kept_image[3])}, 距离: {hamming_distance}")
            else:
                final_images.append((hash1, img_data1, file_path1, reason))
                processed_indices.add(i)

        # 更新主removal_reasons
        removal_reasons.update(internal_removal_reasons)
        return final_images, normal_duplicates, internal_removal_reasons

    @staticmethod
    def remove_duplicates_in_memory(image_hashes, params):
        """处理重复图片"""
        unique_images = []
        hash_duplicates = 0
        normal_duplicates = 0
        skipped_images = {'hash_error': 0, 'small_images': 0, 'white_images': 0}
        removal_reasons = {}  # 初始化removal_reasons字典

        # 预处理：统计跳过的图片
        for img in image_hashes:
            if img[3] == 'small_image':
                skipped_images['small_images'] += 1
                StatisticsManager.update_counts(small_images=1)
                removal_reasons[img[2]] = 'small_image'
            elif img[3] == 'white_image':
                skipped_images['white_images'] += 1
                StatisticsManager.update_counts(white_images=1)
                removal_reasons[img[2]] = 'white_image'
            elif img[0] is None:
                skipped_images['hash_error'] += 1

        # 记录统计信息
        StatisticsManager.update_counts(
            hash_duplicates=hash_duplicates,
            normal_duplicates=normal_duplicates,
            small_images=skipped_images['small_images'],
            white_images=skipped_images['white_images']
        )

        # 加载外部哈希文件
        ref_hashes, hash_to_uri = HashFileHandler.load_hash_file(params.get('hash_file'))

        # 第一步：与参考哈希比较（仅当提供了哈希文件时）
        remaining_images = image_hashes
        hash_reasons = {}
        if ref_hashes:
            logger.info(f"[#hash_calc]开始处理外部哈希文件，长度: {len(ref_hashes)}")
            remaining_images, hash_duplicates, hash_reasons = DuplicateDetector._compare_with_reference_hashes(
                image_hashes, ref_hashes, hash_to_uri, params
            )
            removal_reasons.update(hash_reasons)

        # 第二步：处理内部重复
        # 没有哈希文件时,或者有哈希文件且启用了自身去重时,进行内部去重
        if not ref_hashes or params.get('self_redup', False):
            # 使用hamming_distance进行内部去重
            internal_hamming_distance = params['hamming_distance']
            logger.info(f"[#hash_calc]开始处理内部重复图片 (使用hamming_distance: {internal_hamming_distance})")
            final_images, normal_duplicates, internal_reasons = DuplicateDetector._process_internal_duplicates(
                remaining_images, 
                internal_hamming_distance,
                removal_reasons
            )
            removal_reasons.update(internal_reasons)
        else:
            final_images = [(h, d, p, r) for h, d, p, r in remaining_images]

        # 记录日志
        logger.info( f'总共删除哈希重复图片: {hash_duplicates}')
        logger.info( f'总共删除普通重复图片: {normal_duplicates}')
        logger.info( f"总共删除小图: {skipped_images['small_images']}")
        logger.info( f"总共删除白图: {skipped_images['white_images']}")
        logger.info( f"总共跳过哈希错误: {skipped_images['hash_error']}")

        return (final_images, skipped_images, removal_reasons)

class DirectoryHandler:
    """
    类描述
    """
    @staticmethod
    def remove_empty_directories(path, exclude_keywords=[]):
        """
        删除指定路径下的所有空文件夹
        
        Args:
            path (str): 目标路径
            exclude_keywords (list): 排除关键词列表
        """
        removed_count = 0
        for root, dirs, _ in os.walk(path, topdown=False):
            if any((keyword in root for keyword in exclude_keywords)):
                continue
            for dir_name in dirs:
                folder_path = os.path.join(root, dir_name)
                try:
                    if not os.listdir(folder_path):
                        os.rmdir(folder_path)
                        removed_count += 1
                        logger.info(f'[#file_ops]已删除空文件夹: {folder_path}')
                except Exception as e:
                    logger.info( f"❌ 删除空文件夹失败 {folder_path}: {e}")
        if removed_count > 0:
            logger.info( f'共删除 {removed_count} 个空文件夹')
        return removed_count

class ArchiveExtractor:
    """
    类描述
    """
    @staticmethod
    def get_image_files(directory):
        """获取目录中的所有图片文件"""
        image_files = []
        image_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.jxl', '.avif', '.bmp')
        
        for root, _, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(image_extensions):
                    image_files.append(os.path.join(root, file))
                    
        return image_files



    @staticmethod
    def prepare_archive(file_path):
        """准备压缩包处理环境"""
        temp_dir = PathManager.create_temp_directory(file_path)
        backup_file_path = file_path + '.bak'
        new_zip_path = os.path.join(os.path.dirname(file_path), f'{os.path.splitext(os.path.basename(file_path))[0]}.new.zip')
        try:
            shutil.copy(file_path, backup_file_path)
            logger.info( f'创建备份: {backup_file_path}')
            cmd = ['7z', 'x', file_path, f'-o{temp_dir}', '-y']
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.info( f"❌ 解压失败: {file_path}\n错误: {result.stderr}")
                PathManager.cleanup_temp_files(temp_dir, new_zip_path, backup_file_path)
                return (None, None, None)
            return (temp_dir, backup_file_path, new_zip_path)
        except Exception as e:
            logger.info( f"❌ 准备环境失败 {file_path}: {e}")
            PathManager.cleanup_temp_files(temp_dir, new_zip_path, backup_file_path)
            return (None, None, None)

class ArchiveCompressor:
    """
    类描述
    """
    @staticmethod
    def run_7z_command(command, zip_path, operation='', additional_args=None):
        """
        执7z命令的通函数
        
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
                logger.info( f'成功执行7z {operation}: {zip_path}')
                return (True, result.stdout)
            else:
                logger.info( f"❌ 7z {operation}失败: {zip_path}\n错误: {result.stderr}")
                return (False, result.stderr)
        except Exception as e:
            logger.info( f"❌ 执行7z命令出错: {e}")
            return (False, str(e))



class ArchiveProcessor:
    """
    类描述
    """
    @staticmethod
    def merge_archives(paths, params):
        """
        合并压缩包为一个临时压缩包进行处理
        
        Args:
            paths: 压缩包路径列表或文件夹路径列表
            params: 参数字典
        
        Returns:
            (temp_dir, merged_zip_path, archive_paths): 临时目录、合并后的压缩包路径和原始压缩包路径列表
        """
        temp_dir = None
        try:
            archive_paths = []
            for path in paths:
                if os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        archive_paths.extend((os.path.join(root, file) for file in files if file.lower().endswith('.zip')))
                elif path.lower().endswith('.zip'):
                    archive_paths.append(path)

            # 新增备份步骤：为每个要合并的压缩包创建备份
            for zip_path in archive_paths:
                backup_path = zip_path + '.bak'
                try:
                    if not os.path.exists(backup_path):
                        shutil.copy2(zip_path, backup_path)
                        logger.info(f"[#file_ops]已创建合并前备份: {backup_path}")
                except Exception as e:
                    logger.error(f"[#file_ops]创建合并前备份失败 {zip_path}: {e}")

            if not archive_paths:
                logger.info( f"❌ 没有找到要处理的压缩包")
                return (None, None, None)
                
            directories = {os.path.dirname(path) for path in archive_paths}
            if len(directories) > 1:
                logger.info( f"❌ 所选压缩包不在同一目录")
                return (None, None, None)
            base_dir = list(directories)[0]
            timestamp = int(time.time() * 1000)
            temp_dir = os.path.join(base_dir, f'temp_merge_{timestamp}')
            os.makedirs(temp_dir, exist_ok=True)
            for zip_path in archive_paths:
                logger.info( f'解压: {zip_path}')
                archive_name = os.path.splitext(os.path.basename(zip_path))[0]
                archive_temp_dir = os.path.join(temp_dir, archive_name)
                os.makedirs(archive_temp_dir, exist_ok=True)
                success, error = ArchiveCompressor.run_7z_command('x', zip_path, '解压文件', [f'-o{archive_temp_dir}', '-y'])
                if not success:
                    logger.info( f"❌ 解压失败: {zip_path}\n错误: {error}")
                    PathManager.cleanup_temp_files(temp_dir, None, None)
                    return (None, None, None)
            merged_zip_path = os.path.join(base_dir, f'merged_{timestamp}.zip')
            logger.info( '创建合并压缩包')
            success, error = ArchiveCompressor.run_7z_command('a', merged_zip_path, '创建合并压缩包', ['-tzip', os.path.join(temp_dir, '*')])
            if not success:
                logger.info( f"❌ 创建合并压缩包失败: {error}")
                PathManager.cleanup_temp_files(temp_dir, None, None)
                return (None, None, None)
            return (temp_dir, merged_zip_path, archive_paths)
        except Exception as e:
            logger.info( f"❌ 合并压缩包时出错: {e}")
            if temp_dir and os.path.exists(temp_dir):
                PathManager.cleanup_temp_files(temp_dir, None, None)
            return (None, None, None)

    @staticmethod
    def process_single_archive(file_path, params):
        """处理单个压缩包文件"""
        try:
            logger.info( f"开始处理文件: {file_path}")
            
            if not os.path.exists(file_path):
                logger.info( f"❌ 文件不存在: {file_path}")
                return []
                
            cmd = ['7z', 'l', file_path]
            result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                logger.info( f"❌ 压缩包可能损坏: {file_path}")
                return []
                
            if result.stdout is None:
                logger.info( f"❌ 无法读取压缩包内容: {file_path}")
                return []
                
            has_images = any((line.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.jxl', '.avif', '.jxl')) 
                            for line in result.stdout.splitlines()))
            if not has_images:
                logger.info( f"⚠️ 跳过无图片的压缩包: {file_path}")
                return []
            processed_archives = []
            if not params['ignore_processed_log']:
                if ProcessedLogHandler.has_processed_log(file_path):
                    logger.info( f"⚠️ 文件已有处理记录: {file_path}")
                    return processed_archives
                    
            logger.info( "开始处理压缩包内容...")
            processed_archives.extend(ArchiveProcessor.process_archive_in_memory(file_path, params))
            
            if processed_archives:
                # 更新重复信息面板
                info = processed_archives[-1]
                logger.info( 
                    f"处理结果:\n"
                    f"- 哈希重复: {info.get('hash_duplicates_removed', 0)} 张\n"
                    f"- 普通重复: {info.get('normal_duplicates_removed', 0)} 张\n"
                    f"- 小图: {info.get('small_images_removed', 0)} 张\n"
                    f"- 白图: {info.get('white_images_removed', 0)} 张\n"
                    f"- 减少大小: {info['size_reduction_mb']:.2f} MB"
                )
                
                # 更新进度面板
                logger.info( f"✅ 成功处理: {os.path.basename(file_path)}")
                
                    
                if params['add_processed_log_enabled']:
                    processed_info = {
                        'hash_duplicates_removed': info.get('hash_duplicates_removed', 0),
                        'normal_duplicates_removed': info.get('normal_duplicates_removed', 0),
                        'small_images_removed': info.get('small_images_removed', 0),
                        'white_images_removed': info.get('white_images_removed', 0)
                    }
                    ProcessedLogHandler.add_processed_log(file_path, processed_info)
                    logger.info( "已添加处理日志")
            else:
                logger.info( f"⚠️ 压缩包处理完成，但没有需要处理的内容: {file_path}")
                
            backup_file_path = file_path + '.bak'
            if os.path.exists(backup_file_path):
                BackupHandler.handle_bak_file(backup_file_path, params)
                logger.info( "已处理备份文件")
                
            return processed_archives
            
        except UnicodeDecodeError as e:
            logger.info( f"❌ 处理压缩包时出现编码错误 {file_path}: {e}")
            return []
        except Exception as e:
            logger.info( f"❌ 处理文件时发生异常: {file_path}\n{str(e)}")
            return []

    @staticmethod
    def split_merged_archive(processed_zip, original_archives, temp_dir, params):
        """
        将处理后的合并压缩包拆分回原始压缩包
        
        Args:
            processed_zip: 处理后的合并压缩包路径
            original_archives: 原始压缩包路径列表
            temp_dir: 临时目录路径
            params: 参数字典
        """
        try:
            logger.info( '开始拆分处理后的压缩包')
            extract_dir = os.path.join(temp_dir, 'processed')
            os.makedirs(extract_dir, exist_ok=True)
            success, error = ArchiveCompressor.run_7z_command('x', processed_zip, '解压处理后的压缩包', [f'-o{extract_dir}', '-y'])
            if not success:
                logger.info( f"❌ 解压处理后的压缩包失败: {error}")
                return False
            for original_zip in original_archives:
                archive_name = os.path.splitext(os.path.basename(original_zip))[0]
                source_dir = os.path.join(extract_dir, archive_name)
                if not os.path.exists(source_dir):
                    logger.info( f"⚠️ 找不到对应的目录: {source_dir}")
                    continue
                new_zip = original_zip + '.new'
                success, error = ArchiveCompressor.run_7z_command('a', new_zip, '创建新压缩包', ['-tzip', os.path.join(source_dir, '*')])
                if success:
                    try:
                        if params.get('backup_removed_files_enabled', True):
                            send2trash(original_zip)
                        else:
                            os.remove(original_zip)
                        os.rename(new_zip, original_zip)
                        logger.info( f'成功更新压缩包: {original_zip}')
                    except Exception as e:
                        logger.info( f"❌ 替换压缩包失败 {original_zip}: {e}")
                else:
                    logger.info( f"❌ 创建新压缩包失败 {new_zip}: {error}")
            return True
        except Exception as e:
            logger.info( f"❌ 拆分压缩包时出错: {e}")
            return False

    @staticmethod
    def handle_size_comparison(file_path, new_zip_path, backup_file_path):
        """
        比较新旧文件大小并处理替换
        
        Args:
            file_path: 原始文件路径
            new_zip_path: 新压缩包路径
            backup_file_path: 备份文件路径
        
        Returns:
            (success, size_change): 处理是否成功和文件大小变化(MB)
        """
        try:
            if not os.path.exists(new_zip_path):
                logger.info( f"❌ 新压缩包不存在: {new_zip_path}")
                return (False, 0)
            original_size = os.path.getsize(file_path)
            new_size = os.path.getsize(new_zip_path)
            REDUNDANCY_SIZE = 1 * 1024 * 1024
            if new_size >= original_size + REDUNDANCY_SIZE:
                logger.info( f"⚠️ 新压缩包 ({new_size / 1024 / 1024:.2f}MB) 未比原始文件 ({original_size / 1024 / 1024:.2f}MB) 小超过1MB，还原备份")
                os.remove(new_zip_path)
                if os.path.exists(backup_file_path):
                    os.replace(backup_file_path, file_path)
                return (False, 0)
            os.replace(new_zip_path, file_path)
            size_change = (original_size - new_size) / (1024 * 1024)
            logger.info( f'更新压缩包: {file_path} (减少 {size_change:.2f}MB)')
            return (True, size_change)
        except Exception as e:
            logger.info( f"❌ 比较文件大小时出错: {e}")
            if os.path.exists(backup_file_path):
                os.replace(backup_file_path, file_path)
            if os.path.exists(new_zip_path):
                os.remove(new_zip_path)
            return (False, 0)

    @staticmethod
    def process_archive_in_memory(file_path, params):
        """处理单个压缩包的主函数"""
        processed_archives = []
        temp_dir = None
        backup_file_path = None
        new_zip_path = None
        try:
            logger.info(f"[#file_ops]开始处理压缩包: {file_path}")

            temp_dir, backup_file_path, new_zip_path = ArchiveExtractor.prepare_archive(file_path)
            if not temp_dir:
                logger.info(f"[#file_ops]❌ 准备环境失败: {file_path}")
                return []
                
            logger.info(f"[#file_ops]环境准备完成")
            
            image_files = ArchiveExtractor.get_image_files(temp_dir)
            if not image_files:
                logger.info(f"[#file_ops]⚠️ 未找到图片文件")
                PathManager.cleanup_temp_files(temp_dir, new_zip_path, backup_file_path)
                return []
                
            
            removed_files = set()
            duplicate_files = set()
            removal_reasons = {}  # 初始化removal_reasons
            lock = threading.Lock()
            existing_file_names = set()
            image_processor = ImageProcessor()
            # image_processor.set_global_hashes(global_hashes)  # 设置全局哈希
            
            # 添加zip_path到params
            params['zip_path'] = file_path
            
            # 在处理图片时显示进度
            with ThreadPoolExecutor(max_workers=params['max_workers']) as executor:
                futures = []
                total_files = len(image_files)
                processed_files = 0
                
                for img_path in image_files:
                    rel_path = os.path.relpath(img_path, temp_dir)
                    future = executor.submit(
                        image_processor.process_single_image, 
                        img_path, 
                        rel_path, 
                        existing_file_names, 
                        params, 
                        lock
                    )
                    futures.append((future, img_path))
                    
                image_hashes = []
                for future, img_path in futures:
                    try:
                        img_hash, img_data, _, reason = future.result()
                        processed_files += 1
                        percentage = (processed_files / total_files) * 100
                        logger.info(f"[@cur_progress] 处理图片 ({processed_files}/{total_files}) {percentage:.1f}%")
                        
                        if reason in ['small_image', 'white_image']:
                            removed_files.add(img_path)
                            removal_reasons[img_path] = reason
                        elif img_hash is not None and params['remove_duplicates']:
                            image_hashes.append((img_hash, img_data, img_path, reason))
                            
                    except Exception as e:
                        logger.info(f"[#hash_calc]❌ 处理图片失败 {img_path}: {e}")
                        processed_files += 1
                        percentage = (processed_files / total_files) * 100
                        logger.info(f"[@hash_calc] 处理图片 ({processed_files}/{total_files}) {percentage:.1f}%")

            if params['remove_duplicates'] and image_hashes:
                unique_images, _, dup_removal_reasons = DuplicateDetector.remove_duplicates_in_memory(image_hashes, params)
                removal_reasons.update(dup_removal_reasons)  # 合并删除原因
                processed_files = {img[2] for img in unique_images}
                for img_hash, _, img_path, _ in image_hashes:
                    if img_path not in processed_files:
                        duplicate_files.add(img_path)
                        
                # 处理完成后，将临时哈希更新到全局哈希
                # if image_processor.temp_hashes:
                #     with lock:
                #         global_hashes.update(image_processor.temp_hashes)
                #         logger.info(f"[#hash_calc]已批量添加 {len(image_processor.temp_hashes)} 个哈希到全局缓存")
                #         # 清空临时存储
                #         image_processor.temp_hashes.clear()

            # 保存更新后的缓存
            # ImageHashCalculator.save_global_hashes(global_hashes)  # 注释掉原来的全局保存
            
            # 为当前压缩包保存哈希文件
            zip_path = params.get('zip_path')
            if zip_path:
                zip_dir = os.path.dirname(zip_path)
                zip_name = os.path.splitext(os.path.basename(zip_path))[0]                
                # 构建压缩包特定的哈希字典
                zip_hashes = {}
                for img_hash, _, img_path, _ in image_hashes:
                    if img_hash:
                        rel_path = os.path.relpath(img_path, temp_dir)
                        img_uri = PathURIGenerator.generate(f"{zip_path}!{rel_path}")
                        # 统一哈希值格式：如果是字典则提取hash字段
                        hash_value = img_hash['hash'] if isinstance(img_hash, dict) else img_hash
                        zip_hashes[img_uri] = {"hash": hash_value}  # 直接存储为新格式
                
                # 保存到collection文件
                try:
                    # 确保目录存在
                    os.makedirs(os.path.dirname(HASH_COLLECTION_FILE), exist_ok=True)
                    
                    # 读取现有collection
                    collection_data = {
                        "_hash_params": "hash_size=10;hash_version=1",
                        "dry_run": False,
                        "hashes": {}
                    }
                    
                    if os.path.exists(HASH_COLLECTION_FILE):
                        try:
                            with open(HASH_COLLECTION_FILE, 'r', encoding='utf-8') as f:
                                file_content = f.read().strip()
                                if not file_content:  # 文件为空
                                    logger.info(f"[#hash_calc]Collection文件为空，将创建新文件")
                                    collection_data = {
                                        "_hash_params": "hash_size=10;hash_version=1",
                                        "dry_run": False,
                                        "hashes": {}
                                    }
                                else:
                                    try:
                                        loaded_data = json.loads(file_content)
                                        if not isinstance(loaded_data, dict):
                                            raise ValueError("JSON数据格式不正确，不是字典格式")
                                            
                                        # 保留原有的元数据
                                        collection_data = {
                                            "_hash_params": loaded_data.get("_hash_params", "hash_size=10;hash_version=1"),
                                            "dry_run": loaded_data.get("dry_run", False),
                                            "hashes": {}
                                        }
                                        
                                        # 处理哈希数据
                                        if "hashes" in loaded_data and isinstance(loaded_data["hashes"], dict):
                                            collection_data["hashes"] = loaded_data["hashes"]
                                        else:
                                            # 尝试处理旧格式
                                            for uri, hash_value in loaded_data.items():
                                                if uri not in ["_hash_params", "dry_run"]:
                                                    if isinstance(hash_value, str):
                                                        collection_data["hashes"][uri] = {"hash": hash_value}
                                                    elif isinstance(hash_value, dict) and "hash" in hash_value:
                                                        collection_data["hashes"][uri] = hash_value
                                                        
                                        logger.info(f"[#hash_calc]成功读取Collection文件，包含 {len(collection_data['hashes'])} 个哈希值")
                                        
                                    except json.JSONDecodeError as je:
                                        # 检查文件内容，输出更详细的错误信息
                                        logger.error(f"[#hash_calc]JSON解析错误: {str(je)}")
                                        logger.error(f"[#hash_calc]文件内容预览: {file_content[:200]}...")
                                        raise  # 重新抛出异常，让外层处理
                                        
                        except (json.JSONDecodeError, ValueError) as e:
                            # 只有在确实是JSON格式错误时才创建备份
                            error_time = int(time.time())
                            backup_path = f"{HASH_COLLECTION_FILE}.error_{error_time}"
                            shutil.copy2(HASH_COLLECTION_FILE, backup_path)
                            logger.error(f"[#hash_calc]Collection文件格式错误，已备份到: {backup_path}")
                            logger.error(f"[#hash_calc]错误详情: {str(e)}")
                            # 创建新的collection数据结构
                            collection_data = {
                                "_hash_params": "hash_size=10;hash_version=1",
                                "dry_run": False,
                                "hashes": {}
                            }
                        except Exception as e:
                            logger.error(f"[#hash_calc]读取Collection文件时发生未知错误: {str(e)}")
                            raise  # 对于其他类型的错误，向上抛出
                    else:
                        logger.info(f"[#hash_calc]Collection文件不存在，将创建新文件")
                    
                    # 更新collection（合并新的哈希值）
                    collection_data["hashes"].update(zip_hashes)
                    
                    # 在写入之前验证数据结构
                    if not isinstance(collection_data, dict) or "hashes" not in collection_data:
                        raise ValueError("Collection数据结构无效")
                    
                    # 保存更新后的collection
                    temp_file = f"{HASH_COLLECTION_FILE}.temp"
                    try:
                        with open(temp_file, 'w', encoding='utf-8') as f:
                            json.dump(collection_data, f, ensure_ascii=False, indent=2)
                        # 如果写入成功，替换原文件
                        os.replace(temp_file, HASH_COLLECTION_FILE)
                        logger.info(f"[#hash_calc]已更新 {len(zip_hashes)} 个哈希到collection文件")
                    except Exception as e:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                        raise
                except Exception as e:
                    logger.error(f"[#file_ops]保存collection文件失败: {str(e)}")
                    # 尝试备份损坏的文件
                    if os.path.exists(HASH_COLLECTION_FILE):
                        backup_path = HASH_COLLECTION_FILE + '.bak'
                        try:
                            shutil.copy2(HASH_COLLECTION_FILE, backup_path)
                            logger.info(f"[#hash_calc]已备份可能损坏的collection文件到: {backup_path}")
                        except Exception as backup_error:
                            logger.error(f"[#hash_calc]备份collection文件失败: {str(backup_error)}")
            
            if not ArchiveProcessor.cleanup_and_compress(temp_dir, removed_files, duplicate_files, new_zip_path, params, removal_reasons):
                logger.info( f"❌ 清理和压缩失败: {file_path}")
                if os.path.exists(backup_file_path):
                    os.replace(backup_file_path, file_path)
                return []
            if not os.path.exists(new_zip_path):
                logger.info( f"❌ 新压缩包不存在: {new_zip_path}")
                if os.path.exists(backup_file_path):
                    os.replace(backup_file_path, file_path)
                return []
            original_size = os.path.getsize(file_path)
            new_size = os.path.getsize(new_zip_path)
            REDUNDANCY_SIZE = 1 * 1024 * 1024
            if new_size >= original_size + REDUNDANCY_SIZE:
                logger.info( f"⚠️ 新压缩包 ({new_size / 1024 / 1024:.2f}MB) 不小于原始文件 ({original_size / 1024 / 1024:.2f}MB)，还原备份")
                os.remove(new_zip_path)
                if os.path.exists(backup_file_path):
                    os.replace(backup_file_path, file_path)
                return []
            # 替换原始文件
            os.replace(new_zip_path, file_path)
            # 让 BackupHandler.handle_bak_file 来处理备份文件，不在这里直接删除
            BackupHandler.handle_bak_file(backup_file_path, params)
            
            result = {
                'file_path': file_path,
                'hash_duplicates_removed': len([f for f in duplicate_files if removal_reasons.get(f) == 'hash_duplicate']),
                'normal_duplicates_removed': len([f for f in duplicate_files if removal_reasons.get(f) == 'normal_duplicate']),
                'small_images_removed': len([f for f in removed_files if removal_reasons.get(f) == 'small_image']),
                'white_images_removed': len([f for f in removed_files if removal_reasons.get(f) == 'white_image']),
                'size_reduction_mb': (original_size - new_size) / (1024 * 1024)
            }
            processed_archives.append(result)
        except Exception as e:
            logger.info( f"❌ 处理压缩包时出错 {file_path}: {e}")
            if backup_file_path and os.path.exists(backup_file_path):
                os.replace(backup_file_path, file_path)
            return []
        finally:
            PathManager.cleanup_temp_files(temp_dir, new_zip_path, backup_file_path)
        return processed_archives

    @staticmethod
    def cleanup_and_compress(temp_dir, removed_files, duplicate_files, new_zip_path, params, removal_reasons):
        """清理文件并创建新压缩包"""
        try:
            if removed_files is None:
                removed_files = set()
            if duplicate_files is None:
                duplicate_files = set()
            if not isinstance(removed_files, set) or not isinstance(duplicate_files, set):
                logger.info( f"❌ 无效的参数类型: removed_files={type(removed_files)}, duplicate_files={type(duplicate_files)}")
                return False
            BackupHandler.backup_removed_files(new_zip_path, removed_files, duplicate_files, params, removal_reasons)
            all_files_to_remove = removed_files | duplicate_files
            removed_count = 0
            for file_path in all_files_to_remove:
                try:
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                        removed_count += 1
                        logger.info( f'已删除文件: {file_path}')
                except Exception as e:
                    logger.info( f"❌ 删除文件失败 {file_path}: {e}")
                    continue
            if removed_count > 0:
                logger.info( f'已删除 {removed_count} 个文件')
            empty_dirs_removed = DirectoryHandler.remove_empty_directories(temp_dir)
            if empty_dirs_removed > 0:
                logger.info( f'已删除 {empty_dirs_removed} 个空文件夹')
            if not os.path.exists(temp_dir) or not any(os.scandir(temp_dir)):
                logger.info( f'临时目录为空或不存在: {temp_dir}')
                temp_empty_file = os.path.join(temp_dir, '.empty')
                os.makedirs(temp_dir, exist_ok=True)
                with open(temp_empty_file, 'w') as f:
                    pass
                success, error = ArchiveCompressor.run_7z_command('a', new_zip_path, '创建空压缩包', ['-tzip', temp_empty_file])
                os.remove(temp_empty_file)
                if success and os.path.exists(new_zip_path):
                    logger.info( f'成功创建空压缩包: {new_zip_path}')
                    return True
                else:
                    logger.info( f"❌ 创建空压缩包失败: {error}")
                    return False
            success, error = ArchiveCompressor.run_7z_command('a', new_zip_path, '创建新压缩包', ['-tzip', os.path.join(temp_dir, '*')])
            if success:
                if not os.path.exists(new_zip_path):
                    logger.info( f"❌ 压缩包创建失败: {new_zip_path}")
                    return False
                logger.info( f'成功创建新压缩包: {new_zip_path}')
                return True
            else:
                logger.info( f"❌ 创建压缩包失败: {error}")
                return False
        except Exception as e:
            logger.info( f"❌ 清理和压缩时出错: {e}")
            return False

class ProcessedLogHandler:
    """
    类描述
    """
    @staticmethod
    def has_processed_log(zip_path):
        command = ['7z', 'l', zip_path]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            if 'processed.log' in result.stdout:
                ProcessedLogHandler.save_processed_file(zip_path)
                return True
        else:
            logger.info( f"❌ Failed to list contents of {zip_path}: {result.stderr}")
        return False

    @staticmethod
    def add_processed_log(zip_path, processed_info):
        """
        将处理日志添加到压缩包中
        
        Args:
            zip_path: 压缩包路径
            processed_info: 处理信息字典，包含:
                - hash_duplicates_removed: 哈希重复数量
                - normal_duplicates_removed: 普通重复数量
                - small_images_removed: 小图数量
                - white_images_removed: 白图数量
        """
        try:
            # 创建临时目录
            temp_dir = os.path.join(os.path.dirname(zip_path), 'temp_log')
            os.makedirs(temp_dir, exist_ok=True)
            
            # 创建日志文件
            log_file_path = os.path.join(temp_dir, 'processed.log')
            with open(log_file_path, 'w', encoding='utf-8') as log_file:
                # 基本处理信息
                log_file.write(f'{os.path.basename(zip_path)} - 处理时间: {datetime.now()} - 处理情况:\n')
                log_file.write(f" - 删除的哈希重复图片: {processed_info.get('hash_duplicates_removed', 0)}\n")
                log_file.write(f" - 删除的普通重复图片: {processed_info.get('normal_duplicates_removed', 0)}\n")
                log_file.write(f" - 删除的小图数量: {processed_info.get('small_images_removed', 0)}\n")
                log_file.write(f" - 删除的白图数量: {processed_info.get('white_images_removed', 0)}\n\n")
                
                # 添加相似性记录
                similarity_records = HashFileHandler.get_similarity_records()
                if similarity_records:
                    log_file.write("相似性记录:\n")
                    for record in similarity_records:
                        log_file.write(f" - 文件: {os.path.basename(record['file_path'])}\n")
                        log_file.write(f"   相似于: {record['similar_uri']}\n")
                        log_file.write(f"   汉明距离: {record['hamming_distance']}\n")
                        log_file.write(f"   记录时间: {record['timestamp']}\n")
                    log_file.write("\n")
            
            # 将日志文件添加到压缩包
            command = ['7z', 'a', zip_path, log_file_path]
            result = subprocess.run(command, capture_output=True, text=True)
            
            # 清理临时文件和目录
            os.remove(log_file_path)
            os.rmdir(temp_dir)
            
            # 清空相似性记录，为下一个文件做准备
            HashFileHandler.clear_similarity_records()
            
            if result.returncode == 0:
                logger.info( f'成功添加处理日志到压缩包: {zip_path}')
            else:
                logger.info( f"❌ 添加日志到压缩包失败: {result.stderr}")
                
        except Exception as e:
            logger.info( f"❌ 添加日志到压缩包时出错: {e}")
            # 确保清理临时文件
            if os.path.exists(log_file_path):
                os.remove(log_file_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

class BackupHandler:
    """
    类描述
    """
    @staticmethod
    def handle_bak_file(bak_path, params=None):
        """
        根据指定模式处理bak文件
        
        Args:
            bak_path: 备份文件路径
            params: 参数字典或Namespace对象，包含:
                - bak_mode: 备份文件处理模式 ('keep', 'recycle', 'delete')
                - backup_removed_files_enabled: 是否使用回收站
        """
        try:
            # 如果没有传入参数，使用默认值
            if params is None:
                params = {}
            
            # 获取模式，支持字典和Namespace对象，默认为keep
            mode = params.bak_mode if hasattr(params, 'bak_mode') else params.get('bak_mode', 'keep')
            
            if mode == 'keep':
                logger.info( f'保留备份文件: {bak_path}')
                return
                
            if not os.path.exists(bak_path):
                logger.info( f'备份文件不存在: {bak_path}')
                return
                
            # 获取是否使用回收站，支持字典和Namespace对象

            # 如果是回收站模式，或者启用了备份文件
            if mode == 'recycle':
                try:
                    send2trash(bak_path)
                    logger.info( f'已将备份文件移至回收站: {bak_path}')
                except Exception as e:
                    logger.info( f"❌ 移动备份文件到回收站失败 {bak_path}: {e}")
            # 只有在明确指定删除模式时才直接删除
            elif mode == 'delete':
                try:
                    os.remove(bak_path)
                    logger.info( f'已删除备份文件: {bak_path}')
                except Exception as e:
                    logger.info( f"❌ 删除备份文件失败 {bak_path}: {e}")
        except Exception as e:
            logger.info( f"❌ 处理备份文件时出错 {bak_path}: {e}")



    @staticmethod
    def backup_removed_files(zip_path, removed_files, duplicate_files, params, removal_reasons):
        """
        将删除的文件备份到trash文件夹中，保持原始目录结构
        
        Args:
            zip_path: 原始压缩包路径
            removed_files: 被删除的小图/白图文件集合
            duplicate_files: 被删除的重复图片文件集合
            params: 参数字典
            removal_reasons: 文件删除原因的字典，键为文件路径，值为删除原因
        """
        try:
            if not params.get('backup_removed_files_enabled', True):
                logger.info( '跳过备份删除的文件')
                return
            if not removed_files and (not duplicate_files):
                return
                
            zip_name = os.path.splitext(os.path.basename(zip_path))[0]
            trash_dir = os.path.join(os.path.dirname(zip_path), f'{zip_name}.trash')
            os.makedirs(trash_dir, exist_ok=True)
            
            # 分类备份不同类型的文件
            for file_path in removed_files | duplicate_files:
                try:
                    # 根据记录的删除原因确定子目录
                    reason = removal_reasons.get(file_path)
                    if reason == 'hash_duplicate':
                        subdir = 'hash_duplicates'
                    elif reason == 'normal_duplicate':
                        subdir = 'normal_duplicates'
                    elif reason == 'small_image':
                        subdir = 'small_images'
                    elif reason == 'white_image':
                        subdir = 'white_images'
                    else:
                        subdir = 'other'
                    
                    # 创建目标路径并复制文件
                    rel_path = os.path.relpath(file_path, os.path.dirname(zip_path))
                    dest_path = os.path.join(trash_dir, subdir, rel_path)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy2(file_path, dest_path)
                    logger.info( f"已备份到 {subdir}: {rel_path}")
                    
                except Exception as e:
                    logger.info( f"❌ 备份文件失败 {file_path}: {e}")
                    continue
                
            logger.info( f'已备份删除的文件到: {trash_dir}')
            
        except Exception as e:
            logger.info( f"❌ 备份删除文件时出错: {e}")

class ContentFilter:
    """
    类描述
    """

    @staticmethod
    def should_process_file(file_path, params):
        """判断文件是否需要处理"""
        logger.info( f'\n开始检查文件是否需要处理: {file_path}')
        if params['exclude_paths']:
            for exclude_path in params['exclude_paths']:
                if exclude_path in file_path:
                    logger.info( f'文件在排除路径中 (排除关键词: {exclude_path})')
                    return False
        logger.info( '文件通过所有检查，将进行处理')
        return True
class ProcessManager:
    """
    类描述
    """
    @staticmethod
    def generate_summary_report(processed_archives):
        """生成处理摘要并显示到面板"""
        if not processed_archives:
            logger.info( '没有处理任何压缩包。')
            return
            
        # 使用StatisticsManager中的统计数据
        summary = [
            "📊 处理完成摘要",
            f"总共处理: {len(processed_archives)} 个压缩包",
            f"删除哈希重复图片: {StatisticsManager.hash_duplicates_count} 张",
            f"删除普通重复图片: {StatisticsManager.normal_duplicates_count} 张",
            f"删除小图: {StatisticsManager.small_images_count} 张",
            f"删除白图: {StatisticsManager.white_images_count} 张",
            f"总共减少: {sum(archive['size_reduction_mb'] for archive in processed_archives):.2f} MB",
            "\n详细信息:"
        ]
        
        # 按目录组织处理结果
        common_path_prefix = os.path.commonpath([archive['file_path'] for archive in processed_archives])
        tree_structure = {}
        for archive in processed_archives:
            relative_path = os.path.relpath(archive['file_path'], common_path_prefix)
            path_parts = relative_path.split(os.sep)
            current_level = tree_structure
            for part in path_parts:
                current_level = current_level.setdefault(part, {})
            current_level['_summary'] = (
                f"哈希重复: {archive.get('hash_duplicates_removed', 0)} 张, "
                f"普通重复: {archive.get('normal_duplicates_removed', 0)} 张, "
                f"小图: {archive.get('small_images_removed', 0)} 张, "
                f"白图: {archive.get('white_images_removed', 0)} 张, "
                f"减少: {archive['size_reduction_mb']:.2f} MB"
            )
        
        # 生成树形结构的详细信息
        def build_tree_text(level, indent=''):
            tree_text = []
            for name, content in level.items():
                if name == '_summary':
                    tree_text.append(f'{indent}{content}')
                else:
                    tree_text.append(f'{indent}├─ {name}')
                    tree_text.extend(build_tree_text(content, indent + '│   '))
            return tree_text
        
        # 添加树形结构到摘要
        summary.extend(build_tree_text(tree_structure))
        
        # 更新到面板
        logger.info( '\n'.join(summary))
        logger.info( "✅ 处理完成，已生成摘要报告")


    @staticmethod
    def process_normal_archives(directories, args):
        """处理普通模式的压缩包或目录"""
        for directory in directories:
            if os.path.exists(directory):
                params = InputHandler.prepare_params(args)
                ProcessManager.process_all_archives([directory], params)
                if args.bak_mode != 'keep':
                    for root, _, files in os.walk(directory):
                        for file in files:
                            if file.endswith('.bak'):
                                bak_path = os.path.join(root, file)
                                BackupHandler.handle_bak_file(bak_path, args)
                DirectoryHandler.remove_empty_directories(directory)
            else:
                logger.info( f"输入的路径不存在: {directory}")

    @staticmethod
    def process_merged_archives(directories, args):
        """处理合并模式的压缩包"""
        temp_dir, merged_zip, archive_paths = ArchiveProcessor.merge_archives(directories, args)
        if temp_dir and merged_zip:
            try:
                params = InputHandler.prepare_params(args)
                ProcessManager.process_all_archives([merged_zip], params)
                if ArchiveProcessor.split_merged_archive(merged_zip, archive_paths, temp_dir, params):
                    logger.info( '成功完成压缩包的合并处理和拆分')
                else:
                    logger.info( '拆分压缩包失败')
            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                if os.path.exists(merged_zip):
                    os.remove(merged_zip)

    @staticmethod
    def print_config(args, max_workers):
        """打印当前配置信息"""
        # 清屏
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # 使用log_panel输出配置信息
        config_info = [
            '\n=== 当前配置信息 ===',
            '启用的功能:',
            f"  - 小图过滤: {('是' if args.remove_small else '否')}"
        ]
        
        if args.remove_small:
            config_info.append(f'    最小尺寸: {args.min_size}x{args.min_size} 像素')
            
        config_info.extend([
            f"  - 黑白图过滤: {('是' if args.remove_grayscale else '否')}"
        ])
        

            
        config_info.extend([
            f"  - 重复图片过滤: {('是' if args.remove_duplicates else '否')}"
        ])
        
        if args.remove_duplicates:
            config_info.extend([
                f'    内部去重汉明距离阈值: {args.hamming_distance}',
                f'    外部参考汉明距离阈值: {args.ref_hamming_distance}'
            ])
            
        config_info.extend([
            f"  - 合并压缩包处理: {('是' if args.merge_archives else '否')}",
            f"从剪贴板读取: {('是' if args.clipboard else '否')}",
            f'备份文件处理模式: {args.bak_mode}',
            f'线程数: {max_workers}',
            '==================\n'
        ])
        
        initialize_textual_logger()
        logger.info( '\n'.join(config_info))

    @staticmethod
    def process_all_archives(directories, params):
        """
        主处理函数
        
        Args:
            directories: 要处理的目录列表
            params: 参数字典，包含所有必要的处理参数
        """

            
        processed_archives = []
        logger.info( "开始处理拖入的目录或文件")
        
        # 计算总文件数
        total_zip_files = sum((1 for directory in directories 
                             for root, _, files in os.walk(directory) 
                             for file in files if file.lower().endswith('zip')))
        
        # 更新总体进度面板
        logger.info( 
            f"总文件数: {total_zip_files}\n"
            f"已处理: 0\n"
            f"成功: 0\n"
            f"警告: 0\n"
            f"错误: 0"
        )

        # 设置总数
        StatisticsManager.set_total(total_zip_files)
            
        for directory in directories:
            archives = ProcessManager.process_directory(directory, params)
            processed_archives.extend(archives)
                
            # 更新总体进度
            success_count = sum(1 for a in archives if (a.get('duplicates_removed', 0) > 0 or 
                                                      a.get('small_images_removed', 0) > 0 or 
                                                      a.get('white_images_removed', 0) > 0))
            warning_count = sum(1 for a in archives if (a.get('duplicates_removed', 0) == 0 and 
                                                      a.get('small_images_removed', 0) == 0 and 
                                                      a.get('white_images_removed', 0) == 0))
            error_count = StatisticsManager.processed_count - len(archives)
                
            logger.info( 
                f"总文件数: {total_zip_files}\n"
                f"已处理: {StatisticsManager.processed_count}\n"
                f"成功: {success_count}\n"
                f"警告: {warning_count}\n"
                f"错误: {error_count}"
            )
        
        ProcessManager.generate_summary_report(processed_archives)
        logger.info( "所有目录处理完成")
        return processed_archives

    @staticmethod
    def process_directory(directory, params):
        """处理单个目录"""
        try:
            logger.info( f"\n开始处理目录: {directory}")
            processed_archives = []
            if os.path.isfile(directory):
                logger.info( f"处理单个文件: {directory}")
                if directory.lower().endswith('zip'):
                    if ContentFilter.should_process_file(directory, params):
                        logger.info( f"开始处理压缩包: {directory}")
                        archives = ProcessManager.process_single_archive(directory, params)
                        processed_archives.extend(archives)
                    else:
                        logger.info( f"跳过文件（根据过滤规则）: {directory}")
                    StatisticsManager.increment()
                else:
                    logger.info( f"跳过非zip文件: {directory}")
            elif os.path.isdir(directory):
                logger.info( f"扫描目录中的文件: {directory}")
                files_to_process = []
                for root, _, files in os.walk(directory):
                    logger.debug( f"扫描子目录: {root}")
                    for file in files:
                        if file.lower().endswith('zip'):
                            file_path = os.path.join(root, file)
                            logger.info( f"发现zip文件: {file_path}")
                            if ContentFilter.should_process_file(file_path, params):
                                logger.info( f"添加到处理列表: {file_path}")
                                files_to_process.append(file_path)
                            else:
                                logger.info( f"跳过文件（根据过滤规则）: {file_path}")
                                StatisticsManager.increment()
                logger.info( f"扫描完成: 找到 {len(files_to_process)} 个要处理的文件")
                for file_path in files_to_process:
                    try:
                        logger.info( f"\n正在处理压缩包: {file_path}")
                        archives = ProcessManager.process_single_archive(file_path, params)
                        if archives:
                            logger.info( f"成功处理压缩包: {file_path}")
                        else:
                            logger.info( f"压缩包处理完成，但没有变化: {file_path}")
                        processed_archives.extend(archives)
                    except Exception as e:
                        logger.info( f"处理压缩包出错: {file_path}\n错误: {e}")
                    finally:
                        StatisticsManager.increment()
            if os.path.isdir(directory):
                exclude_keywords = params.get('exclude_paths', [])
            return processed_archives
        except Exception as e:
            logger.info( f"处理目录时发生异常: {directory}\n{str(e)}")
            return []

    @staticmethod
    def process_single_archive(file_path, params):
        """处理单个压缩包文件"""
        try:
            logger.info( f"开始处理文件: {file_path}")
            
            if not os.path.exists(file_path):
                logger.info( f"❌ 文件不存在: {file_path}")
                return []
                
            cmd = ['7z', 'l', file_path]
            result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                logger.info( f"❌ 压缩包可能损坏: {file_path}")
                return []
                
            if result.stdout is None:
                logger.info( f"❌ 无法读取压缩包内容: {file_path}")
                return []
                
            has_images = any((line.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.jxl', '.avif', '.jxl')) 
                            for line in result.stdout.splitlines()))
            if not has_images:
                logger.info( f"⚠️ 跳过无图片的压缩包: {file_path}")
                return []
            processed_archives = []
            if not params['ignore_processed_log']:
                if ProcessedLogHandler.has_processed_log(file_path):
                    logger.info( f"⚠️ 文件已有处理记录: {file_path}")
                    return processed_archives
                    
            logger.info( "开始处理压缩包内容...")
            processed_archives.extend(ArchiveProcessor.process_archive_in_memory(file_path, params))
            
            if processed_archives:
                # 更新重复信息面板
                info = processed_archives[-1]
                logger.info( 
                    f"处理结果:\n"
                    f"- 哈希重复: {info.get('hash_duplicates_removed', 0)} 张\n"
                    f"- 普通重复: {info.get('normal_duplicates_removed', 0)} 张\n"
                    f"- 小图: {info.get('small_images_removed', 0)} 张\n"
                    f"- 白图: {info.get('white_images_removed', 0)} 张\n"
                    f"- 减少大小: {info['size_reduction_mb']:.2f} MB"
                )
                
                # 更新进度面板
                logger.info( f"✅ 成功处理: {os.path.basename(file_path)}")
                
                    
                if params['add_processed_log_enabled']:
                    processed_info = {
                        'hash_duplicates_removed': info.get('hash_duplicates_removed', 0),
                        'normal_duplicates_removed': info.get('normal_duplicates_removed', 0),
                        'small_images_removed': info.get('small_images_removed', 0),
                        'white_images_removed': info.get('white_images_removed', 0)
                    }
                    ProcessedLogHandler.add_processed_log(file_path, processed_info)
                    logger.info( "已添加处理日志")
            else:
                logger.info( f"⚠️ 压缩包处理完成，但没有需要处理的内容: {file_path}")
                
            backup_file_path = file_path + '.bak'
            if os.path.exists(backup_file_path):
                BackupHandler.handle_bak_file(backup_file_path, params)
                logger.info( "已处理备份文件")
                
            return processed_archives
            
        except UnicodeDecodeError as e:
            logger.info( f"❌ 处理压缩包时出现编码错误 {file_path}: {e}")
            return []
        except Exception as e:
            logger.info( f"❌ 处理文件时发生异常: {file_path}\n{str(e)}")
            return []

    @staticmethod
    def get_max_workers():
        """获取最大工作线程数"""
        return max_workers  # 返回全局配置的max_workers值

class StatisticsManager:
    """Statistics"""
    processed_count = 0
    total_count = 0
    hash_duplicates_count = 0  # 哈希文件去重的数量
    normal_duplicates_count = 0  # 普通去重的数量
    small_images_count = 0  # 小图数量
    white_images_count = 0  # 白图数量

    @staticmethod
    def update_progress():
        """更新进度显示"""
        if StatisticsManager.total_count > 0:
            percentage = (StatisticsManager.processed_count / StatisticsManager.total_count) * 100
            # 更新总体统计信息
            stats_str = (
                f"处理进度: {StatisticsManager.processed_count}/{StatisticsManager.total_count}\n"
                f"哈希去重: {StatisticsManager.hash_duplicates_count} 张\n"
                f"普通去重: {StatisticsManager.normal_duplicates_count} 张\n"
                f"小图: {StatisticsManager.small_images_count} 张\n"
                f"白图: {StatisticsManager.white_images_count} 张"
            )
            logger.info(f"[#cur_stats]{stats_str}")
            
            # 使用进度条面板显示总体进度
            logger.info(f"[@cur_stats] 总体进度 {percentage:.1f}%")

    @staticmethod
    def increment():
        """增加处理计数并更新进度"""
        StatisticsManager.processed_count += 1
        StatisticsManager.update_progress()

    @staticmethod
    def set_total(total):
        """设置总数并重置所有计数"""
        StatisticsManager.total_count = total
        StatisticsManager.processed_count = 0
        StatisticsManager.hash_duplicates_count = 0
        StatisticsManager.normal_duplicates_count = 0
        StatisticsManager.small_images_count = 0
        StatisticsManager.white_images_count = 0
        StatisticsManager.update_progress()


    @staticmethod
    def update_counts(hash_duplicates=0, normal_duplicates=0, small_images=0, white_images=0):
        """更新各类型文件的计数"""
        StatisticsManager.hash_duplicates_count += hash_duplicates
        StatisticsManager.normal_duplicates_count += normal_duplicates
        StatisticsManager.small_images_count += small_images
        StatisticsManager.white_images_count += white_images
        StatisticsManager.update_progress()



# 配置参数
verbose_logging = True
use_direct_path_mode = True
filter_height_enabled = True
remove_grayscale = True
add_processed_log_enabled = True
ignore_processed_log = True
min_size = 631
# max_workers = min(4, os.cpu_count() or 4)
max_workers = 4
backup_removed_files_enabled = True
use_clipboard = False


# 初始化日志管理器

class HashFileHandler:
    """处理哈希文件的类"""
    
    # 用于临时存储相似性记录的类变量
    similarity_records = []
    
    @staticmethod
    def clear_similarity_records():
        """清空相似性记录"""
        HashFileHandler.similarity_records = []
    
    @staticmethod
    def record_similarity(file_path, similar_uri, hamming_distance):
        """记录相似文件的对应关系到内存中
        
        Args:
            file_path: 当前处理的文件路径
            similar_uri: 相似文件的URI
            hamming_distance: 汉明距离
        """
        try:
            # 添加相似性信息
            similarity_info = {
                'file_path': file_path,
                'similar_uri': similar_uri,
                'hamming_distance': hamming_distance,
                'timestamp': datetime.now().isoformat()
            }
            
            HashFileHandler.similarity_records.append(similarity_info)
            logger.info( f"[#update_log]已记录相似性: {file_path} -> {similar_uri} (距离: {hamming_distance})")
            # 添加哈希操作面板标识
            
        except Exception as e:
            logger.info(f"[#update_log]- 记录相似性时出错: {str(e)}")

    @staticmethod
    def get_similarity_records():
        """获取所有相似性记录"""
        return HashFileHandler.similarity_records

    @staticmethod
    def load_hash_file(hash_file_path):
        """加载哈希文件并对哈希值进行预处理
        
        Args:
            hash_file_path: 哈希文件路径
            
        Returns:
            tuple: (哈希值列表, 哈希值到URI的映射字典)
        """
        try:
            if not hash_file_path:
                logger.info("[#file_ops]未提供哈希文件路径")
                return [], {}
                
            logger.info(f"[#file_ops]尝试加载哈希文件: {hash_file_path}")
            
            if not os.path.exists(hash_file_path):
                logger.info(f"[#file_ops]哈希文件不存在: {hash_file_path}")
                return [], {}
                
            with open(hash_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            logger.info(f"[#update_log]✅ 成功读取哈希文件: {hash_file_path}")
            
            # 提取所有哈希值并建立映射关系
            hash_to_uri = {}
            hash_values = []
            
            # 首先尝试新格式 (hashes字段)
            hashes_data = data.get('hashes', {})
            if not hashes_data:
                # 如果没有hashes字段,尝试旧格式 (results字段)
                hashes_data = data.get('results', {})
            
            total_count = len(hashes_data)
            loaded_count = 0
            
            for uri, info in hashes_data.items():
                # 处理不同格式的哈希值
                if isinstance(info, dict):
                    # 新格式: {'hash': 'xxx'} 或旧格式: {'hash_value': 'xxx'}
                    hash_str = str(info.get('hash') or info.get('hash_value', ''))
                elif isinstance(info, str):
                    # 直接是哈希字符串
                    hash_str = info
                else:
                    continue
                    
                # 验证哈希值
                if not hash_str:
                    continue
                    
                # 统一使用小写
                hash_str = hash_str.lower()
                hash_values.append(hash_str)
                hash_to_uri[hash_str] = uri
                
                loaded_count += 1
                if loaded_count % 1000 == 0:  # 每1000个显示一次进度
                    percentage = (loaded_count / total_count) * 100
                    logger.info(f"[@hash_calc] 加载哈希文件 {percentage:.1f}%")
            
            # 合并日志输出
            logger.info(f"[#hash_calc]加载哈希文件完成")
            logger.info(f"[#update_log]✅ 哈希文件加载完成 - 总数: {len(hash_values)}个")
            logger.info(f"[#hash_calc]哈希值数量: {len(hash_values)}")
            logger.info(f"[#hash_calc]URI映射数量: {len(hash_to_uri)}")
            
            return hash_values, hash_to_uri
                
        except Exception as e:
            logger.error(f"[#hash_calc]❌ 加载哈希文件失败: {str(e)}")
            return [], {}

    @staticmethod
    def find_similar_hash(target_hash, ref_hashes, hash_to_uri, hamming_distance_threshold):
        """遍历所有哈希值进行完整比较
        
        Args:
            target_hash: 目标哈希值（可以是字典格式或字符串格式）
            ref_hashes: 参考哈希值列表
            hash_to_uri: 哈希值到URI的映射字典
            hamming_distance_threshold: 汉明距离阈值
            
        Returns:
            tuple: (是否找到相似值, 相似哈希值, 对应的URI)
        """
        try:
            # 如果没有外部哈希文件，直接返回未找到
            if not ref_hashes:
                return False, None, None

            # 统一获取哈希值字符串
            def get_hash_str(hash_obj):
                if isinstance(hash_obj, dict):
                    return str(hash_obj.get('hash') or hash_obj.get('phash') or hash_obj.get('hash_value', '')).lower()
                return str(hash_obj).lower()
                
            # 提取目标哈希值
            target_hash_str = get_hash_str(target_hash)
            target_url = target_hash.get('url', '') if isinstance(target_hash, dict) else ''
            
            # 记录比较过程
            logger.debug(f"[#hash_calc]开始查找相似哈希值: {target_hash_str}" + (f" (来自: {target_url})" if target_url else ""))
            
            compared_count = 0
            max_diff = 2 ** hamming_distance_threshold  # 最大可能的差异值
            
            # 遍历所有哈希值进行比较
            for current_hash in ref_hashes:
                # 提取当前哈希值
                current_hash_str = get_hash_str(current_hash)
                current_url = current_hash.get('url', '') if isinstance(current_hash, dict) else ''
                
                # 计算汉明距离
                hamming_distance = ImageHashCalculator.calculate_hamming_distance(target_hash_str, current_hash_str)
                
                compared_count += 1
                
                if hamming_distance <= hamming_distance_threshold:
                    # 找到相似的哈希值
                    result_msg = f"[#hash_calc]找到相似哈希值: {current_hash_str}"
                    if current_url:
                        result_msg += f" (来自: {current_url})"
                    result_msg += f", 汉明距离: {hamming_distance}, URI: {hash_to_uri[current_hash_str]}"
                    logger.info(result_msg)
                    return True, current_hash_str, hash_to_uri[current_hash_str]
            
            return False, None, None
            
        except Exception as e:
            logger.info(f"[#hash_calc]查找相似哈希值时出错: {str(e)}")
            return False, None, None

class InputHandler:
    """输入处理类"""
    @staticmethod
    def parse_arguments(args=None):
        parser = argparse.ArgumentParser(description='图片压缩包去重工具')
        # 添加排除路径参数
        parser.add_argument('--exclude-paths', '-ep',
                          nargs='*',
                          default=[],
                          help='要排除的路径关键词列表')
        feature_group = parser.add_argument_group('功能开关')
        feature_group.add_argument('--remove-small', '-rs', action='store_true', help='启用小图过滤')
        feature_group.add_argument('--remove-grayscale', '-rg', action='store_true', help='启用黑白图过滤')
        feature_group.add_argument('--remove-duplicates', '-rd', action='store_true', help='启用重复图片过滤')
        feature_group.add_argument('--merge-archives', '-ma', action='store_true', help='合并同一文件夹下的多个压缩包进行处理')
        feature_group.add_argument('--no-trash', '-nt', action='store_true', help='不保留trash文件夹，直接删除到回收站')
        feature_group.add_argument('--hash-file', '-hf', type=str, help='指定哈希文件路径,用于跨压缩包去重')
        feature_group.add_argument('--self-redup', '-sr', action='store_true', help='启用自身去重复(当使用哈希文件时默认不启用)')
        feature_group.add_argument('path', nargs='*', help='要处理的文件或目录路径')
        small_group = parser.add_argument_group('小图过滤参数')
        small_group.add_argument('--min-size', '-ms', type=int, default=631, help='最小图片尺寸（宽度和高度），默认为631')
        duplicate_group = parser.add_argument_group('重复图片过滤参数')
        duplicate_group.add_argument('--hamming_distance', '-hd', type=int, default=0, help='内部去重的汉明距离阈值，数值越大判定越宽松，默认为2')
        duplicate_group.add_argument('--ref_hamming_distance', '-rhd', type=int, default=12, help='与外部参考文件比较的汉明距离阈值，默认为12')
        
        parser.add_argument('--clipboard', '-c', action='store_true', help='从剪贴板读取路径')
        parser.add_argument('--bak-mode', '-bm', choices=['recycle', 'delete', 'keep'], default='keep', help='bak文件处理模式：recycle=移到回收站（默认），delete=直接删除，keep=保留')
        parser.add_argument('--max-workers', '-mw', type=int, default=4, help='最大线程数，默认为4')

        return parser.parse_args(args)  # 添加参数传递


    @staticmethod
    def prepare_params(args):
        """
        统一准备参数字典
        
        Args:
            args: 命令行参数对象
            
        Returns:
            dict: 包含所有处理参数的字典
        """
        return {
            'min_size': args.min_size,
            'hamming_distance': args.hamming_distance,  # 这里使用连字符形式的参数名
            'ref_hamming_distance': args.ref_hamming_distance,  # 这里使用连字符形式的参数名
            'filter_height_enabled': args.remove_small,
            'remove_grayscale': args.remove_grayscale,
            'ignore_processed_log': ignore_processed_log,
            'add_processed_log_enabled': add_processed_log_enabled,
            'max_workers': args.max_workers,
            'bak_mode': args.bak_mode,
            'remove_duplicates': args.remove_duplicates,
            'hash_file': args.hash_file,
            'self_redup': args.self_redup,
            'exclude_paths': args.exclude_paths if args.exclude_paths else []
        }

    @staticmethod
    def get_input_paths(args):
        """获取输入路径"""
        directories = []
        
        # 首先检查命令行参数中的路径
        if args.path:
            directories.extend(args.path)
            
        # 如果没有路径且启用了剪贴板，则从剪贴板读取
        if not directories and args.clipboard:
            directories = InputHandler.get_paths_from_clipboard()
            
        # 如果仍然没有路径，则使用Rich Logger的输入功能
        if not directories:
            try:
                print("请输入要处理的文件夹或压缩包路径（每行一个，输入空行结束）：")
                while True:
                    line = input().strip()
                    if not line:
                        break
                    path = line.strip().strip('"').strip("'")
                    if os.path.exists(path):
                        directories.append(path)
                        # print(f"✅ 已添加有效路径: {path}")
                    else:
                        print(f"❌ 路径不存在: {path}")
                
            except Exception as e:
                print(f"获取路径失败: {e}")
                
        return directories

    @staticmethod
    def get_paths_from_clipboard():
        """从剪贴板读取多行路径"""
        try:
            clipboard_content = pyperclip.paste()
            if not clipboard_content:
                return []
            paths = [path.strip().strip('"') for path in clipboard_content.splitlines() if path.strip()]
            valid_paths = [path for path in paths if os.path.exists(path)]
            if valid_paths:
                logger.info( f'从剪贴板读取到 {len(valid_paths)} 个有效路径')
            else:
                logger.info( '剪贴板中没有有效路径')
            return valid_paths
        except ImportError:
            logger.info( '未安装 pyperclip 模块，无法读取剪贴板')
            return []
        except Exception as e:
            logger.info( f'读取剪贴板时出错: {e}')
            return []

    @staticmethod
    def validate_args(args):
        """验证参数是否有效"""
        if not any([args.remove_small, args.remove_grayscale, args.remove_duplicates]):
            logger.info( '警告: 未启用任何过滤功能，将不会对图片进行处理')
        return True

class Application:
    """
    类描述
    """
    def main(self):
        """主函数"""
        try:
            # 添加父目录到Python路径
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            
            # 检查是否有命令行参数
            if len(sys.argv) > 1:
                # 命令行模式处理
                args = InputHandler.parse_arguments()
                if not InputHandler.validate_args(args):
                    sys.exit(1)
                self._process_with_args(args)
                return

            # TUI模式处理
            if not HAS_TUI:
                print("无法导入TUI配置模块,将使用命令行模式")
                args = InputHandler.parse_arguments()
                if not InputHandler.validate_args(args):
                    sys.exit(1)
                self._process_with_args(args)
                return

            # 创建配置选项和预设
            checkbox_options, input_options, preset_configs = self._create_ui_config()

            # 创建配置界面
            app = create_config_app(
                program=os.path.abspath(__file__),
                checkbox_options=checkbox_options,
                input_options=input_options,
                title="图片压缩包去重工具",
                preset_configs=preset_configs,
                on_run=False  # 新增回调函数
            )
            
            # 运行配置界面
            app.run()

        except Exception as e:
            logger.error(f"❌ 处理过程中发生错误: {e}")
            print(f"错误信息: {e}")
            sys.exit(1)

    def _process_with_args(self, args):
        """统一处理参数执行"""
        directories = InputHandler.get_input_paths(args)
        if not directories:
            print('未提供任何输入路径')
            return
        # initialize_textual_logger()
        ProcessManager.print_config(args, ProcessManager.get_max_workers())
        if args.remove_duplicates:
            
            global global_hashes
        if args.merge_archives:
            ProcessManager.process_merged_archives(directories, args)
        else:
            ProcessManager.process_normal_archives(directories, args)

    def _handle_tui_run(self, params: dict):
        """TUI模式回调处理"""
        # 转换参数为命令行格式
        args_list = []
        
        # 添加选项参数
        for arg, enabled in params['options'].items():
            if enabled:
                args_list.append(arg)
        
        # 添加输入参数
        for arg, value in params['inputs'].items():
            if value:  # 只添加有值的参数
                args_list.extend([arg, value])
        
        # 添加路径参数
        if params.get('paths'):
            args_list.extend(params['paths'])
        
        # 解析参数
        args = InputHandler.parse_arguments(args_list)
        if not InputHandler.validate_args(args):
            sys.exit(1)
        
        # 统一执行处理
        self._process_with_args(args)

    def _create_ui_config(self):
        """创建TUI配置选项和预设"""
        checkbox_options = [
            ("小图过滤", "remove_small", "--remove-small"),
            ("黑白图过滤", "remove_grayscale", "--remove-grayscale"), 
            ("重复图片过滤", "remove_duplicates", "--remove-duplicates"),
            ("合并压缩包处理", "merge_archives", "--merge-archives"),
            ("自身去重复", "self_redup", "--self-redup"),
        ]

        input_options = [
            ("最小图片尺寸", "min_size", "--min-size", "631", "输入数字(默认631)"),
            ("汉明距离", "hamming_distance", "--hamming_distance", "12", "输入汉明距离的数字"),
            ("内部去重的汉明距离阈值", "ref_hamming_distance", "--ref-hamming_distance", "12", "输入内部去重的汉明距离阈值"),
            ("哈希文件路径", "hash_file", "--hash-file", "", "输入哈希文件路径(可选)"),
        ]

        preset_configs = {
            "去小图模式": {
                "description": "仅去除小尺寸图片",
                "checkbox_options": ["remove_small",  "clipboard"],
                "input_values": {
                    "min_size": "631"
                }
            },
            "去重复模式": {
                "description": "仅去除重复图片",
                "checkbox_options": ["remove_duplicates", "clipboard"],
                "input_values": {
                    "hamming_distance": "12"
                }
            },
            "去黑白模式": {
                "description": "仅去除黑白/白图",
                "checkbox_options": ["remove_grayscale", "clipboard"],
            },
            "合并处理模式": {
                "description": "合并压缩包处理(去重+去小图+去黑白)",
                "checkbox_options": ["merge_archives", "remove_small", "remove_duplicates", "remove_grayscale", "clipboard"],
                "input_values": {
                    "min_size": "631",
                    "hamming_distance": "12"

                }
            }
        }

        return checkbox_options, input_options, preset_configs


class DebuggerHandler:
    LAST_CONFIG_FILE = "last_debug_config.json"

    @staticmethod
    def save_last_config(mode_choice, final_args):
        """保存最后一次使用的配置"""
        try:
            config = {
                "mode": mode_choice,
                "args": final_args
            }
            with open(DebuggerHandler.LAST_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.info(f"[#update_log]保存配置失败: {e}")

    @staticmethod
    def load_last_config():
        """加载上次使用的配置"""
        try:
            if os.path.exists(DebuggerHandler.LAST_CONFIG_FILE):
                with open(DebuggerHandler.LAST_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.info(f"[#update_log]加载配置失败: {e}")
        return None

    @staticmethod
    def get_debugger_options():
        """交互式调试模式菜单"""
        # 基础模式选项
        base_modes = {
            "1": {"name": "去小图模式", "base_args": ["-rs"], "default_params": {"ms": "631"}},
            "2": {"name": "去重复模式", "base_args": ["-rd"], "default_params": {"hd": "12", "rhd": "12"}},
            "3": {"name": "去黑白模式", "base_args": ["-rg"]},
            "4": {"name": "合并处理模式", "base_args": ["-ma", "-rs", "-rd", "-rg"], 
                  "default_params": {"ms": "631", "hd": "12", "rhd": "12"}}
        }
        
        # 可配置参数选项
        param_options = {
            "ms": {"name": "最小尺寸", "arg": "-ms", "default": "631", "type": int},
            "hd": {"name": "汉明距离", "arg": "-hd", "default": "12", "type": int},
            "rhd": {"name": "参考汉明距离", "arg": "-rhd", "default": "12", "type": int},
            "bm": {"name": "备份模式", "arg": "-bm", "default": "keep", "choices": ["keep", "recycle", "delete"]},
            "c": {"name": "从剪贴板读取", "arg": "-c", "is_flag": True},
            "mw": {"name": "最大线程数", "arg": "-mw", "default": "4", "type": int}
        }

        # 加载上次配置
        last_config = DebuggerHandler.load_last_config()
        
        while True:
            print("\n=== 调试模式选项 ===")
            print("\n基础模式:")
            for key, mode in base_modes.items():
                print(f"{key}. {mode['name']}")
            
            if last_config:
                print("\n上次配置:")
                print(f"模式: {base_modes[last_config['mode']]['name']}")
                print("参数:", " ".join(last_config['args']))
                print("\n选项:")
                print("L. 使用上次配置")
                print("N. 使用新配置")
                choice = input("\n请选择 (L/N 或直接选择模式 1-4): ").strip().upper()
                
                if choice == 'L':
                    return last_config['args']
                elif choice == 'N':
                    pass  # 继续使用新配置
                elif not choice:
                    return []
                elif choice in base_modes:
                    mode_choice = choice
                else:
                    print("❌ 无效的选择，请重试")
                    continue
            else:
                # 获取基础模式选择
                mode_choice = input("\n请选择基础模式(1-4): ").strip()
                if not mode_choice:
                    return []
                
                if mode_choice not in base_modes:
                    print("❌ 无效的模式选择，请重试")
                    continue
            
            selected_mode = base_modes[mode_choice]
            final_args = selected_mode["base_args"].copy()
            
            # 添加默认参数
            if "default_params" in selected_mode:
                for param_key, default_value in selected_mode["default_params"].items():
                    if param_key in param_options:
                        param = param_options[param_key]
                        final_args.append(f"{param['arg']}={default_value}")
            
            # 显示当前配置
            print("\n当前配置:")
            for arg in final_args:
                print(f"  {arg}")
            
            # 询问是否需要修改参数
            while True:
                print("\n可选操作:")
                print("1. 修改参数")
                print("2. 添加参数")
                print("3. 开始执行")
                print("4. 重新选择模式")
                print("0. 退出程序")
                
                op_choice = input("\n请选择操作(0-4): ").strip()
                
                if op_choice == "0":
                    return []
                elif op_choice == "1":
                    # 显示当前所有参数
                    print("\n当前参数:")
                    for i, arg in enumerate(final_args, 1):
                        print(f"{i}. {arg}")
                    param_idx = input("请选择要修改的参数序号: ").strip()
                    try:
                        idx = int(param_idx) - 1
                        if 0 <= idx < len(final_args):
                            new_value = input(f"请输入新的值: ").strip()
                            if '=' in final_args[idx]:
                                arg_name = final_args[idx].split('=')[0]
                                final_args[idx] = f"{arg_name}={new_value}"
                            else:
                                final_args[idx] = new_value
                    except ValueError:
                        print("❌ 无效的输入")
                elif op_choice == "2":
                    # 显示可添加的参数
                    print("\n可添加的参数:")
                    for key, param in param_options.items():
                        if param.get("is_flag"):
                            print(f"  {key}. {param['name']} (开关参数)")
                        elif "choices" in param:
                            print(f"  {key}. {param['name']} (可选值: {'/'.join(param['choices'])})")
                        else:
                            print(f"  {key}. {param['name']}")
                    
                    param_key = input("请输入要添加的参数代号: ").strip()
                    if param_key in param_options:
                        param = param_options[param_key]
                        if param.get("is_flag"):
                            final_args.append(param["arg"])
                        else:
                            value = input(f"请输入{param['name']}的值: ").strip()
                            if "choices" in param and value not in param["choices"]:
                                print(f"❌ 无效的值，可选值: {'/'.join(param['choices'])}")
                                continue
                            if "type" in param:
                                try:
                                    value = param["type"](value)
                                except ValueError:
                                    print("❌ 无效的数值")
                                    continue
                            final_args.append(f"{param['arg']}={value}")
                elif op_choice == "3":
                    print("\n最终参数:", " ".join(final_args))
                    # 保存当前配置
                    DebuggerHandler.save_last_config(mode_choice, final_args)
                    return final_args
                elif op_choice == "4":
                    break
                else:
                    print("❌ 无效的选择")
            
        return []
    
if __name__ == '__main__':
    if USE_DEBUGGER:
        selected_options = DebuggerHandler.get_debugger_options()
        if selected_options:
            # 移除多余的--no-tui参数
            args = InputHandler.parse_arguments(selected_options)  # 删除+ ['--no-tui']
            Application()._process_with_args(args)
        else:
            print("未选择任何功能，程序退出。")
            sys.exit(0)
    else:
        Application().main()
 
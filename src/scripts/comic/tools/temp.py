import os
import logging


from nodes.pics.image_filter import ImageFilter
logger = logging.getLogger(__name__)

class ImageProcessor:
    """图片处理器"""
    def __init__(self):
        """初始化图片处理器"""
        self.image_filter = ImageFilter()
        self.temp_hashes = {}  # 临时存储当前压缩包的哈希值

    def process_single_image(self, file_path, rel_path, existing_file_names, params, lock): 
        """处理单个图片文件"""
        try:
            if not file_path or not os.path.exists(file_path):
                logger.info(f"[#file_ops]❌ 文件不存在: {file_path}")
                return (None, None, None, 'file_not_found')
                            
            try:
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                    logger.info(f"[#file_ops]📷读图: {file_path}")
            except (IOError, OSError) as e:
                logger.info(f"[#file_ops]❌ 图片文件损坏或无法读取 {rel_path}: {e}")
                return (None, None, None, 'corrupted_image')
            except Exception as e:
                logger.info(f"[#file_ops]❌ 读取文件失败 {rel_path}: {e}")
                return (None, None, None, 'read_error')
                
            if file_path.lower().endswith(('png', 'webp', 'jxl', 'avif', 'jpg', 'jpeg', 'bmp', 'tiff', 'tif', 'heic', 'heif', 'bmp')):
                # 使用ImageFilter进行图片过滤
                to_delete, removal_reason = self.image_filter.process_images(
                    [file_path],
                    enable_small_filter=params.get('filter_height_enabled', False),
                    enable_grayscale_filter=params.get('remove_grayscale', False),
                    enable_duplicate_filter=params.get('remove_duplicates', False),
                    min_size=params.get('min_size', 631),
                    duplicate_filter_mode='hash' if params.get('hash_file') else 'quality',
                    ref_hamming_threshold=params.get('ref_hamming_distance', 12)
                )

                if to_delete:
                    reason = next(iter(removal_reason.values()))['reason']
                    return (None, file_data, file_path, reason)

                # 如果启用了重复检测，计算并返回哈希值
                if params.get('remove_duplicates', False):
                    img_hash = self.image_filter._get_image_hash(file_path)
                    if not img_hash:
                        return (None, file_data, file_path, 'hash_error')
                    return (img_hash, file_data, file_path, None)

                return (None, file_data, file_path, None)
            else:
                return (None, file_data, file_path, 'non_image_file')
        except Exception as e:
            logger.info(f"[#file_ops]❌ 处理文件时出错 {rel_path}: {e}")
            return (None, None, None, 'processing_error')


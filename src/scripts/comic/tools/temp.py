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

    def detect_small_image(self, image_data, params):
        """独立的小图检测，使用优化的方法"""
        try:
            # 如果是PIL图像对象，先转换为字节数据
            if isinstance(image_data, Image.Image):
                img_byte_arr = BytesIO()
                image_data.save(img_byte_arr, format=image_data.format)
                img_data = img_byte_arr.getvalue()
            else:
                img_data = image_data

            # 使用优化的尺寸检测方法
            with Image.open(BytesIO(img_data)) as img:
                # 只获取图片尺寸信息，不加载整个图片
                width, height = img.size
                min_size = params.get('min_size', 631)
                
                if width < min_size or height < min_size:
                    logger.info(f"[#image_processing]🖼️ 发现小图: {width}x{height} < {min_size}")
                    return None, 'small_image'
                    
                logger.info(f"[#image_processing]🖼️ 图片尺寸合格: {width}x{height} >= {min_size}")
                return img_data, None
                
        except Exception as e:
            logger.info(f"[#image_processing]❌ 检查图片尺寸失败: {str(e)}")
            return None, 'size_detection_error'

    def detect_grayscale_image(self, image_data):
        """独立的白图检测，使用优化的方法"""
        try:
            # 如果是PIL图像对象，先转换为字节数据
            if isinstance(image_data, Image.Image):
                img_byte_arr = BytesIO()
                image_data.save(img_byte_arr, format=image_data.format)
                img_data = img_byte_arr.getvalue()
            else:
                img_data = image_data

            with Image.open(BytesIO(img_data)) as img:
                # 如果是灰度图，直接返回
                if img.mode == "L":
                    logger.info(f"[#image_processing]🎨 发现原始灰度图")
                    return None, 'grayscale'

                if img.mode in ["RGB", "RGBA"]:
                    # 转换为RGB模式
                    rgb_img = img.convert("RGB")
                    
                    # 获取图片的一小部分样本进行分析
                    width, height = rgb_img.size
                    sample_points = [
                        (x, y) for x in range(0, width, width//10)
                        for y in range(0, height, height//10)
                    ][:100]  # 最多取100个采样点
                    
                    # 检查采样点的RGB值
                    pixels = [rgb_img.getpixel(point) for point in sample_points]
                    
                    # 检查是否为纯白图
                    if all(all(v > 240 for v in pixel) for pixel in pixels):
                        logger.info(f"[#image_processing]🎨 发现纯白图")
                        return None, 'white_image'
                    
                    # 检查是否为灰度图
                    is_grayscale = all(
                        abs(pixel[0] - pixel[1]) < 5 and 
                        abs(pixel[1] - pixel[2]) < 5 and
                        abs(pixel[0] - pixel[2]) < 5 
                        for pixel in pixels
                    )
                    
                    if is_grayscale:
                        logger.info(f"[#image_processing]🎨 发现灰度图(RGB接近)")
                        return None, 'grayscale'

            return image_data, None
            
        except Exception as e:
            logger.info(f"[#image_processing]❌ 检查灰度图片失败: {str(e)}")
            return None, 'grayscale_detection_error'

// ... existing code ...
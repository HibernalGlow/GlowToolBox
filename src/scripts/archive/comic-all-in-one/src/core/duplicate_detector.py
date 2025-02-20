from src.utils.hash_utils import HashUtils
from src.services.logging_service import LoggingService
import logging
from src.utils.hash_utils import HashFileHandler
import os
import sys
from src.services.stats_service import StatsService
from pics.calculate_hash_custom import ImageHashCalculator
from pics.grayscale_detector import GrayscaleDetector
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
                StatsService.update_counts(hash_duplicates=1)
                removal_reasons[file_path1] = 'hash_duplicate'

                # 记录相似性
                hamming_distance = ImageHashCalculator.calculate_hamming_distance(hash1, similar_hash)
                # 添加哈希操作面板标识
                logging.info(f"[#hash_calc]汉明距离: {hamming_distance}<{params['ref_hamming_distance']}")  
                HashFileHandler.record_similarity(file_path1, similar_uri, hamming_distance)
                # 使用新的日志格式
                logging.info(f"[#cur_progress]处理文件: {os.path.basename(file_path1)}")
                logging.info(f"[#hash_calc]发现哈希重复，将删除: {os.path.basename(file_path1)}")  # 修改面板标识
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
            logging.info(f"[#cur_progress]分析文件: {os.path.basename(file_path1)}")
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
                    StatsService.update_counts(normal_duplicates=1)
                    
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
                    logging.info(f"[#hash_calc]发现重复图片，将删除: {os.path.basename(file_path)}, 距离: {hamming_distance}")  
                    logging.info(f"[#hash_calc]重复详情 - 源: {os.path.basename(kept_image[3])}, 距离: {hamming_distance}")
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
                StatsService.update_counts(small_images=1)
                removal_reasons[img[2]] = 'small_image'
            elif img[3] == 'white_image':
                skipped_images['white_images'] += 1
                StatsService.update_counts(white_images=1)
                removal_reasons[img[2]] = 'white_image'
            elif img[0] is None:
                skipped_images['hash_error'] += 1

        # 记录统计信息
        StatsService.update_counts(
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
            logging.info(f"[#hash_calc]开始处理外部哈希文件，长度: {len(ref_hashes)}")
            remaining_images, hash_duplicates, hash_reasons = DuplicateDetector._compare_with_reference_hashes(
                image_hashes, ref_hashes, hash_to_uri, params
            )
            removal_reasons.update(hash_reasons)

        # 第二步：处理内部重复
        # 没有哈希文件时,或者有哈希文件且启用了自身去重时,进行内部去重
        if not ref_hashes or params.get('self_redup', False):
            # 使用hamming_distance进行内部去重
            internal_hamming_distance = params['hamming_distance']
            logging.info(f"[#hash_calc]开始处理内部重复图片 (使用hamming_distance: {internal_hamming_distance})")
            final_images, normal_duplicates, internal_reasons = DuplicateDetector._process_internal_duplicates(
                remaining_images, 
                internal_hamming_distance,
                removal_reasons
            )
            removal_reasons.update(internal_reasons)
        else:
            final_images = [(h, d, p, r) for h, d, p, r in remaining_images]

        # 记录日志
        logging.info( f'总共删除哈希重复图片: {hash_duplicates}')
        logging.info( f'总共删除普通重复图片: {normal_duplicates}')
        logging.info( f"总共删除小图: {skipped_images['small_images']}")
        logging.info( f"总共删除白图: {skipped_images['white_images']}")
        logging.info( f"总共跳过哈希错误: {skipped_images['hash_error']}")

        return (final_images, skipped_images, removal_reasons)

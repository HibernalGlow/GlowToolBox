from src.services.logging_service import LoggingService
import logging


class StatsService:
    """统计服务类"""
    processed_count = 0
    total_count = 0
    hash_duplicates_count = 0  # 哈希文件去重的数量
    normal_duplicates_count = 0  # 普通去重的数量
    small_images_count = 0  # 小图数量
    white_images_count = 0  # 白图数量

    @staticmethod
    def update_progress():
        """更新进度显示"""
        if StatsService.total_count > 0:
            percentage = (StatsService.processed_count / StatsService.total_count) * 100
            # 更新总体统计信息
            stats_str = (
                f"处理进度: {StatsService.processed_count}/{StatsService.total_count}\n"
                f"哈希去重: {StatsService.hash_duplicates_count} 张\n"
                f"普通去重: {StatsService.normal_duplicates_count} 张\n"
                f"小图: {StatsService.small_images_count} 张\n"
                f"白图: {StatsService.white_images_count} 张"
            )
            logging.info(f"[#cur_stats]{stats_str}")
            
            # 使用进度条面板显示总体进度
            logging.info(f"[@cur_stats] 总体进度 {percentage:.1f}%")

    @staticmethod
    def increment():
        """增加处理计数并更新进度"""
        StatsService.processed_count += 1
        StatsService.update_progress()

    @staticmethod
    def set_total(total):
        """设置总数并重置所有计数"""
        StatsService.total_count = total
        StatsService.processed_count = 0
        StatsService.hash_duplicates_count = 0
        StatsService.normal_duplicates_count = 0
        StatsService.small_images_count = 0
        StatsService.white_images_count = 0
        StatsService.update_progress()


    @staticmethod
    def update_counts(hash_duplicates=0, normal_duplicates=0, small_images=0, white_images=0):
        """更新各类型文件的计数"""
        StatsService.hash_duplicates_count += hash_duplicates
        StatsService.normal_duplicates_count += normal_duplicates
        StatsService.small_images_count += small_images
        StatsService.white_images_count += white_images
        StatsService.update_progress()


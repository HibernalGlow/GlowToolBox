import os
import sys
import json
import hashlib
import argparse
import subprocess
from pathlib import Path
from typing import Optional, List
import logging
from datetime import datetime
# 添加TextualLogger导入

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nodes.tui.textual_logger import TextualLoggerManager
from nodes.pics.hash_process_config import get_latest_hash_file_path, process_artist_folder, process_duplicates
from nodes.record.logger_config import setup_logger
from nodes.record.logger_config import setup_logger
from nodes.tui.mode_manager import create_mode_manager
from nodes.file_ops.backup_handler import BackupHandler
from nodes.file_ops.archive_handler import ArchiveHandler
from nodes.pics.image_filter import ImageFilter
from nodes.io.input_handler import InputHandler
from nodes.io.config_handler import ConfigHandler
from nodes.io.path_handler import PathHandler, ExtractMode
# 在全局配置部分添加以下内容
# ================= 日志配置 =================
config = {
    'script_name': 'recruit_remove',
}
logger, config_info = setup_logger(config)

# 参数配置
DEFAULT_PARAMS = {
    'ref_hamming_distance': 16,  # 与外部参考文件比较的汉明距离阈值
    'hamming_distance': 0,  # 内部去重的汉明距离阈值
    'self_redup': False,  # 是否启用自身去重复
    'remove_duplicates': True,  # 是否启用重复图片过滤
    'hash_size': 10,  # 哈希值大小
    'filter_white_enabled': False,  # 是否启用白图过滤
    'recruit_folder': r'E:\1EHV\[01杂]\zzz去图',  # 画师文件夹
    'exclude-paths': ['画集', 'cg', '动画', '图集'],  # 已经存在，无需修改
}

# TextualLogger布局配置
TEXTUAL_LAYOUT = {
    "current_stats": {
        "ratio": 2,
        "title": "📊 总体进度",
        "style": "lightyellow"
    },
    "current_progress": {
        "ratio": 2,
        "title": "🔄 当前进度",
        "style": "lightcyan"
    },
    "process_log": {
        "ratio": 3,
        "title": "📝 处理日志",
        "style": "lightpink"
    },
    "update_log": {
        "ratio": 3,
        "title": "ℹ️ 更新日志",
        "style": "lightblue"
    },
}

# 常量设置
WORKER_COUNT = 2  # 线程数
FORCE_UPDATE = False  # 是否强制更新哈希值

def init_TextualLogger():
    TextualLoggerManager.set_layout(TEXTUAL_LAYOUT, config_info['log_file'])

class RecruitRemoveFilter:
    """招募图片过滤器"""
    
    def __init__(self, hash_file: str = None, cover_count: int = 3, hamming_threshold: int = 12):
        """初始化过滤器"""
        self.image_filter = ImageFilter(hash_file, cover_count, hamming_threshold)
        
    def _robust_cleanup(self, temp_dir: str) -> None:
        """更健壮的文件清理方法，处理文件被占用的情况"""
        if not os.path.exists(temp_dir):
            return

        def on_rm_error(func, path, exc_info):
            try:
                os.chmod(path, stat.S_IWRITE)
                os.unlink(path)
            except Exception as e:
                logger.warning(f"[#process_log]无法删除 {path}: {e}")

        try:
            # 尝试标准删除
            shutil.rmtree(temp_dir, onerror=on_rm_error)
        except Exception as e:
            logger.warning(f"[#process_log]标准删除失败，尝试强制删除: {temp_dir}")
            try:
                # 使用系统命令强制删除（Windows）
                if platform.system() == 'Windows':
                    subprocess.run(f'rmdir /s /q "{temp_dir}"', shell=True, check=True)
                else:  # Linux/MacOS
                    subprocess.run(f'rm -rf "{temp_dir}"', shell=True, check=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"[#update_log]强制删除失败: {temp_dir}")
                raise

    def process_archive(self, zip_path: str, extract_mode: str = ExtractMode.ALL, extract_params: dict = None) -> bool:
        """处理单个压缩包"""
        TextualLoggerManager.set_layout(TEXTUAL_LAYOUT, config_info['log_file'])
        
        # 检查输入路径是否为目录
        if os.path.isdir(zip_path):
            # 遍历目录查找zip文件
            zip_files = []
            for root, _, files in os.walk(zip_path):
                for file in files:
                    if file.lower().endswith('.zip'):
                        # 检查是否在黑名单中
                        skip = False
                        for exclude_path in DEFAULT_PARAMS['exclude-paths']:
                            if exclude_path.lower() in root.lower() or exclude_path.lower() in file.lower():
                                logger.info(f"[#process_log]跳过黑名单路径: {os.path.join(root, file)}")
                                skip = True
                                break
                        if not skip:
                            zip_files.append(os.path.join(root, file))
            
            if not zip_files:
                logger.info(f"[#process_log]在目录中未找到可处理的压缩包: {zip_path}")
                return False
                
            # 处理找到的每个压缩包
            success_count = 0
            for zip_file in zip_files:
                if self.process_archive(zip_file, extract_mode, extract_params):
                    success_count += 1
            return success_count > 0
        
        # 如果是单个文件，检查是否为zip文件
        if not zip_path.lower().endswith('.zip'):
            logger.info(f"[#process_log]不是有效的压缩包文件: {zip_path}")
            return False
            
        # 检查是否在黑名单中
        for exclude_path in DEFAULT_PARAMS['exclude-paths']:
            if exclude_path.lower() in zip_path.lower():
                logger.info(f"[#process_log]跳过黑名单路径: {zip_path}")
                return False
        
        logger.info(f"[#process_log]开始处理压缩包: {zip_path}")
        
        # 列出压缩包内容
        files = ArchiveHandler.list_archive_contents(zip_path)
        if not files:
            logger.info("[#process_log]未找到图片文件")
            return False
            
        # 获取要解压的文件索引
        extract_params = extract_params or {}
        selected_indices = ExtractMode.get_selected_indices(extract_mode, len(files), extract_params)
        if not selected_indices:
            logger.error("[#process_log]未选择任何文件进行解压")
            return False
            
        # 解压选定文件
        selected_files = [files[i] for i in selected_indices]
        success, temp_dir = ArchiveHandler.extract_files(zip_path, selected_files)
        if not success:
            return False
            
        try:
            # 获取解压后的图片文件
            image_files = []
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if PathHandler.get_file_extension(file) in {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.avif', '.heic', '.heif', '.jxl'}:
                        image_files.append(PathHandler.join_paths(root, file))
                        
            # 处理图片 - 启用重复图片过滤
            to_delete, removal_reasons = self.image_filter.process_images(
                image_files,
                enable_duplicate_filter=True,   # 启用重复图片过滤
                duplicate_filter_mode='quality'  # 使用质量过滤模式
            )
            
            if not to_delete:
                logger.info("[#process_log]没有需要删除的图片")
                self._robust_cleanup(temp_dir)
                return False
                
            # 备份要删除的文件
            backup_results = BackupHandler.backup_removed_files(zip_path, to_delete, removal_reasons)
            
            # 从压缩包中删除文件
            files_to_delete = []
            for file_path in to_delete:
                # 获取文件在压缩包中的相对路径
                rel_path = os.path.relpath(file_path, temp_dir)
                files_to_delete.append(rel_path)
                
            # 使用7z删除文件
            delete_list_file = os.path.join(temp_dir, '@delete.txt')
            with open(delete_list_file, 'w', encoding='utf-8') as f:
                for file_path in files_to_delete:
                    f.write(file_path + '\n')
                    
            # 在执行删除操作前备份原始压缩包
            backup_success, backup_path = BackupHandler.backup_source_file(zip_path)
            if backup_success:
                logger.info(f"[#process_log]✅ 源文件备份成功: {backup_path}")
            else:
                logger.warning(f"[#process_log]⚠️ 源文件备份失败: {backup_path}")

            # 使用7z删除文件
            cmd = ['7z', 'd', zip_path, f'@{delete_list_file}']
            result = subprocess.run(cmd, capture_output=True, text=True)
            os.remove(delete_list_file)
            
            if result.returncode != 0:
                logger.error(f"[#process_log]从压缩包删除文件失败: {result.stderr}")
                self._robust_cleanup(temp_dir)
                return False
                
            logger.info(f"[#process_log]成功处理压缩包: {zip_path}")
            logger.info("[#current_progress]正在分析图片相似度...")
            self._robust_cleanup(temp_dir)
            return True
            
        except Exception as e:
            logger.error(f"[#process_log]处理压缩包失败 {zip_path}: {e}")
            self._robust_cleanup(temp_dir)
            return False

def process_single_path(path: Path, workers: int = 4, force_update: bool = False, params: dict = None) -> bool:
    """处理单个路径
    
    Args:
        path: 输入路径
        workers: 线程数
        force_update: 是否强制更新
        params: 参数字典，包含处理参数
        
    Returns:
        bool: 是否处理成功
    """
    try:
        logging.info(f"[#process_log]\n🔄 处理路径: {path}")
        
        recruit_folder=Path(params['recruit_folder']).resolve()
        # 处理画师文件夹，生成哈希文件
        hash_file = process_artist_folder(recruit_folder, workers, force_update)
        if not hash_file:
            return False
            
        logging.info(f"[#update_log]✅ 生成哈希文件: {hash_file}")
        
        # 处理重复文件
        logging.info(f"[#process_log]\n🔄 处理重复文件 {path}")
        
        # 创建过滤器实例并处理文件
        filter_instance = RecruitRemoveFilter(
            hash_file=hash_file,
            cover_count=3,  # 默认处理前3张
            hamming_threshold=params.get('ref_hamming_distance', 16)
        )
        
        # 设置解压参数，默认处理前3张和后5张
        extract_params = {
            'first_n': 3,  # 前3张
            'last_n': 5   # 后5张
        }
        
        # 处理文件
        success = filter_instance.process_archive(
            str(path),
            extract_mode=ExtractMode.RANGE,
            extract_params=extract_params
        )
        
        if success:
            logging.info(f"[#update_log]✅ 处理完成: {path}")
            return True
        return False
        
    except Exception as e:
        logging.info(f"[#process_log]❌ 处理路径时出错: {path}: {e}")
        return False

def main():
    """主函数"""
    # 获取路径列表
    print("请输入要处理的路径（每行一个，输入空行结束）:")
    paths = []
    while True:
        path = input().strip().replace('"', '')
        if not path:
            break
        paths.append(Path(path))
    if not paths:
        print("[#process_log]❌ 未输入任何路径")
        return
        
    print("[#process_log]\n🚀 开始处理...")
    
    # 准备参数
    params = DEFAULT_PARAMS.copy()
    recruit_folder = Path(params['recruit_folder']).resolve()
    
    # 处理画师文件夹，生成哈希文件
    hash_file = process_artist_folder(recruit_folder, WORKER_COUNT, FORCE_UPDATE)
    if not hash_file:
        logging.info("[#process_log]❌ 无法生成哈希文件")
        return
    
    success_count = 0
    total_count = len(paths)
    
    for i, path in enumerate(paths, 1):
        logging.info(f"[#process_log]\n=== 处理第 {i}/{total_count} 个路径 ===")
        logging.info(f"[#process_log]路径: {path}")
        
        # 更新进度
        progress = int((i - 1) / total_count * 100)
        logging.debug(f"[#current_progress]当前进度: [{('=' * int(progress/5))}] {progress}%")
        logging.info(f"[#current_stats]总路径数: {total_count} 已处理: {i-1} 成功: {success_count} 总进度: [{('=' * int(progress/5))}] {progress}%")
        
        # 处理重复文件
        try:
            # 创建过滤器实例并处理文件
            filter_instance = RecruitRemoveFilter(
                hash_file=hash_file,
                cover_count=3,  # 默认处理前3张
                hamming_threshold=params.get('ref_hamming_distance', 16)
            )
            
            # 设置解压参数，默认处理前3张和后5张
            extract_params = {
                'first_n': 3,  # 前3张
                'last_n': 5   # 后5张
            }
            
            # 处理文件
            success = filter_instance.process_archive(
                str(path),
                extract_mode=ExtractMode.RANGE,
                extract_params=extract_params
            )
            
            if success:
                success_count += 1
        except Exception as e:
            logging.info(f"[#process_log]❌ 处理失败: {path}: {e}")
        
        # 更新最终进度
        progress = int(i / total_count * 100)
        logging.debug(f"[#current_progress]当前进度: [{('=' * int(progress/5))}] {progress}%")
        logging.info(f"[#current_stats]总路径数: {total_count}\n已处理: {i}\n成功: {success_count}\n总进度: [{('=' * int(progress/5))}] {progress}%")
            
    logging.info(f"[#update_log]\n✅ 所有处理完成: 成功 {success_count}/{total_count}")

if __name__ == "__main__":
    main()
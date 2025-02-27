import os
import logging
import shutil
import tempfile
import subprocess
from pathlib import Path
from nodes.record.logger_config import setup_logger
from nodes.tui.textual_logger import TextualLoggerManager
from scripts.comic.psd_convert import convert_psd_files

# 配置日志面板布局
TEXTUAL_LAYOUT = {
    "cur_stats": {
        "ratio": 2,
        "title": "📊 总体进度",
        "style": "lightyellow"
    },
    "cur_progress": {
        "ratio": 2,
        "title": "🔄 当前进度",
        "style": "lightcyan"
    },
    "file_ops": {
        "ratio": 3,
        "title": "📂 文件操作",
        "style": "lightpink"
    },
    "process": {
        "ratio": 3,
        "title": "📝 处理日志",
        "style": "lightblue"
    }
}
def init_TextualLogger():
    TextualLoggerManager.set_layout(TEXTUAL_LAYOUT, config_info['log_file'])
    
config = {
    'script_name': 'single_packer',
    'console_enabled': False
}
logger, config_info = setup_logger(config)

def init_TextualLogger():
    TextualLoggerManager.set_layout(TEXTUAL_LAYOUT, config_info['log_file'])

class SinglePacker:
    """单层目录打包工具
    
    只处理指定目录下的一级内容：
    1. 将每个一级子文件夹打包成独立的压缩包
    2. 将一级目录下的所有图片文件打包成一个压缩包
    3. 压缩包名称基于父文件夹名称
    """
    
    SUPPORTED_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.jxl', '.avif', '.gif')
    
    @staticmethod
    def pack_directory(directory_path: str, convert_psd: bool = True):
        """处理指定目录的单层打包
        
        Args:
            directory_path: 要处理的目录路径
            convert_psd: 是否在打包前转换PSD文件，默认为True
        """
        init_TextualLogger()
        try:
            directory_path = os.path.abspath(directory_path)
            if not os.path.exists(directory_path):
                logger.error(f"❌ 目录不存在: {directory_path}")
                return
                
            if not os.path.isdir(directory_path):
                logger.error(f"❌ 指定路径不是目录: {directory_path}")
                return
            
            # 在打包前处理PSD文件
            if convert_psd:
                logger.info(f"[#process]🔄 开始处理PSD文件")
                convert_psd_files(directory_path, use_recycle_bin=False)
                logger.info(f"[#process]✅ PSD处理完成")
                
            base_name = os.path.basename(directory_path)
            logger.info(f"[#process]🔄 开始处理目录: {directory_path}")
            
            # 获取一级目录内容
            items = os.listdir(directory_path)
            subdirs = []
            images = []
            
            for item in items:
                item_path = os.path.join(directory_path, item)
                if os.path.isdir(item_path):
                    subdirs.append(item_path)
                elif os.path.isfile(item_path) and item_path.lower().endswith(SinglePacker.SUPPORTED_IMAGE_EXTENSIONS):
                    images.append(item_path)
            
            # 计算总任务数
            total_tasks = len(subdirs) + (1 if images else 0)
            current_task = 0
            
            # 处理子文件夹
            for subdir in subdirs:
                current_task += 1
                progress = (current_task / total_tasks) * 100
                logger.info(f"[#cur_stats]总进度: ({current_task}/{total_tasks}) {progress:.1f}%")
                
                subdir_name = os.path.basename(subdir)
                archive_name = f"{subdir_name}.zip"
                archive_path = os.path.join(directory_path, archive_name)
                
                logger.info(f"[#cur_progress]🔄 打包子文件夹: {subdir_name}")
                if SinglePacker._create_archive(subdir, archive_path):
                    SinglePacker._cleanup_source(subdir)
            
            # 处理散图文件
            if images:
                current_task += 1
                progress = (current_task / total_tasks) * 100
                logger.info(f"[#cur_stats]总进度: ({current_task}/{total_tasks}) {progress:.1f}%")
                
                images_archive_name = f"{base_name}.zip"
                images_archive_path = os.path.join(directory_path, images_archive_name)
                
                # 创建临时目录存放图片
                with tempfile.TemporaryDirectory() as temp_dir:
                    for image in images:
                        shutil.copy2(image, temp_dir)
                    
                    logger.info(f"[#cur_progress]🔄 打包散图文件: {len(images)}个文件")
                    if SinglePacker._create_archive(temp_dir, images_archive_path):
                        # 删除原始图片文件
                        for image in images:
                            SinglePacker._cleanup_source(image)
            
            logger.info("[#process]✅ 打包完成")
            
        except Exception as e:
            logger.error(f"❌ 处理过程中出现错误: {str(e)}")
    
    @staticmethod
    def _create_archive(source_path: str, archive_path: str):
        """创建压缩包
        
        Args:
            source_path: 要打包的源路径
            archive_path: 目标压缩包路径
        """
        try:
            cmd = ['7z', 'a', '-tzip', archive_path, f"{source_path}\\*"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"❌ 创建压缩包失败: {archive_path}\n{result.stderr}")
                return False
            else:
                logger.info(f"[#file_ops]✅ 创建压缩包成功: {os.path.basename(archive_path)}")
                
                # 验证压缩包完整性
                logger.info(f"[#file_ops]🔄 正在验证压缩包完整性: {os.path.basename(archive_path)}")
                test_cmd = ['7z', 't', archive_path]
                test_result = subprocess.run(test_cmd, capture_output=True, text=True)
                
                if test_result.returncode != 0:
                    logger.error(f"❌ 压缩包验证失败: {archive_path}\n{test_result.stderr}")
                    return False
                else:
                    logger.info(f"[#file_ops]✅ 压缩包验证成功: {os.path.basename(archive_path)}")
                    return True
                
        except Exception as e:
            logger.error(f"❌ 创建压缩包时出现错误: {str(e)}")
            return False
            
    @staticmethod
    def _cleanup_source(source_path: str):
        """清理源文件或文件夹
        
        Args:
            source_path: 要清理的源路径
        """
        try:
            if os.path.isdir(source_path):
                shutil.rmtree(source_path)
                logger.info(f"[#file_ops]✅ 已删除源文件夹: {os.path.basename(source_path)}")
            elif os.path.isfile(source_path):
                os.remove(source_path)
                logger.info(f"[#file_ops]✅ 已删除源文件: {os.path.basename(source_path)}")
        except Exception as e:
            logger.error(f"❌ 清理源文件时出现错误: {str(e)}")
            
if "__main__" == __name__:
    import argparse
    import sys
    
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(
        description="单层目录打包工具 - 将指定目录下的一级子文件夹和散图分别打包",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    # 添加参数
    parser.add_argument(
        'directories',
        nargs='*',  # 改为可选参数
        help="要处理的目录路径，支持输入多个路径"
    )
    
    parser.add_argument(
        '--no-psd',
        action='store_true',
        help="不处理PSD文件（默认会处理）"
    )
    
    # 解析命令行参数
    args = parser.parse_args()
    
    directories = args.directories
    
    # 如果没有提供命令行参数，则进入交互式输入模式
    if not directories:
        print("请输入要处理的目录路径，每行一个，输入空行结束：")
        while True:
            line = input().strip().strip('"').strip("'")
            if not line:
                break
            directories.append(line)
    
    # 如果仍然没有输入任何路径，显示帮助信息并退出
    if not directories:
        parser.print_help()
        sys.exit(1)
    
    # 处理每个输入的目录
    for directory in directories:
        SinglePacker.pack_directory(directory, convert_psd=not args.no_psd)
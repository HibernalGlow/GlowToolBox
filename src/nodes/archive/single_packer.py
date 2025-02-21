import os
import logging
import shutil
import tempfile
import subprocess
from pathlib import Path

class SinglePacker:
    """单层目录打包工具
    
    只处理指定目录下的一级内容：
    1. 将每个一级子文件夹打包成独立的压缩包
    2. 将一级目录下的所有图片文件打包成一个压缩包
    3. 压缩包名称基于父文件夹名称
    """
    
    SUPPORTED_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.jxl', '.avif', '.gif')
    
    @staticmethod
    def pack_directory(directory_path: str):
        """处理指定目录的单层打包
        
        Args:
            directory_path: 要处理的目录路径
        """
        try:
            directory_path = os.path.abspath(directory_path)
            if not os.path.exists(directory_path):
                logging.error(f"❌ 目录不存在: {directory_path}")
                return
                
            if not os.path.isdir(directory_path):
                logging.error(f"❌ 指定路径不是目录: {directory_path}")
                return
                
            base_name = os.path.basename(directory_path)
            logging.info(f"开始处理目录: {directory_path}")
            
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
            
            # 处理子文件夹
            for subdir in subdirs:
                subdir_name = os.path.basename(subdir)
                archive_name = f"{subdir_name}.zip"
                archive_path = os.path.join(directory_path, archive_name)
                
                logging.info(f"打包子文件夹: {subdir_name}")
                SinglePacker._create_archive(subdir, archive_path)
            
            # 处理散图文件
            if images:
                images_archive_name = f"{base_name}_images.zip"
                images_archive_path = os.path.join(directory_path, images_archive_name)
                
                # 创建临时目录存放图片
                with tempfile.TemporaryDirectory() as temp_dir:
                    for image in images:
                        shutil.copy2(image, temp_dir)
                    
                    logging.info(f"打包散图文件: {len(images)}个文件")
                    SinglePacker._create_archive(temp_dir, images_archive_path)
            
            logging.info("✅ 打包完成")
            
        except Exception as e:
            logging.error(f"❌ 处理过程中出现错误: {str(e)}")
    
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
                logging.error(f"❌ 创建压缩包失败: {archive_path}\n{result.stderr}")
            else:
                logging.info(f"✅ 创建压缩包成功: {os.path.basename(archive_path)}")
                
        except Exception as e:
            logging.error(f"❌ 创建压缩包时出现错误: {str(e)}")
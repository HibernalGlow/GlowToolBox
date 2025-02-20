import os
import sys
import ctypes
import winreg
import logging
from pathlib import Path
import tempfile
import hashlib
import yaml
import shutil
import time
from typing import Dict, List, Tuple
import argparse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('long_path_check.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def check_windows_build():
    """检查Windows版本是否支持长路径"""
    try:
        if sys.platform != 'win32':
            return False, "不是Windows系统"
            
        win_ver = sys.getwindowsversion()
        build_number = win_ver.build
        logger.info(f"Windows Build Number: {build_number}")
        
        # Windows 10 (1607) 及以上版本支持长路径
        if build_number >= 14393:  # Windows 10 1607的构建号
            return True, f"Windows版本支持长路径 (Build {build_number})"
        else:
            return False, f"Windows版本过低，不支持长路径 (Build {build_number})"
    except Exception as e:
        return False, f"检查Windows版本时出错: {e}"

def check_registry_setting():
    """检查注册表中的长路径支持设置"""
    try:
        key_path = r"SYSTEM\CurrentControlSet\Control\FileSystem"
        value_name = "LongPathsEnabled"
        
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, 
                           winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
            
        if value == 1:
            return True, "注册表已启用长路径支持"
        else:
            return False, "注册表未启用长路径支持"
    except Exception as e:
        return False, f"检查注册表设置时出错: {e}"

def check_python_support():
    """检查Python是否支持长路径"""
    try:
        # 检查Python版本
        py_ver = sys.version_info
        logger.info(f"Python版本: {sys.version}")
        
        if py_ver.major >= 3 and py_ver.minor >= 6:
            return True, f"Python版本支持长路径 (v{py_ver.major}.{py_ver.minor})"
        else:
            return False, f"Python版本过低，不完全支持长路径 (v{py_ver.major}.{py_ver.minor})"
    except Exception as e:
        return False, f"检查Python支持时出错: {e}"

def test_long_path_creation():
    """测试创建长路径文件"""
    try:
        # 创建临时目录
        temp_dir = tempfile.mkdtemp(prefix="long_path_test_")
        base_path = Path(temp_dir)
        
        # 创建一个非常长的路径（超过260个字符）
        deep_dirs = "a" * 50  # 50个字符的目录名
        test_dirs = []
        current_path = base_path
        
        # 创建5层深的目录，每层50个字符
        for i in range(5):
            current_path = current_path / f"{deep_dirs}_{i}"
            test_dirs.append(current_path)
        
        # 尝试创建目录
        for dir_path in test_dirs:
            os.makedirs(dir_path, exist_ok=True)
            
        # 在最深层创建测试文件
        test_file = current_path / "test.txt"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("Test long path")
            
        # 计算最终路径长度
        final_path_len = len(str(test_file))
        
        # 清理测试目录
        import shutil
        shutil.rmtree(base_path)
        
        return True, f"成功创建并访问长路径（{final_path_len}字符）"
    except Exception as e:
        return False, f"测试长路径创建失败: {e}"

def check_api_support():
    """检查Windows API是否支持长路径"""
    try:
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        
        # 检查是否存在相关API
        if hasattr(kernel32, 'GetLongPathNameW'):
            return True, "Windows API支持长路径"
        else:
            return False, "Windows API不完全支持长路径"
    except Exception as e:
        return False, f"检查Windows API支持时出错: {e}"

class LongPathHandler:
    def __init__(self, yaml_path: str = "long_paths_mapping.yaml"):
        self.yaml_path = yaml_path
        self.mapping: Dict[str, str] = {}
        self.load_mapping()

    def load_mapping(self) -> None:
        """从YAML文件加载映射关系"""
        if os.path.exists(self.yaml_path):
            try:
                with open(self.yaml_path, 'r', encoding='utf-8') as f:
                    self.mapping = yaml.safe_load(f) or {}
                logger.info(f"已加载 {len(self.mapping)} 个映射关系")
            except Exception as e:
                logger.error(f"加载YAML文件失败: {e}")
                self.mapping = {}
        else:
            self.mapping = {}

    def save_mapping(self) -> None:
        """保存映射关系到YAML文件"""
        try:
            with open(self.yaml_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(self.mapping, f, allow_unicode=True)
            logger.info(f"已保存 {len(self.mapping)} 个映射关系到 {self.yaml_path}")
        except Exception as e:
            logger.error(f"保存YAML文件失败: {e}")

    def generate_md5_name(self, original_path: str) -> str:
        """生成MD5文件名"""
        original_name = os.path.basename(original_path)
        md5_hash = hashlib.md5(original_name.encode()).hexdigest()
        ext = os.path.splitext(original_name)[1]
        return f"md5-{md5_hash[:8]}{ext}"

    def rename_to_md5(self, file_path: str) -> Tuple[str, str]:
        """将文件重命名为MD5格式"""
        try:
            dir_path = os.path.dirname(file_path)
            original_name = os.path.basename(file_path)
            md5_name = self.generate_md5_name(file_path)
            new_path = os.path.join(dir_path, md5_name)

            # 检查是否已经存在相同的MD5文件名
            counter = 1
            while os.path.exists(new_path):
                base_name = os.path.splitext(md5_name)[0]
                ext = os.path.splitext(md5_name)[1]
                md5_name = f"{base_name}-{counter}{ext}"
                new_path = os.path.join(dir_path, md5_name)
                counter += 1

            # 重命名文件
            os.rename(file_path, new_path)
            logger.info(f"已重命名: {original_name} -> {md5_name}")
            
            # 更新映射关系
            self.mapping[md5_name] = original_name
            self.save_mapping()
            
            return new_path, md5_name
        except Exception as e:
            logger.error(f"重命名文件失败 {file_path}: {e}")
            return file_path, os.path.basename(file_path)

    def restore_original_name(self, md5_path: str) -> str:
        """恢复原始文件名"""
        try:
            dir_path = os.path.dirname(md5_path)
            md5_name = os.path.basename(md5_path)
            
            if md5_name not in self.mapping:
                logger.warning(f"未找到映射关系: {md5_name}")
                return md5_path
                
            original_name = self.mapping[md5_name]
            original_path = os.path.join(dir_path, original_name)
            
            # 检查目标文件是否存在
            if os.path.exists(original_path):
                logger.warning(f"目标文件已存在: {original_path}")
                return md5_path
                
            # 恢复原始文件名
            os.rename(md5_path, original_path)
            logger.info(f"已恢复: {md5_name} -> {original_name}")
            
            # 从映射中删除
            del self.mapping[md5_name]
            self.save_mapping()
            
            return original_path
        except Exception as e:
            logger.error(f"恢复文件名失败 {md5_path}: {e}")
            return md5_path

    def process_directory(self, directory: str, max_length: int = 64) -> List[str]:
        """处理目录中的长文件名"""
        renamed_files = []
        try:
            for root, _, files in os.walk(directory):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in ['.zip', '.cbz']):
                        file_path = os.path.join(root, file)
                        if len(file) > max_length:
                            new_path, _ = self.rename_to_md5(file_path)
                            renamed_files.append(new_path)
            return renamed_files
        except Exception as e:
            logger.error(f"处理目录失败 {directory}: {e}")
            return renamed_files

    def restore_all(self, directory: str) -> None:
        """恢复目录中所有被重命名的文件"""
        try:
            restored_count = 0
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.startswith('md5-') and any(file.lower().endswith(ext) for ext in ['.zip', '.cbz']):
                        file_path = os.path.join(root, file)
                        if self.restore_original_name(file_path) != file_path:
                            restored_count += 1
            logger.info(f"已恢复 {restored_count} 个文件的原始名称")
        except Exception as e:
            logger.error(f"恢复目录失败 {directory}: {e}")

def main():
    parser = argparse.ArgumentParser(description='长文件名处理工具')
    parser.add_argument('directory', help='要处理的目录路径')
    parser.add_argument('--restore', '-r', action='store_true', help='恢复原始文件名')
    parser.add_argument('--max-length', '-m', type=int, default=64, help='最大文件名长度（默认64）')
    parser.add_argument('--yaml-path', '-y', default='long_paths_mapping.yaml', help='YAML映射文件路径')
    
    args = parser.parse_args()
    
    handler = LongPathHandler(args.yaml_path)
    
    if args.restore:
        handler.restore_all(args.directory)
    else:
        handler.process_directory(args.directory, args.max_length)

if __name__ == '__main__':
    main() 
import os
import logging
import subprocess
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import yaml
from datetime import datetime
import warnings
import argparse
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import radiolist_dialog
from prompt_toolkit.styles import Style
import pyperclip
import zipfile
from pathlib import Path
import sys

# 添加项目根目录到Python路径
from nodes.tui.textual_logger import TextualLoggerManager
from nodes.record.logger_config import setup_logger
from nodes.tui.textual_preset import create_config_app
# 设置日志记录器
config = {
    'script_name': 'name',
    'console_enabled': False
}
logger, config_info = setup_logger(config)

# 定义布局配置
TEXTUAL_LAYOUT = {
    "current_stats": {  # 总体进度面板
        "ratio": 2,     
        "title": "📊 总体进度",  
        "style": "lightyellow"  
    },
    "current_progress": {  # 当前进度面板
        "ratio": 2,
        "title": "🔄 当前进度",
        "style": "lightcyan"
    },
    "process": {  # 处理日志面板
        "ratio": 3,
        "title": "📝 处理日志",
        "style": "lightmagenta"
    },
    "update": {  # 更新日志面板
        "ratio": 2,
        "title": "ℹ️ 更新日志",
        "style": "lightblue"
    }
}

# 初始化布局
def init_textuallogger():
    TextualLoggerManager.set_layout(TEXTUAL_LAYOUT, config_info['log_file'])

# 清理旧日志

class Config:
    # 示例: python auto_unzip.py -i jpg png
    def __init__(self):
        # 添加命令行参数解析
        parser = argparse.ArgumentParser(description='文件解压缩工具')
        parser.add_argument('-c', '--clipboard', action='store_true', help='从剪贴板读取路径')
        parser.add_argument('-i', '--include', nargs='+', help='包含的文件格式列表 (例如: jpg png)')
        parser.add_argument('-e', '--exclude', nargs='+', help='排除的文件格式列表 (例如: gif mp4)')
        parser.add_argument('-m', '--mode', choices=['1', '2'], help='处理模式 (1:解压, 2:压缩)')
        parser.add_argument('-d', '--disable-zipfile', action='store_true', help='禁用zipfile检查')
        parser.add_argument('-a', '--archive-types', nargs='+', 
                          choices=['zip', 'cbz', 'rar', 'cbr', '7z'],
                          help='指定要处理的压缩包格式 (例如: zip cbz)')
        
        # 保存解析器
        self.parser = parser
        
        # 基本配置
        self.yaml_file = r"E:\1EHV\file_timestamps.yaml"
        self.compress_prefix = "[#a]"
        self.error_prefix = "[#e]"
        self.damaged_suffix = ".tdel"
        self.seven_zip_path = r"C:\Program Files\7-Zip\7z.exe"
        
        # 这些选项直接在代码中设置，不需要命令行参数
        self.delete_source = True
        self.use_recycle_bin = True  # 改为默认启用
        self.mark_failed = True      # 改为默认启用
        
        # 初始化参数相关的属性
        self.args = None
        self.include_formats = []
        self.exclude_formats = []
        self.disable_zipfile = False
        self.archive_types = None
        self.source_directories = []
        
        # 初始化日志
        
    def parse_args(self, args=None):
        """解析命令行参数并更新配置"""
        self.args = self.parser.parse_args(args)
        
        # 更新配置
        self.include_formats = self.args.include if self.args.include else []
        self.exclude_formats = self.args.exclude if self.args.exclude else []
        self.disable_zipfile = self.args.disable_zipfile
        self.archive_types = self._get_archive_types()
        
        # 获取源目录
        self.source_directories = self._get_multiple_paths()
        
        return self.args

    def _get_multiple_paths(self):
        """获取多个路径输入，支持剪贴板和手动输入"""
        paths = []
        
        # 从剪贴板读取路径
        if self.args and self.args.clipboard:
            try:
                clipboard_content = pyperclip.paste()
                if clipboard_content:
                    clipboard_paths = [p.strip().strip('"') for p in clipboard_content.splitlines() if p.strip()]
                    for path in clipboard_paths:
                        try:
                            normalized_path = os.path.normpath(path)
                            if os.path.exists(normalized_path):
                                paths.append(normalized_path)
                                logging.info(f"[#process]📎 从剪贴板读取路径: {normalized_path}")
                        except Exception as e:
                            logging.warning(f"[#update]⚠️ 警告: 路径处理失败 - {path}")
                            logging.error(f"[#update]❌ 错误信息: {str(e)}")
                else:
                    logging.warning("[#update]⚠️ 剪贴板为空")
            except Exception as e:
                logging.warning(f"[#update]⚠️ 警告: 剪贴板读取失败: {str(e)}")
        
        # 如果没有使用剪贴板或剪贴板为空，使用简单的input输入
        if not paths:
            logging.info("[#process]📝 请输入目录或压缩包路径（每行一个，输入空行结束）:")
            while True:
                path = input().strip().strip('"')
                if not path:  # 空行结束输入
                    break
                    
                try:
                    path = path.strip().strip('"')
                    normalized_path = os.path.normpath(path)
                    
                    if os.path.exists(normalized_path):
                        paths.append(normalized_path)
                        logging.info(f"[#process]✅ 已添加路径: {normalized_path}")
                    else:
                        logging.warning(f"[#update]⚠️ 警告: 路径不存在 - {path}")
                except Exception as e:
                    logging.warning(f"[#update]⚠️ 警告: 路径处理失败 - {path}")
                    logging.error(f"[#update]❌ 错误信息: {str(e)}")

        if not paths:
            logging.error("[#update]❌ 未输入有效路径")
            raise ValueError("未输入有效路径")
        return paths

    def _get_archive_types(self):
        """获取要处理的压缩包格式列表"""
        if self.args.archive_types:
            # 将cbz和cbr也映射到zip和rar
            types = set()
            for t in self.args.archive_types:
                if t in ['zip', 'cbz']:
                    types.add('.zip')
                    types.add('.cbz')
                elif t in ['rar', 'cbr']:
                    types.add('.rar')
                    types.add('.cbr')
                elif t == '7z':
                    types.add('.7z')
            return list(types)
        else:
            # 默认支持所有格式
            return ['.zip', '.cbz', '.rar', '.cbr', '.7z']


class TimestampManager:
    def __init__(self, yaml_file):
        self.yaml_file = yaml_file
        self.file_timestamps = self._load_yaml()
        
    def _load_yaml(self):
        if os.path.exists(self.yaml_file):
            with open(self.yaml_file, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file) or {}
        return {}
    
    def save_yaml(self):
        with open(self.yaml_file, 'w', encoding='utf-8') as file:
            yaml.safe_dump(self.file_timestamps, file, allow_unicode=True)
            
    def record_timestamp(self, file_path):
        self.file_timestamps[file_path] = os.path.getmtime(file_path)
        self.save_yaml()
        
    def restore_timestamp(self, file_path):
        if file_path in self.file_timestamps:
            timestamp = self.file_timestamps[file_path]
            os.utime(file_path, (timestamp, timestamp))
            logging.info(f"已恢复时间戳: {file_path} -> {datetime.fromtimestamp(timestamp)}")
        else:
            logging.warning(f"未找到时间戳记录: {file_path}")

class ArchiveProcessor:
    def __init__(self, config):
        self.config = config
        self.lock = Lock()
        self.timestamp_manager = TimestampManager(config.yaml_file)
        warnings.filterwarnings('ignore', message='File is not a zip file')
        self.supported_extensions = ['.zip', '.cbz','.rar','.cbr']
        
    def should_process_archive(self, archive_path):
        """检查压缩包是否需要处理"""
        if self.config.disable_zipfile:
            return True
            
        try:
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                all_files = zip_ref.namelist()
                
                # 如果同时设置了包含和排除格式，优先使用包含模式
                if self.config.include_formats and self.config.exclude_formats:
                    logging.warning("[#update]⚠️ 同时设置了包含和排除格式，将优先使用包含模式")
                    self.exclude_formats = []
                
                # 检查是否存在排除格式
                if self.config.exclude_formats:
                    exclude_files = [
                        file for file in all_files 
                        if file.lower().endswith(tuple(f'.{fmt.lower()}' for fmt in self.config.exclude_formats))
                    ]
                    if exclude_files:
                        logging.warning(
                            f"[#update]⏭️ 跳过包含排除格式的压缩包: {archive_path}\n"
                            f"   发现排除文件: {', '.join(exclude_files[:3])}{'...' if len(exclude_files) > 3 else ''}"
                        )
                        return False
                
                # 检查是否包含指定格式
                if self.config.include_formats:
                    include_files = [
                        file for file in all_files 
                        if file.lower().endswith(tuple(f'.{fmt.lower()}' for fmt in self.config.include_formats))
                    ]
                    if not include_files:
                        logging.warning(
                            f"[#update]⏭️ 跳过不包含指定格式的压缩包: {archive_path}\n"
                            f"   需要包含以下格式之一: {', '.join(self.config.include_formats)}"
                        )
                        return False
                    else:
                        logging.info(
                            f"[#process]✅ 发现目标文件: {', '.join(include_files[:3])}{'...' if len(include_files) > 3 else ''}"
                        )
                    
                return True
                
        except zipfile.BadZipFile:
            logging.error(f"[#update]❌ 损坏的压缩包: {archive_path}")
            return False
        except Exception as e:
            logging.error(f"[#update]❌ 检查压缩包出错: {archive_path}, 错误: {str(e)}")
            return False

    def decompress(self, archive_path):
        try:
            if not self.should_process_archive(archive_path):
                return
                
            logging.info(f"[#process]🔄 开始解压: {archive_path}")
            self.timestamp_manager.record_timestamp(archive_path)
            
            # 准备解压路径
            base_name = os.path.basename(archive_path)
            for ext in self.supported_extensions:
                base_name = base_name.replace(ext, '')
            extract_path = os.path.join(
                os.path.dirname(archive_path), 
                f"{self.config.compress_prefix}{base_name}"
            )
            
            logging.info(f"[#process]📂 解压目标路径: {extract_path}")
            
            # 使用7-Zip解压
            cmd = f'"{self.config.seven_zip_path}" x "{archive_path}" -o"{extract_path}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode != 0:
                error_msg = result.stderr.lower()
                if "cannot open the file as archive" in error_msg or "is not supported archive" in error_msg:
                    damaged_path = archive_path + self.config.damaged_suffix
                    with self.lock:
                        if not os.path.exists(damaged_path):
                            os.rename(archive_path, damaged_path)
                            logging.error(f"[#update]❌ 文件损坏: {archive_path} -> {damaged_path}")
                elif "cannot open" in error_msg:
                    logging.error(f"[#update]❌ 文件被占用，跳过: {archive_path}")
                else:
                    raise Exception(f"解压失败: {result.stderr}")
                return
            
            # 成功后处理源文件
            if self.config.delete_source:
                with self.lock:
                    self._delete_file(archive_path)
            
            logging.info(f"[#update]✅ 解压完成: {archive_path} -> {extract_path}")
            
        except Exception as e:
            if self.config.mark_failed:
                error_path = os.path.join(
                    os.path.dirname(archive_path), 
                    f"{self.config.error_prefix}{os.path.basename(archive_path)}"
                )
                with self.lock:
                    if not os.path.exists(error_path):
                        os.rename(archive_path, error_path)
                        logging.error(f"[#update]❌ 处理失败并已标记: {archive_path} -> {error_path}")
            else:
                logging.error(f"[#update]❌ 处理失败: {archive_path}")
            logging.error(f"[#update]❌ 错误详情: {str(e)}")

    def _delete_file(self, file_path):
        """安全删除文件"""
        try:
            if self.config.use_recycle_bin and hasattr(self, 'send2trash'):
                self.send2trash(file_path)
                logging.info(f"[#process]🗑️ 已将文件移至回收站: {file_path}")
            else:
                os.remove(file_path)
                logging.info(f"[#process]🗑️ 已永久删除文件: {file_path}")
        except Exception as e:
            logging.error(f"[#update]❌ 删除文件失败: {file_path}, 错误: {str(e)}")

    def compress(self, folder_path):
        try:
            logging.info(f"[#process]🔄 开始压缩: {folder_path}")
            folder_name = os.path.basename(folder_path).replace(self.config.compress_prefix, '')
            archive_path = os.path.join(os.path.dirname(folder_path), f"{folder_name}.zip")
            
            logging.info(f"[#process]📦 压缩目标路径: {archive_path}")
            
            cmd = f'"{self.config.seven_zip_path}" a -tzip "{archive_path}" "{folder_path}\\*" -r -sdel'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"压缩失败: {result.stderr}")
            
            # 成功后处理源文件夹
            if not os.listdir(folder_path):
                with self.lock:
                    if self.config.delete_source:
                        if self.config.use_recycle_bin and hasattr(self, 'send2trash'):
                            self.send2trash(folder_path)
                            logging.info(f"[#process]🗑️ 已将空文件夹移至回收站: {folder_path}")
                        else:
                            os.rmdir(folder_path)
                            logging.info(f"[#process]🗑️ 已删除空文件夹: {folder_path}")
            
            self.timestamp_manager.restore_timestamp(archive_path)
            logging.info(f"[#update]✅ 压缩完成: {folder_path} -> {archive_path}")
            
        except Exception as e:
            if self.config.mark_failed:
                error_path = os.path.join(
                    os.path.dirname(folder_path), 
                    f"{self.config.error_prefix}{os.path.basename(folder_path)}"
                )
                with self.lock:
                    if not os.path.exists(error_path):
                        os.rename(folder_path, error_path)
                        logging.error(f"[#update]❌ 压缩失败并已标记: {folder_path} -> {error_path}")
            else:
                logging.error(f"[#update]❌ 压缩失败: {folder_path}")
            logging.error(f"[#update]❌ 错误详情: {str(e)}")

class BatchProcessor:
    def __init__(self, config):
        self.config = config
        self.processor = ArchiveProcessor(config)
        
    def process_all(self, mode='decompress'):
        if mode == 'decompress':
            self._process_zips()
        else:
            self._process_folders()
            
    def _process_zips(self):
        archive_files = []
        logging.info("[#process]🔍 正在扫描压缩文件...")
        
        # 显示当前支持的格式
        logging.info(
            f"[#process]📦 当前处理的压缩包格式: {', '.join(fmt.lstrip('.') for fmt in self.config.archive_types)}"
        )
        
        for path in self.config.source_directories:
            if os.path.isfile(path):
                ext = os.path.splitext(path)[1].lower()
                if ext in self.config.archive_types:
                    archive_files.append(path)
                    logging.info(f"[#process]📄 找到压缩文件: {path}")
                else:
                    logging.warning(f"[#update]⏭️ 跳过不支持的格式: {path}")
            elif os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for file in files:
                        ext = os.path.splitext(file)[1].lower()
                        if ext in self.config.archive_types:
                            full_path = os.path.join(root, file)
                            archive_files.append(full_path)
                            logging.info(f"[#process]📄 找到压缩文件: {full_path}")
        
        total_files = len(archive_files)
        if not archive_files:
            logging.warning("[#update]⚠️ 未找到符合条件的压缩文件")
            return
            
        logging.info(f"[#process]📊 共找到 {total_files} 个压缩文件待处理")
        
        # 更新总体进度
        logging.info(f"[#current_stats]总文件数: {total_files}")
        
        # 处理文件
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(self.processor.decompress, archive_path)
                for archive_path in archive_files
            ]
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                # 更新进度条
                percentage = (completed / total_files) * 100
                logging.info(f"[@current_progress]解压进度 ({completed}/{total_files}) {percentage:.1f}%")
                future.result()
                # 更新总体进度
                logging.info(f"[#current_stats]已处理: {completed}/{total_files}")
                    
    def _process_folders(self):
        folders = []
        logging.info("[#process]🔍 正在扫描待压缩文件夹...")
        
        for path in self.config.source_directories:
            if os.path.isdir(path):
                if os.path.basename(path).startswith(self.config.compress_prefix):
                    folders.append(path)
                    logging.info(f"[#process]📁 找到待压缩文件夹: {path}")
                    continue
                
                for root, dirs, _ in os.walk(path):
                    for dir_name in dirs:
                        if dir_name.startswith(self.config.compress_prefix):
                            full_path = os.path.join(root, dir_name)
                            folders.append(full_path)
                            logging.info(f"[#process]📁 找到待压缩文件夹: {full_path}")
        
        total_folders = len(folders)
        if not folders:
            logging.warning("[#update]⚠️ 未找到需要处理的文件夹")
            return
            
        logging.info(f"[#process]📊 共找到 {total_folders} 个文件夹待处理")
        
        # 更新总体进度
        logging.info(f"[#current_stats]总文件夹数: {total_folders}")
        
        # 处理文件夹
        with ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(self.processor.compress, folder_path)
                for folder_path in folders
            ]
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                # 更新进度条
                percentage = (completed / total_folders) * 100
                logging.info(f"[@current_progress]压缩进度 ({completed}/{total_folders}) {percentage:.1f}%")
                future.result()
                # 更新总体进度
                logging.info(f"[#current_stats]已处理: {completed}/{total_folders}")

def select_mode():
    """使用 prompt_toolkit 的 radiolist_dialog 选择模式"""
    style = Style.from_dict({
        'dialog': 'bg:#4444ff #ffffff',
        'dialog frame.label': 'bg:#ffffff #000000',
        'dialog.body': 'bg:#ffffff #000000',
        'dialog shadow': 'bg:#000000',
    })

    result = radiolist_dialog(
        title='选择操作模式',
        text='请选择要执行的操作:',
        values=[
            ('1', '解压模式'),
            ('2', '压缩模式'),
        ],
        style=style
    ).run()
    
    return result

def main():
    """主函数"""
    # 创建配置对象
    config = Config()
    
    # 检查是否有命令行参数（除了程序名称外的参数）
    has_args = len(sys.argv) > 1
    
    if has_args:
        # 解析命令行参数
        config.parse_args()
        
        # 如果指定了模式，直接使用；否则通过对话框选择
        mode = config.args.mode if config.args.mode else select_mode()
        if mode is None:  # 用户取消
            return
            
        # 直接执行处理
        processor = BatchProcessor(config)
        processor.process_all('decompress' if mode == '1' else 'compress')
        return
    
    # 没有命令行参数时启动TUI界面

    # 定义复选框选项
    checkbox_options = [
        ("从剪贴板读取路径", "clipboard", "--clipboard", True),
        ("禁用zipfile检查", "disable_zipfile", "--disable-zipfile", False),
    ]

    # 定义输入框选项
    input_options = [
        ("处理模式", "mode", "--mode", "1", "1:解压 2:压缩"),
        ("包含格式", "include", "--include", "", "例如: jpg png"),
        ("排除格式", "exclude", "--exclude", "", "例如: gif mp4"),
        ("压缩包格式", "archive_types", "--archive-types", "", "zip/cbz/rar/cbr/7z"),
    ]

    # 预设配置
    preset_configs = {
        "解压-全部": {
            "description": "解压所有支持的压缩包",
            "checkbox_options": ["clipboard"],
            "input_values": {
                "mode": "1",
                "include": "",
                "exclude": "",
                "archive_types": ""
            }
        },
        "压缩-标准": {
            "description": "压缩带[#a]前缀的文件夹",
            "checkbox_options": ["clipboard"],
            "input_values": {
                "mode": "2",
                "include": "",
                "exclude": "",
                "archive_types": ""
            }
        },
        "解压-cbz": {
            "description": "解压cbz压缩包",
            "checkbox_options": ["clipboard"],
            "input_values": {
                "mode": "1",
                "archive_types": "cbz"
            }
        },
        "解压-cbr": {
            "description": "解压cbz压缩包",
            "checkbox_options": ["clipboard"],
            "input_values": {
                "mode": "1",
                "archive_types": "cbr"
            }
        }
    }

    # 创建配置界面
    app = create_config_app(
        program=f'"{os.path.abspath(__file__)}"',  # 使用绝对路径并用引号包裹
        checkbox_options=checkbox_options,
        input_options=input_options,
        title="压缩包处理配置",
        preset_configs=preset_configs
    )
    
    app.run()

if __name__ == "__main__":
    main()
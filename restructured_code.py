"""
重组后的代码文件
根据目标结构自动生成
"""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from diff_match_patch import diff_match_patch
from nodes.record.logger_config import setup_logger
from nodes.tui.textual_logger import TextualLoggerManager
from nodes.tui.textual_preset import create_config_app
from opencc import OpenCC
from pathlib import Path
from queue import Queue
from rapidfuzz import fuzz, process
import argparse
import ctypes
import difflib
import functools
import logging
import os
import os
import pyperclip
import re
import shutil
import signal
import subprocess
import sys
import sys
import tempfile
import threading
import time
import win32api

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEXTUAL_LAYOUT = {'current_stats': {'ratio': 2, 'title': '📊 总体进度', 'style': 'lightyellow'}, 'current_progress': {'ratio': 2, 'title': '🔄 当前进度', 'style': 'lightcyan'}, 'process': {'ratio': 3, 'title': '📝 处理日志', 'style': 'lightpink'}, 'update': {'ratio': 2, 'title': 'ℹ️ 更新日志', 'style': 'lightblue'}}
config = {'script_name': 'comic_auto_uuid', 'console_enabled': False}
cc_t2s = OpenCC('t2s')
cc_s2t = OpenCC('s2t')
CATEGORY_RULES = {'1. 同人志': {'patterns': ['\\[C\\d+\\]', '\\(C\\d+\\)', 'コミケ\\d+', 'COMIC\\s*MARKET', 'COMIC1', '同人誌', '同人志', 'コミケ', 'コミックマーケット', '例大祭', 'サンクリ', '(?i)doujin', 'COMIC1☆\\d+'], 'exclude_patterns': ['画集', 'artbook', 'art\\s*works', '01视频', '02动图', 'art\\s*works']}, '2. 商业志': {'patterns': ['(?i)magazine', '(?i)COMIC', '雑誌', '杂志', '商业', '週刊', '月刊', '月号', 'COMIC\\s*REX', 'コミック', 'ヤングマガジン', '\\d{4}年\\d{1,2}月号'], 'exclude_patterns': ['同人', '(?i)doujin', '単行本', '画集']}, '3. 单行本': {'patterns': ['単行本', '单行本', '(?i)tankoubon', '第\\d+巻', 'vol\\.?\\d+', 'volume\\s*\\d+'], 'exclude_patterns': ['画集', 'artbook', 'art\\s*works']}, '4. 画集': {'patterns': ['画集', '(?i)art\\s*book', '(?i)art\\s*works', 'イラスト集', '杂图合集', '作品集', 'illustrations?', '(?i)illust\\s*collection'], 'exclude_patterns': []}, '5. 同人CG': {'patterns': ['同人CG'], 'exclude_patterns': []}}
if sys.platform == 'win32':
    try:
        import win32api

        def win32_path_exists(path):
            try:
                win32api.GetFileAttributes(path)
                return True
            except:
                print('未安装win32api模块，某些路径可能无法正确处理')
                win32_path_exists = os.path.exists
    except ImportError:
        print('未安装win32api模块，某些路径可能无法正确处理')
        win32_path_exists = os.path.exists
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.jxl', '.avif', '.heic', '.heif', '.jfif', '.tiff', '.tif', '.psd', '.xcf'}
SERIES_PREFIXES = {'[#s]', '#'}
PATH_BLACKLIST = {'画集', '01视频', '02动图', '损坏压缩包'}
SERIES_BLACKLIST_PATTERNS = ['画集', 'fanbox', 'pixiv', '・', '杂图合集', '01视频', '02动图', '作品集', '01视频', '02动图', '损坏压缩包']
SIMILARITY_CONFIG = {'THRESHOLD': 75, 'LENGTH_DIFF_MAX': 0.3, 'RATIO_THRESHOLD': 75, 'PARTIAL_THRESHOLD': 85, 'TOKEN_THRESHOLD': 80}
if __name__ == '__main__':
    main()

class Config:
    """
    类描述
    """

class Logger:
    """
    类描述
    """

class PathManager:
    """
    类描述
    """

class ImageAnalyzer:
    """
    类描述
    """

class ImageProcessor:
    """
    类描述
    """

class DuplicateDetector:
    """
    类描述
    """

class FileNameHandler:
    """
    类描述
    """

class DirectoryHandler:
    """
    类描述
    """

class ArchiveExtractor:
    """
    类描述
    """

class ArchiveCompressor:
    """
    类描述
    """

class ArchiveProcessor:
    """
    类描述
    """

class ProcessedLogHandler:
    """
    类描述
    """

class BackupHandler:
    """
    类描述
    """

class ContentFilter:
    """
    类描述
    """

class ProgressTracker:
    """
    类描述
    """

class InputHandler:
    """
    类描述
    """

class ProcessManager:
    """
    类描述
    """

class MangaClassifier:
    """
    类描述
    """

class Utils:
    """
    类描述
    """

class UnclassifiedFunctions:
    """
    未分类的函数集合
    """

    def normalize_filename(self, filename):
        """去除文件名中的圆括号、方括号及其内容，返回规范化的文件名"""
        name = os.path.splitext(filename)[0]
        name = re.sub('\\[[^\\]]*\\]', '', name)
        name = re.sub('\\([^)]*\\)', '', name)
        name = re.sub('vol\\.?|第|巻|卷', '', name, flags=re.IGNORECASE)
        name = re.sub('[\\s!！?？_~～]+', ' ', name)
        name = name.strip()
        return name

    def is_similar_to_existing_folder(self, dir_path, series_name, handler=None):
        """检查是否存在相似的文件夹名称"""
        try:
            existing_folders = [d for d in os.listdir(dir_path) if os.path.isdir(os.path.join(dir_path, d))]
        except Exception as e:
            logger.error(f'[#update] ❌ 读取目录失败: {dir_path}')
            return False
        series_key = UnclassifiedFunctions.get_series_key(series_name)
        for folder in existing_folders:
            is_series_folder = False
            folder_name = folder
            for prefix in SERIES_PREFIXES:
                if folder.startswith(prefix):
                    folder_name = folder[len(prefix):]
                    is_series_folder = True
                    break
            if is_series_folder:
                folder_key = UnclassifiedFunctions.get_series_key(folder_name, handler)
                if series_key == folder_key:
                    if handler:
                        handler.update_panel('update_log', f"📁 找到相同系列文件夹: '{folder}'")
                    return True
                similarity = UnclassifiedFunctions.calculate_similarity(series_key, folder_key, handler)
                if similarity >= SIMILARITY_CONFIG['THRESHOLD']:
                    if handler:
                        handler.update_panel('update_log', f"📁 找到相似文件夹: '{folder}'")
                    return True
            else:
                similarity = UnclassifiedFunctions.calculate_similarity(series_name, folder, handler)
                if similarity >= SIMILARITY_CONFIG['THRESHOLD']:
                    if handler:
                        handler.update_panel('update_log', f"📁 找到相似文件夹: '{folder}'")
                    return True
        return False

    def preprocess_filenames(self, files, handler=None):
        """预处理所有文件名"""
        file_keys = {}
        for file_path in files:
            key = UnclassifiedFunctions.get_series_key(os.path.basename(file_path))
            file_keys[file_path] = key
            logger.info(f'[#update] 🔄 预处理: {os.path.basename(file_path)} -> {key}')
        return file_keys

    def find_similar_files(self, current_file, files, file_keys, processed_files, handler=None):
        """查找与当前文件相似的文件"""
        current_key = file_keys[current_file]
        similar_files = [current_file]
        to_process = set()
        if not current_key.strip():
            return (similar_files, to_process)
        for other_file in files:
            if other_file in processed_files or other_file == current_file:
                continue
            if UnclassifiedFunctions.is_in_series_folder(other_file):
                continue
            if UnclassifiedFunctions.is_essentially_same_file(current_file, other_file):
                to_process.add(other_file)
                continue
            other_key = file_keys[other_file]
            if not other_key.strip():
                continue
            ratio = fuzz.ratio(current_key.lower(), other_key.lower())
            partial = fuzz.partial_ratio(current_key.lower(), other_key.lower())
            token = fuzz.token_sort_ratio(current_key.lower(), other_key.lower())
            len_diff = abs(len(current_key) - len(other_key)) / max(len(current_key), len(other_key))
            is_similar = ratio >= SIMILARITY_CONFIG['RATIO_THRESHOLD'] and partial >= SIMILARITY_CONFIG['PARTIAL_THRESHOLD'] and (token >= SIMILARITY_CONFIG['TOKEN_THRESHOLD']) and (len_diff <= SIMILARITY_CONFIG['LENGTH_DIFF_MAX'])
            if is_similar:
                logger.info(f'[#update] ✨ 发现相似文件: {os.path.basename(other_file)} (相似度: {max(ratio, partial, token)}%)')
                similar_files.append(other_file)
                to_process.add(other_file)
        return (similar_files, to_process)

    def find_keyword_based_groups(self, remaining_files, file_keys, processed_files, handler=None):
        """基于关键词查找系列组"""
        keyword_groups = defaultdict(list)
        file_keywords = {}
        to_process = set()
        for file_path in remaining_files:
            if file_path in processed_files:
                continue
            keywords = UnclassifiedFunctions.extract_keywords(os.path.basename(file_path))
            if len(keywords) >= 1:
                file_keywords[file_path] = keywords
    
        def process_file_keywords(self, args):
            file_path, keywords = args
            if file_path in processed_files:
                return None
            current_group = [file_path]
            group_keywords = set(keywords)
            current_to_process = set()
            for other_path, other_keywords in file_keywords.items():
                if other_path == file_path or other_path in processed_files:
                    continue
                common_keywords = set(keywords) & set(other_keywords)
                if common_keywords and any((len(k) > 1 for k in common_keywords)):
                    current_group.append(other_path)
                    current_to_process.add(other_path)
                    group_keywords &= set(other_keywords)
            if len(current_group) > 1:
                series_name = max(group_keywords, key=len) if group_keywords else max(keywords, key=len)
                return (series_name, current_group, current_to_process)
            return None
        with ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(process_file_keywords, file_keywords.items()))
        for result in results:
            if result:
                series_name, group, current_to_process = result
                logger.info(f'[#update] 📚 发现系列: {series_name} ({len(group)}个文件)')
                for file_path in group:
                    logger.info(f'[#update]   └─ {os.path.basename(file_path)}')
                keyword_groups[series_name] = group
                to_process.update(current_to_process)
                to_process.add(group[0])
        return (keyword_groups, to_process)

    def main(self):
        if sys.platform == 'win32':
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleCP(65001)
                kernel32.SetConsoleOutputCP(65001)
            except:
                print('无法设置控制台编码为UTF-8')
        paths, args = UnclassifiedFunctions.process_args()
        UnclassifiedFunctions.run_classifier(paths, args)

    def decorator(self, func):
    
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
    
            def handler(self, signum, frame):
                raise TimeoutError(f'函数执行超时 ({seconds}秒)')
            if sys.platform != 'win32':
                original_handler = signal.signal(signal.SIGALRM, handler)
                signal.alarm(seconds)
            else:
                timer = threading.Timer(seconds, lambda: threading._shutdown())
                timer.start()
            try:
                result = func(*args, **kwargs)
            finally:
                if sys.platform != 'win32':
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, original_handler)
                else:
                    timer.cancel()
            return result
        return wrapper

    def process_file_keywords(self, args):
        file_path, keywords = args
        if file_path in processed_files:
            return None
        current_group = [file_path]
        group_keywords = set(keywords)
        current_to_process = set()
        for other_path, other_keywords in file_keywords.items():
            if other_path == file_path or other_path in processed_files:
                continue
            common_keywords = set(keywords) & set(other_keywords)
            if common_keywords and any((len(k) > 1 for k in common_keywords)):
                current_group.append(other_path)
                current_to_process.add(other_path)
                group_keywords &= set(other_keywords)
        if len(current_group) > 1:
            series_name = max(group_keywords, key=len) if group_keywords else max(keywords, key=len)
            return (series_name, current_group, current_to_process)
        return None

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
    
        def handler(self, signum, frame):
            raise TimeoutError(f'函数执行超时 ({seconds}秒)')
        if sys.platform != 'win32':
            original_handler = signal.signal(signal.SIGALRM, handler)
            signal.alarm(seconds)
        else:
            timer = threading.Timer(seconds, lambda: threading._shutdown())
            timer.start()
        try:
            result = func(*args, **kwargs)
        finally:
            if sys.platform != 'win32':
                signal.alarm(0)
                signal.signal(signal.SIGALRM, original_handler)
            else:
                timer.cancel()
        return result

    def handler(self, signum, frame):
        raise TimeoutError(f'函数执行超时 ({seconds}秒)')

    def calculate_similarity(self, str1, str2, handler=None):
        """计算两个字符串的相似度"""
        str1 = UnclassifiedFunctions.normalize_chinese(str1)
        str2 = UnclassifiedFunctions.normalize_chinese(str2)
        ratio = fuzz.ratio(str1.lower(), str2.lower())
        partial = fuzz.partial_ratio(str1.lower(), str2.lower())
        token = fuzz.token_sort_ratio(str1.lower(), str2.lower())
        max_similarity = max(ratio, partial, token)
        if max_similarity >= SIMILARITY_CONFIG['THRESHOLD']:
            logger.info(f'[#update] 🔍 相似度: {max_similarity}%')
        return max_similarity

    def is_in_series_folder(self, file_path):
        """检查文件是否已经在系列文件夹内"""
        parent_dir = os.path.dirname(file_path)
        parent_name = os.path.basename(parent_dir)
        for prefix in SERIES_PREFIXES:
            if parent_name.startswith(prefix):
                series_name = parent_name[len(prefix):]
                parent_key = UnclassifiedFunctions.get_series_key(series_name)
                file_key = UnclassifiedFunctions.get_series_key(os.path.basename(file_path))
                return parent_key == file_key
        parent_key = UnclassifiedFunctions.get_series_key(parent_name)
        file_key = UnclassifiedFunctions.get_series_key(os.path.basename(file_path))
        if parent_key and parent_key in file_key:
            return True
        return False

    def is_essentially_same_file(self, file1, file2):
        """检查两个文件是否本质上是同一个文件（只是标签不同）"""
        name1 = os.path.splitext(os.path.basename(file1))[0]
        name2 = os.path.splitext(os.path.basename(file2))[0]
        if name1 == name2:
            return True
        base1 = re.sub('\\[[^\\]]*\\]|\\([^)]*\\)', '', name1)
        base2 = re.sub('\\[[^\\]]*\\]|\\([^)]*\\)', '', name2)
        base1 = re.sub('[\\s]+', '', base1).lower()
        base2 = re.sub('[\\s]+', '', base2).lower()
        base1 = UnclassifiedFunctions.normalize_chinese(base1)
        base2 = UnclassifiedFunctions.normalize_chinese(base2)
        return base1 == base2

    def extract_keywords(self, filename):
        """从文件名中提取关键词"""
        name = UnclassifiedFunctions.get_base_filename(filename)
        separators = '[\\s]+'
        keywords = []
        name = re.sub('\\[[^\\]]*\\]|\\([^)]*\\)', ' ', name)
        parts = [p.strip() for p in re.split(separators, name) if p.strip()]
        for part in parts:
            if len(part) > 1:
                keywords.append(part)
        return keywords

    def process_args(self):
        """处理命令行参数"""
        parser = argparse.ArgumentParser(description='漫画压缩包分类工具')
        parser.add_argument('paths', nargs='*', help='要处理的路径列表')
        parser.add_argument('-c', '--clipboard', action='store_true', help='从剪贴板读取路径')
        parser.add_argument('-f', '--features', type=str, default='', help='启用的功能（1-4，用逗号分隔）：1=分类，2=系列提取，3=删除空文件夹，4=序号修复。默认全部启用')
        parser.add_argument('--similarity', type=float, default=80, help='设置基本相似度阈值(0-100)，默认80')
        parser.add_argument('--ratio', type=float, default=75, help='设置完全匹配阈值(0-100)，默认75')
        parser.add_argument('--partial', type=float, default=85, help='设置部分匹配阈值(0-100)，默认85')
        parser.add_argument('--token', type=float, default=80, help='设置标记匹配阈值(0-100)，默认80')
        parser.add_argument('--length-diff', type=float, default=0.3, help='设置长度差异最大值(0-1)，默认0.3')
        parser.add_argument('--wait', action='store_true', help='处理完每个路径后等待用户确认')
        if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ['-c', '--clipboard']):
            presets = {'默认配置': {'features': '1,2,3,4', 'similarity': '80', 'ratio': '75', 'partial': '85', 'token': '80', 'length_diff': '0.3', 'clipboard': True, 'wait': False}, '仅分类': {'features': '1', 'similarity': '80', 'ratio': '75', 'partial': '85', 'token': '80', 'length_diff': '0.3', 'clipboard': True, 'wait': False}, '仅系列提取': {'features': '2', 'similarity': '80', 'ratio': '75', 'partial': '85', 'token': '80', 'length_diff': '0.3', 'clipboard': True, 'wait': False}, '分类+系列': {'features': '1,2', 'similarity': '80', 'ratio': '75', 'partial': '85', 'token': '80', 'length_diff': '0.3', 'clipboard': True, 'wait': False}}
            checkbox_options = [('从剪贴板读取', 'clipboard', '-c', True), ('分类功能', 'feature1', '-f 1'), ('系列提取', 'feature2', '-f 2'), ('删除空文件夹', 'feature3', '-f 3'), ('序号修复', 'feature4', '-f 4'), ('等待确认', 'wait', '--wait', False)]
            input_options = [('基本相似度阈值', 'similarity', '--similarity', '80', '0-100'), ('完全匹配阈值', 'ratio', '--ratio', '75', '0-100'), ('部分匹配阈值', 'partial', '--partial', '85', '0-100'), ('标记匹配阈值', 'token', '--token', '80', '0-100'), ('长度差异最大值', 'length_diff', '--length-diff', '0.3', '0-1')]
            app = create_config_app(program=__file__, checkbox_options=checkbox_options, input_options=input_options, title='漫画压缩包分类工具配置', preset_configs=presets)
            app.run()
            return (None, None)
        args = parser.parse_args()
        if args.clipboard:
            try:
                import pyperclip
                clipboard_content = pyperclip.paste().strip()
                if clipboard_content:
                    args.paths.extend([p.strip() for p in clipboard_content.replace('\r\n', '\n').split('\n') if p.strip()])
                    print('从剪贴板读取到以下路径：')
                    for path in args.paths:
                        print(path)
            except ImportError:
                print('未安装 pyperclip 模块，无法从剪贴板读取路径')
        return (args.paths, args)

    def run_classifier(self, paths, args):
        """运行分类器主逻辑"""
        if not paths or not args:
            return
        similarity_config = {'THRESHOLD': args.similarity, 'RATIO_THRESHOLD': args.ratio, 'PARTIAL_THRESHOLD': args.partial, 'TOKEN_THRESHOLD': args.token, 'LENGTH_DIFF_MAX': args.length_diff}
        SIMILARITY_CONFIG.update(similarity_config)
        enabled_features = set()
        if args.features:
            try:
                enabled_features = {int(f.strip()) for f in args.features.split(',') if f.strip()}
                for f in enabled_features.copy():
                    if f not in {1, 2, 3, 4}:
                        print(f'无效的功能编号: {f}')
                        enabled_features.remove(f)
            except ValueError:
                print('无效的功能编号格式，将启用所有功能')
                enabled_features = {1, 2, 3, 4}
        else:
            enabled_features = {1, 2, 3, 4}
        UnclassifiedFunctions.process_paths(paths, enabled_features=enabled_features, wait_for_confirm=args.wait)

    def process_paths(self, paths, enabled_features=None, similarity_config=None, wait_for_confirm=False):
        """处理输入的路径列表"""
        UnclassifiedFunctions.init_TextualLogger()
        if similarity_config:
            SIMILARITY_CONFIG.update(similarity_config)
        valid_paths = []
        for path in paths:
            path = path.strip().strip('"').strip("'")
            if path:
                try:
                    if sys.platform == 'win32':
                        if UnclassifiedFunctions.win32_path_exists(path):
                            valid_paths.append(path)
                        else:
                            print(f'❌ 路径不存在或无法访问: {path}')
                    elif os.path.exists(path):
                        valid_paths.append(path)
                    else:
                        print(f'❌ 路径不存在: {path}')
                except Exception as e:
                    print(f'❌ 处理路径时出错: {path}, 错误: {str(e)}')
        if not valid_paths:
            print('❌ 没有有效的路径')
            return
        total_paths = len(valid_paths)
        print(f"\n🚀 开始{('处理' if wait_for_confirm else '批量处理')} {total_paths} 个路径...")
        if not wait_for_confirm:
            print('路径列表:')
            for path in valid_paths:
                print(f'  - {path}')
            print()
        UnclassifiedFunctions.init_TextualLogger()
        for i, path in enumerate(valid_paths, 1):
            try:
                if wait_for_confirm:
                    logger.info(f'[#current_progress] 📍 处理第 {i}/{total_paths} 个路径: {path}')
                else:
                    logger.info(f'[#current_progress] 处理: {os.path.basename(path)}')
                if sys.platform == 'win32':
                    if UnclassifiedFunctions.win32_path_exists(path):
                        if os.path.isdir(path):
                            UnclassifiedFunctions.process_directory(path, enabled_features=enabled_features)
                        elif os.path.isfile(path) and UnclassifiedFunctions.is_archive(path):
                            if 1 in enabled_features:
                                if wait_for_confirm:
                                    logger.info(f'[#current_progress] 📦 处理单个文件: {path}')
                                UnclassifiedFunctions.process_single_file(path)
                                if wait_for_confirm:
                                    logger.info('[#update] ✨ 文件处理完成')
                elif os.path.isdir(path):
                    UnclassifiedFunctions.process_directory(path, enabled_features=enabled_features)
                elif os.path.isfile(path) and UnclassifiedFunctions.is_archive(path):
                    if 1 in enabled_features:
                        if wait_for_confirm:
                            logger.info(f'[#current_progress] 📦 处理单个文件: {path}')
                        UnclassifiedFunctions.process_single_file(path)
                        if wait_for_confirm:
                            logger.info('[#update] ✨ 文件处理完成')
                if wait_for_confirm and i < total_paths:
                    logger.info(f'[#current_progress] ⏸️ 已处理完第 {i}/{total_paths} 个路径')
                    input('按回车键继续处理下一个路径...')
            except Exception as e:
                logger.error(f'[#update] ❌ 处理路径时出错: {path}, 错误: {str(e)}')
                if wait_for_confirm and i < total_paths:
                    logger.warning('[#update] ⚠️ 处理出错，是否继续？')
                    input('按回车键继续处理下一个路径，按 Ctrl+C 终止程序...')
        if wait_for_confirm:
            logger.info('[#update] ✅ 所有路径处理完成！')
        else:
            logger.info(f'[#update] ✅ 批量处理完成！共处理 {total_paths} 个路径')

    def win32_path_exists(self, path):
        try:
            win32api.GetFileAttributes(path)
            return True
        except:
            print('未安装win32api模块，某些路径可能无法正确处理')
            win32_path_exists = os.path.exists

    def process_directory(self, directory_path, progress_task=None, enabled_features=None, handler=None):
        """处理目录下的压缩包"""
        try:
            if enabled_features is None:
                enabled_features = {1, 2, 3, 4}
            abs_dir_path = UnclassifiedFunctions.validate_directory(directory_path)
            if not abs_dir_path:
                return []
            UnclassifiedFunctions.init_TextualLogger()
            try:
                logger.info(f'[#process] 📂 开始处理目录: {abs_dir_path}')
                if 2 in enabled_features:
                    logger.info('[#process] 🔄 检查并更新旧的系列文件夹名称...')
                    UnclassifiedFunctions.update_all_series_folders(abs_dir_path)
                if 1 in enabled_features:
                    UnclassifiedFunctions.create_category_folders(abs_dir_path)
                category_folders = set(CATEGORY_RULES.keys())
                found_archives = False
                if 2 in enabled_features:
                    logger.info('[#process] 🔍 开始查找可提取系列的压缩包...')
                    archives = UnclassifiedFunctions.collect_archives_for_series(abs_dir_path, category_folders)
                    if archives:
                        found_archives = True
                        total_archives = len(archives)
                        logger.info(f"[#update] ✨ 在目录 '{abs_dir_path}' 及其子文件夹下找到 {total_archives} 个有效压缩包")
                        UnclassifiedFunctions.create_series_folders(abs_dir_path, archives)
                        logger.info('[#current_progress] 系列提取完成')
                    else:
                        logger.info('[#process] 没有找到可提取系列的压缩包')
                if 1 in enabled_features:
                    logger.info('[#process] 🔍 开始查找需要分类的压缩包...')
                    archives = UnclassifiedFunctions.collect_archives_for_category(abs_dir_path, category_folders)
                    if archives:
                        found_archives = True
                        total_archives = len(archives)
                        logger.info(f"[#update] ✨ 在目录 '{abs_dir_path}' 下找到 {total_archives} 个有效压缩包")
                        for i, archive in enumerate(archives, 1):
                            percentage = i / total_archives * 100
                            progress_text = f'正在分类压缩包... {percentage:.1f}% ({i}/{total_archives})'
                            logger.info(f'[#current_progress] {progress_text}')
                            logger.info(f'[#process] 处理: {os.path.basename(archive)}')
                            UnclassifiedFunctions.process_single_file(archive)
                    else:
                        logger.info('[#process] 没有找到需要分类的压缩包')
                if 3 in enabled_features or 4 in enabled_features:
                    logger.info('[#post_process] 🔧 开始运行后续处理...')
                    UnclassifiedFunctions.run_post_processing(abs_dir_path, enabled_features)
                if not found_archives:
                    logger.info(f"[#process] 在目录 '{abs_dir_path}' 下没有找到需要处理的压缩包")
                logger.info(f'[#process] ✨ 目录处理完成: {abs_dir_path}')
            except Exception as e:
                logger.error(f'[#update] ❌ 处理目录时出错 {directory_path}: {str(e)}')
                logger.error(f'[#process] ❌ 处理出错: {os.path.basename(directory_path)}')
            return []
        except Exception as e:
            logger.error(f'[#update] ❌ 处理目录时出错 {directory_path}: {str(e)}')
            logger.error(f'[#process] ❌ 处理出错: {os.path.basename(directory_path)}')
            return []

    def validate_directory(self, directory_path, handler=None):
        """验证目录是否有效且不在黑名单中"""
        abs_dir_path = os.path.abspath(directory_path)
        if not os.path.isdir(abs_dir_path):
            logger.error(f'[#update] ❌ 不是有效的目录路径: {abs_dir_path}')
            return None
        if UnclassifiedFunctions.is_path_blacklisted(abs_dir_path):
            logger.warning(f'[#update] ⚠️ 目录在黑名单中，跳过处理: {abs_dir_path}')
            return None
        return abs_dir_path

    def init_TextualLogger(self):
        """初始化TextualLogger"""
        TextualLoggerManager.set_layout(TEXTUAL_LAYOUT, config_info['log_file'])

    def update_all_series_folders(self, directory_path, handler=None):
        """更新目录下所有的系列文件夹名称"""
        try:
            updated_count = 0
            for root, dirs, _ in os.walk(directory_path):
                for dir_name in dirs:
                    if dir_name.startswith('[#s]'):
                        full_path = os.path.join(root, dir_name)
                        if UnclassifiedFunctions.update_series_folder_name(full_path):
                            updated_count += 1
            if updated_count > 0:
                logger.info(f'[#update] ✨ 更新了 {updated_count} 个系列文件夹名称')
            return updated_count
        except Exception as e:
            logger.error(f'[#update] ❌ 更新系列文件夹失败: {str(e)}')
            return 0

    def collect_archives_for_series(self, directory_path, category_folders, handler=None):
        """收集用于系列提取的压缩包"""
        base_level = len(Path(directory_path).parts)
        archives = []
        archives_to_check = []
        for root, _, files in os.walk(directory_path):
            current_level = len(Path(root).parts)
            if current_level - base_level > 1:
                continue
            if UnclassifiedFunctions.is_path_blacklisted(root):
                logger.warning(f'[#update] ⚠️ 目录在黑名单中，跳过: {root}')
                continue
            current_dir = os.path.basename(root)
            if current_dir.startswith('[#s]') or current_dir == '损坏压缩包':
                continue
            for file in files:
                if UnclassifiedFunctions.is_archive(file):
                    file_path = os.path.join(root, file)
                    if UnclassifiedFunctions.is_series_blacklisted(file):
                        logger.warning(f'[#update] ⚠️ 文件在系列提取黑名单中，跳过: {file}')
                        continue
                    if UnclassifiedFunctions.is_path_blacklisted(file):
                        logger.warning(f'[#update] ⚠️ 文件在黑名单中，跳过: {file}')
                        continue
                    archives_to_check.append(file_path)
        if archives_to_check:
            logger.info(f'[#update] 🔍 正在检查 {len(archives_to_check)} 个压缩包的完整性...')
            with ThreadPoolExecutor(max_workers=16) as executor:
                futures = {executor.submit(is_archive_corrupted, path): path for path in archives_to_check}
                for i, future in enumerate(futures, 1):
                    path = futures[future]
                    percentage = i / len(archives_to_check) * 100
                    if handler:
                        percentage = i / len(archives_to_check) * 100
                        handler.update_panel('current_task', f'检测压缩包完整性... ({i}/{len(archives_to_check)}) {percentage:.1f}%')
                    try:
                        is_corrupted = future.result()
                        if is_corrupted:
                            if handler:
                                handler.update_panel('update_log', f'⚠️ 压缩包已损坏: {os.path.basename(path)}')
                            UnclassifiedFunctions.move_corrupted_archive(path, directory_path, handler)
                        else:
                            archives.append(path)
                    except TimeoutError:
                        if handler:
                            handler.update_panel('update_log', f'⚠️ 压缩包处理超时: {os.path.basename(path)}')
                        UnclassifiedFunctions.move_corrupted_archive(path, directory_path, handler)
                    except Exception as e:
                        if handler:
                            handler.update_panel('update_log', f'❌ 检查压缩包时出错: {os.path.basename(path)}')
                        UnclassifiedFunctions.move_corrupted_archive(path, directory_path, handler)
        return archives

    def collect_archives_for_category(self, directory_path, category_folders, handler=None):
        """收集用于分类的压缩包"""
        archives = []
        archives_to_check = []
        with os.scandir(directory_path) as entries:
            for entry in entries:
                if entry.is_file() and UnclassifiedFunctions.is_archive(entry.name):
                    parent_dir = os.path.basename(os.path.dirname(entry.path))
                    if parent_dir == '损坏压缩包' or parent_dir in category_folders:
                        continue
                    archives_to_check.append(entry.path)
        if archives_to_check:
            logger.info(f'[#update] 🔍 正在检查 {len(archives_to_check)} 个压缩包的完整性...')
            with ThreadPoolExecutor(max_workers=16) as executor:
                futures = {executor.submit(is_archive_corrupted, path): path for path in archives_to_check}
                for i, future in enumerate(futures, 1):
                    path = futures[future]
                    percentage = i / len(archives_to_check) * 100
                    logger.info(f'[#current_progress] 检测压缩包完整性... ({i}/{len(archives_to_check)}) {percentage:.1f}%')
                    try:
                        is_corrupted = future.result()
                        if not is_corrupted:
                            archives.append(path)
                        else:
                            logger.warning(f'[#update] ⚠️ 压缩包已损坏，跳过: {os.path.basename(path)}')
                    except TimeoutError:
                        logger.warning(f'[#update] ⚠️ 压缩包处理超时，跳过: {os.path.basename(path)}')
                    except Exception as e:
                        logger.error(f'[#update] ❌ 检查压缩包时出错: {os.path.basename(path)}')
        return archives

    def run_post_processing(self, directory_path, enabled_features, handler=None):
        """运行后续处理脚本（删除空文件夹和序号修复）"""
        if 3 in enabled_features:
            try:
                handler.update_panel('post_process', '🗑️ 正在删除空文件夹...')
                result = subprocess.run(f'python "D:\\1VSCODE\\1ehv\\archive\\013-删除空文件夹释放单独文件夹.py" "{directory_path}" -r', shell=True, capture_output=True, text=True, encoding='utf-8')
                if result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, result.args)
                handler.update_panel('post_process', '✅ 空文件夹处理完成')
            except subprocess.CalledProcessError as e:
                if handler:
                    handler.update_panel('update_log', f'❌ 运行删除空文件夹脚本失败: {str(e)}')
                    handler.update_panel('post_process', '❌ 空文件夹处理失败')
        if 4 in enabled_features:
            try:
                handler.update_panel('post_process', '🔧 正在修复序号...')
                result = subprocess.run(f'python "D:\\1VSCODE\\1ehv\\other\\012-文件夹序号修复工具.py" "{directory_path}"', shell=True, capture_output=True, text=True, encoding='utf-8')
                if result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, result.args)
                handler.update_panel('post_process', '✅ 序号修复完成')
            except subprocess.CalledProcessError as e:
                if handler:
                    handler.update_panel('update_log', f'❌ 运行序号修复脚本失败: {str(e)}')
                    handler.update_panel('post_process', '❌ 序号修复失败')

    def create_series_folders(self, directory_path, archives, handler=None):
        """为同一系列的文件创建文件夹"""
        dir_groups = defaultdict(list)
        archives = [f for f in archives if os.path.isfile(f) and UnclassifiedFunctions.is_archive(f)]
        for archive in archives:
            dir_path = os.path.dirname(archive)
            parent_name = os.path.basename(dir_path)
            is_series_dir = any((parent_name.startswith(prefix) for prefix in SERIES_PREFIXES))
            if is_series_dir:
                continue
            dir_groups[dir_path].append(archive)
        for dir_path, dir_archives in dir_groups.items():
            if len(dir_archives) <= 1:
                continue
            logger.info(f'[#update] 找到 {len(dir_archives)} 个压缩包')
            series_groups = UnclassifiedFunctions.find_series_groups(dir_archives)
            if series_groups:
                logger.info(f'[#update] 📚 找到 {len(series_groups)} 个系列')
                total_files = len(dir_archives)
                for series_name, files in series_groups.items():
                    if series_name == '其他':
                        continue
                    if len(files) == total_files:
                        logger.warning(f'[#update] ⚠️ 所有文件都属于同一个系列，跳过创建子文件夹')
                        return
                series_folders = {}
                for series_name, files in series_groups.items():
                    if series_name == '其他' or len(files) <= 1:
                        if series_name == '其他':
                            logger.warning(f'[#update] ⚠️ {len(files)} 个文件未能匹配到系列')
                        else:
                            logger.warning(f"[#update] ⚠️ 系列 '{series_name}' 只有一个文件，跳过创建文件夹")
                        continue
                    series_folder = os.path.join(dir_path, f'[#s]{series_name.strip()}')
                    if not os.path.exists(series_folder):
                        os.makedirs(series_folder)
                        logger.info(f'[#update] 📁 创建系列文件夹: [#s]{series_name}')
                    series_folders[series_name] = series_folder
                for series_name, folder_path in series_folders.items():
                    files = series_groups[series_name]
                    logger.info(f"[#update] 📦 开始移动系列 '{series_name}' 的文件...")
                    for file_path in files:
                        target_path = os.path.join(folder_path, os.path.basename(file_path))
                        if not os.path.exists(target_path):
                            shutil.move(file_path, target_path)
                            logger.info(f'[#update]   └─ 移动: {os.path.basename(file_path)}')
                        else:
                            logger.warning(f"[#update] ⚠️ 文件已存在于系列 '{series_name}': {os.path.basename(file_path)}")
                logger.info('[#current_progress] 系列提取完成')
            logger.info(f'[#process] ✨ 目录处理完成: {dir_path}')

    def process_single_file(self, abs_path, handler=None):
        """处理单个文件"""
        try:
            if not os.path.exists(abs_path):
                logger.error(f'[#update] ❌ 路径不存在: {abs_path}')
                return
            logger.info(f'[#current_progress] 处理文件: {os.path.basename(abs_path)}')
            logger.info(f'[#process] 分析: {os.path.basename(abs_path)}')
            UnclassifiedFunctions.create_category_folders(os.path.dirname(abs_path))
            category = UnclassifiedFunctions.get_category(abs_path)
            if category == '损坏':
                logger.warning(f'[#update] ⚠️ 压缩包已损坏: {os.path.basename(abs_path)}')
                logger.warning(f'[#process] ❌ 损坏: {os.path.basename(abs_path)}')
                UnclassifiedFunctions.move_corrupted_archive(abs_path, os.path.dirname(abs_path))
                return
            UnclassifiedFunctions.move_file_to_category(abs_path, category)
            logger.info(f'[#process] ✅ 完成: {os.path.basename(abs_path)} -> {category}')
        except Exception as e:
            logger.error(f'[#update] ❌ 处理文件时出错 {abs_path}: {str(e)}')
            logger.error(f'[#process] ❌ 错误: {os.path.basename(abs_path)}')

    def update_series_folder_name(self, old_path, handler=None):
        """更新系列文件夹名称为最新标准"""
        try:
            dir_name = os.path.basename(old_path)
            is_series = False
            prefix_used = None
            for prefix in SERIES_PREFIXES:
                if dir_name.startswith(prefix):
                    is_series = True
                    prefix_used = prefix
                    break
            if not is_series:
                return False
            old_series_name = dir_name[len(prefix_used):]
            new_series_name = UnclassifiedFunctions.get_series_key(old_series_name)
            if not new_series_name or new_series_name == old_series_name:
                return False
            new_path = os.path.join(os.path.dirname(old_path), f'[#s]{new_series_name}')
            if os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(old_path):
                if handler:
                    handler.update_panel('update_log', f'⚠️ 目标路径已存在: {new_path}')
                return False
            os.rename(old_path, new_path)
            if handler:
                handler.update_panel('update_log', f'📁 更新系列文件夹名称: {dir_name} -> [#s]{new_series_name}')
            return True
        except Exception as e:
            if handler:
                handler.update_panel('update_log', f'❌ 更新系列文件夹名称失败 {old_path}: {str(e)}')
            return False

    def is_path_blacklisted(self, path):
        """检查路径是否在黑名单中"""
        path_lower = path.lower()
        return any((keyword.lower() in path_lower for keyword in PATH_BLACKLIST))

    def is_series_blacklisted(self, filename):
        """检查文件名是否在系列提取黑名单中"""
        for pattern in SERIES_BLACKLIST_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                return True
        return False

    def create_category_folders(self, base_path, handler=None):
        """在指定路径创建分类文件夹"""
        for category in CATEGORY_RULES.keys():
            category_path = os.path.join(base_path, category)
            if not os.path.exists(category_path):
                os.makedirs(category_path)
                logger.info(f'[#update] 📁 创建分类文件夹: {category}')
        corrupted_path = os.path.join(base_path, '损坏压缩包')
        if not os.path.exists(corrupted_path):
            os.makedirs(corrupted_path)
            logger.info(f'[#update] 📁 创建损坏压缩包文件夹')

    def get_category(self, path, handler=None):
        """根据路径名判断类别，使用正则表达式进行匹配"""
        filename = os.path.basename(path)
        if not UnclassifiedFunctions.is_archive(path):
            return '未分类'
        if UnclassifiedFunctions.is_archive_corrupted(path):
            return '损坏'
        for pattern in CATEGORY_RULES['4. 画集']['patterns']:
            if re.search(pattern, filename, re.IGNORECASE):
                return '4. 画集'
        image_count = UnclassifiedFunctions.count_images_in_archive(path)
        if image_count == -1:
            return '损坏'
        logger.info(f"[#update] 压缩包 '{filename}' 中包含 {image_count} 张图片")
        if image_count >= 100:
            for category, rules in CATEGORY_RULES.items():
                if category == '4. 画集':
                    continue
                excluded = False
                for exclude_pattern in rules['exclude_patterns']:
                    if re.search(exclude_pattern, filename, re.IGNORECASE):
                        excluded = True
                        break
                if excluded:
                    continue
                for pattern in rules['patterns']:
                    if re.search(pattern, filename, re.IGNORECASE):
                        return category
            return '3. 单行本'
        for category, rules in CATEGORY_RULES.items():
            if category == '4. 画集':
                continue
            excluded = False
            for exclude_pattern in rules['exclude_patterns']:
                if re.search(exclude_pattern, filename, re.IGNORECASE):
                    excluded = True
                    break
            if excluded:
                continue
            for pattern in rules['patterns']:
                if re.search(pattern, filename, re.IGNORECASE):
                    return category
        return '未分类'

    def move_file_to_category(self, file_path, category, handler=None):
        """将文件移动到对应的分类文件夹"""
        if category == '未分类':
            logger.info(f"[#update] 文件 '{file_path}' 未能匹配任何分类规则，保持原位置")
            return
        target_dir = os.path.join(os.path.dirname(file_path), category)
        target_path = os.path.join(target_dir, os.path.basename(file_path))
        if not os.path.exists(target_path):
            shutil.move(file_path, target_path)
            logger.info(f'[#update] 已移动到: {target_path}')
        else:
            logger.info(f'[#update] 目标路径已存在文件: {target_path}')

    def move_corrupted_archive(self, file_path, base_path, handler=None):
        """移动损坏的压缩包到损坏压缩包文件夹，保持原有目录结构"""
        try:
            rel_path = os.path.relpath(os.path.dirname(file_path), base_path)
            corrupted_base = os.path.join(base_path, '损坏压缩包')
            target_dir = os.path.join(corrupted_base, rel_path)
            os.makedirs(target_dir, exist_ok=True)
            target_path = os.path.join(target_dir, os.path.basename(file_path))
            if os.path.exists(target_path):
                base, ext = os.path.splitext(target_path)
                counter = 1
                while os.path.exists(f'{base}_{counter}{ext}'):
                    counter += 1
                target_path = f'{base}_{counter}{ext}'
            shutil.move(file_path, target_path)
            logger.info(f'[#update] 📦 已移动损坏压缩包: {os.path.basename(file_path)} -> 损坏压缩包/{rel_path}')
        except Exception as e:
            logger.error(f'[#update] ❌ 移动损坏压缩包失败 {file_path}: {str(e)}')

    def get_series_key(self, filename, handler=None):
        """获取用于系列比较的键值"""
        logger.info(f'[#process] 处理文件: {filename}')
        test_group = [filename, filename]
        series_groups = UnclassifiedFunctions.find_series_groups(test_group)
        if series_groups:
            series_name = next(iter(series_groups.keys()))
            logger.info(f'[#process] 找到系列名称: {series_name}')
            return series_name
        name = UnclassifiedFunctions.preprocess_filename(filename)
        name = UnclassifiedFunctions.normalize_chinese(name)
        logger.info(f'[#process] 使用预处理结果: {name}')
        if handler:
            handler.update_panel('series_extract', f'使用预处理结果: {name}')
        return name.strip()

    @UnclassifiedFunctions.timeout(60)
    def count_images_in_archive(self, archive_path, handler=None):
        """使用7z的列表模式统计压缩包中的图片数量"""
        try:
            if UnclassifiedFunctions.is_archive_corrupted(archive_path):
                logger.warning(f'[#update] ⚠️ 压缩包已损坏，跳过处理: {archive_path}')
                return -1
            output = UnclassifiedFunctions.run_7z_command('l', archive_path, additional_args=['-slt'])
            if not output:
                logger.error(f'[#update] ❌ 无法获取压缩包内容列表: {archive_path}')
                return 0
            image_count = sum((1 for ext in IMAGE_EXTENSIONS if ext in output.lower()))
            logger.info(f"[#update] 📦 压缩包 '{os.path.basename(archive_path)}' 中包含 {image_count} 张图片")
            return image_count
        except TimeoutError as e:
            logger.error(f'[#update] ❌ 处理压缩包超时 {archive_path}: {str(e)}')
            return -1
        except Exception as e:
            logger.error(f'[#update] ❌ 处理压缩包时出错 {archive_path}: {str(e)}')
            return -1

    def is_archive(self, path):
        """检查文件是否为支持的压缩包格式"""
        return Path(path).suffix.lower() in {'.zip', '.rar', '.7z', '.cbz', '.cbr'}

    def find_series_groups(self, filenames, handler=None):
        """查找属于同一系列的文件组，使用三阶段匹配策略"""
        processed_names = {f: UnclassifiedFunctions.preprocess_filename(f) for f in filenames}
        processed_keywords = {f: UnclassifiedFunctions.get_keywords(processed_names[f]) for f in filenames}
        simplified_names = {f: UnclassifiedFunctions.normalize_chinese(n) for f, n in processed_names.items()}
        simplified_keywords = {f: [UnclassifiedFunctions.normalize_chinese(k) for k in kws] for f, kws in processed_keywords.items()}
        series_groups = defaultdict(list)
        remaining_files = set(filenames)
        matched_files = set()
        logger.info('[#process] 🔍 预处理阶段：检查已标记的系列')
        for file_path in list(remaining_files):
            if file_path in matched_files:
                continue
            file_name = os.path.basename(file_path)
            for prefix in SERIES_PREFIXES:
                if file_name.startswith(prefix):
                    series_name = file_name[len(prefix):]
                    series_name = re.sub('\\[.*?\\]|\\(.*?\\)', '', series_name)
                    series_name = series_name.strip()
                    if series_name:
                        series_groups[series_name].append(file_path)
                        matched_files.add(file_path)
                        remaining_files.remove(file_path)
                        logger.info(f"[#process] ✨ 预处理阶段：文件 '{os.path.basename(file_path)}' 已标记为系列 '{series_name}'")
                    break
        logger.info('[#process] 🔍 第一阶段：风格匹配（关键词匹配）')
        while remaining_files:
            best_length = 0
            best_common = None
            best_pair = None
            best_series_name = None
            for file1 in remaining_files:
                if file1 in matched_files:
                    continue
                keywords1 = simplified_keywords[file1]
                base_name1 = UnclassifiedFunctions.get_base_filename(os.path.basename(file1))
                for file2 in remaining_files - {file1}:
                    if file2 in matched_files:
                        continue
                    base_name2 = UnclassifiedFunctions.get_base_filename(os.path.basename(file2))
                    if base_name1 == base_name2:
                        logger.info(f"[#process] ✨ 第一阶段：文件 '{os.path.basename(file1)}' 和 '{os.path.basename(file2)}' 基础名完全相同，跳过")
                        continue
                    keywords2 = simplified_keywords[file2]
                    common = UnclassifiedFunctions.find_longest_common_keywords(keywords1, keywords2)
                    if common:
                        original_kw1 = processed_keywords[file1]
                        original_common = original_kw1[keywords1.index(common[0]):keywords1.index(common[-1]) + 1]
                        series_name = UnclassifiedFunctions.validate_series_name(' '.join(original_common))
                        if series_name and len(common) > best_length:
                            best_length = len(common)
                            best_common = common
                            best_pair = (file1, file2)
                            best_series_name = series_name
            if best_pair and best_series_name:
                matched_files_this_round = set(best_pair)
                base_name1 = UnclassifiedFunctions.get_base_filename(os.path.basename(best_pair[0]))
                for other_file in remaining_files - matched_files_this_round - matched_files:
                    other_base_name = UnclassifiedFunctions.get_base_filename(os.path.basename(other_file))
                    if base_name1 == other_base_name:
                        continue
                    other_keywords = simplified_keywords[other_file]
                    common = UnclassifiedFunctions.find_longest_common_keywords(simplified_keywords[best_pair[0]], other_keywords)
                    if common == best_common:
                        matched_files_this_round.add(other_file)
                series_groups[best_series_name].extend(matched_files_this_round)
                remaining_files -= matched_files_this_round
                matched_files.update(matched_files_this_round)
                logger.info(f"[#process] ✨ 第一阶段：通过关键词匹配找到系列 '{best_series_name}'")
                for file_path in matched_files_this_round:
                    logger.info(f"[#process] ✨ 第一阶段：通过关键词匹配找到系列 '{best_series_name}'")
                    for file_path in matched_files_this_round:
                        logger.info(f"[#process] ✨ 第一阶段：通过关键词匹配找到系列 '{best_series_name}'")
            else:
                break
        if remaining_files:
            if handler:
                handler.update_panel('series_extract', '🔍 第二阶段：完全基础名匹配')
            existing_series = list(series_groups.keys())
            dir_path = os.path.dirname(list(remaining_files)[0])
            try:
                for folder_name in os.listdir(dir_path):
                    if os.path.isdir(os.path.join(dir_path, folder_name)):
                        for prefix in SERIES_PREFIXES:
                            if folder_name.startswith(prefix):
                                series_name = folder_name[len(prefix):]
                                if series_name not in existing_series:
                                    existing_series.append(series_name)
                                    if handler:
                                        handler.update_panel('series_extract', f"📁 第二阶段：从目录中找到已有系列 '{series_name}'")
                                break
            except Exception:
                pass
            matched_files_by_series = defaultdict(list)
            for file in list(remaining_files):
                if file in matched_files:
                    continue
                base_name = simplified_names[file]
                base_name_no_space = re.sub('\\s+', '', base_name)
                for series_name in existing_series:
                    series_base = UnclassifiedFunctions.normalize_chinese(series_name)
                    series_base_no_space = re.sub('\\s+', '', series_base)
                    if series_base_no_space in base_name_no_space:
                        base_name_current = UnclassifiedFunctions.get_base_filename(os.path.basename(file))
                        has_same_base = False
                        for existing_file in matched_files_by_series[series_name]:
                            if UnclassifiedFunctions.get_base_filename(os.path.basename(existing_file)) == base_name_current:
                                has_same_base = True
                                break
                        if not has_same_base:
                            matched_files_by_series[series_name].append(file)
                            matched_files.add(file)
                            remaining_files.remove(file)
                            if handler:
                                handler.update_panel('series_extract', f"✨ 第二阶段：文件 '{os.path.basename(file)}' 匹配到已有系列 '{series_name}'（包含系列名）")
                        break
            for series_name, files in matched_files_by_series.items():
                series_groups[series_name].extend(files)
                if handler:
                    handler.update_panel('series_extract', f"✨ 第二阶段：将 {len(files)} 个文件添加到系列 '{series_name}'")
                    for file_path in files:
                        handler.update_panel('series_extract', f'  └─ {os.path.basename(file_path)}')
        if remaining_files:
            if handler:
                handler.update_panel('series_extract', '🔍 第三阶段：最长公共子串匹配')
            while remaining_files:
                best_ratio = 0
                best_pair = None
                best_common = None
                original_form = None
                for file1 in remaining_files:
                    if file1 in matched_files:
                        continue
                    base1 = simplified_names[file1]
                    base1_lower = base1.lower()
                    original1 = processed_names[file1]
                    base_name1 = UnclassifiedFunctions.get_base_filename(os.path.basename(file1))
                    for file2 in remaining_files - {file1}:
                        if file2 in matched_files:
                            continue
                        base_name2 = UnclassifiedFunctions.get_base_filename(os.path.basename(file2))
                        if base_name1 == base_name2:
                            continue
                        base2 = simplified_names[file2]
                        base2_lower = base2.lower()
                        matcher = difflib.SequenceMatcher(None, base1_lower, base2_lower)
                        ratio = matcher.ratio()
                        if ratio > best_ratio and ratio > 0.6:
                            best_ratio = ratio
                            best_pair = (file1, file2)
                            match = matcher.find_longest_match(0, len(base1_lower), 0, len(base2_lower))
                            best_common = base1_lower[match.a:match.a + match.size]
                            original_form = original1[match.a:match.a + match.size]
                if best_pair and best_common and (len(best_common.strip()) > 1):
                    matched_files_this_round = set(best_pair)
                    base_name1 = UnclassifiedFunctions.get_base_filename(os.path.basename(best_pair[0]))
                    for other_file in remaining_files - matched_files_this_round - matched_files:
                        other_base_name = UnclassifiedFunctions.get_base_filename(os.path.basename(other_file))
                        if base_name1 == other_base_name:
                            continue
                        other_base = simplified_names[other_file].lower()
                        if best_common in other_base:
                            matched_files_this_round.add(other_file)
                    series_name = UnclassifiedFunctions.validate_series_name(original_form)
                    if series_name:
                        series_groups[series_name].extend(matched_files_this_round)
                        remaining_files -= matched_files_this_round
                        matched_files.update(matched_files_this_round)
                        if handler:
                            handler.update_panel('series_extract', f"✨ 第三阶段：通过公共子串匹配找到系列 '{series_name}'")
                            handler.update_panel('series_extract', f"  └─ 公共子串：'{best_common}' (相似度: {best_ratio:.2%})")
                            for file_path in matched_files_this_round:
                                handler.update_panel('series_extract', f"  └─ 文件 '{os.path.basename(file_path)}'")
                    else:
                        remaining_files.remove(best_pair[0])
                        matched_files.add(best_pair[0])
                else:
                    break
        if handler and remaining_files:
            handler.update_panel('series_extract', f'⚠️ 还有 {len(remaining_files)} 个文件未能匹配到任何系列')
        return dict(series_groups)

    @UnclassifiedFunctions.timeout(60)
    def is_archive_corrupted(self, archive_path):
        """检查压缩包是否损坏"""
        try:
            cmd = ['7z', 't', archive_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=55)
            return result.returncode != 0
        except subprocess.TimeoutExpired:
            raise TimeoutError(f'检查压缩包完整性超时: {archive_path}')
        except Exception:
            return True

    @UnclassifiedFunctions.timeout(60)
    def run_7z_command(self, command, archive_path, operation='', additional_args=None, handler=None):
        """运行7z命令并返回输出"""
        try:
            cmd = ['7z', command]
            if additional_args:
                cmd.extend(additional_args)
            cmd.append(archive_path)
            result = subprocess.run(cmd, capture_output=True, text=False, timeout=55)
            try:
                output = result.stdout.decode('cp932')
            except UnicodeDecodeError:
                try:
                    output = result.stdout.decode('utf-8')
                except UnicodeDecodeError:
                    output = result.stdout.decode('utf-8', errors='replace')
            return output if output else ''
        except subprocess.TimeoutExpired:
            raise TimeoutError(f'7z命令执行超时: {archive_path}')
        except Exception as e:
            if handler:
                logger.error(f'[#update] ❌ 执行7z命令时出错 {archive_path}: {str(e)}')
            return ''

    def preprocess_filename(self, filename):
        """预处理文件名"""
        name = os.path.basename(filename)
        name = name.rsplit('.', 1)[0]
        for prefix in SERIES_PREFIXES:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
        name = re.sub('\\[.*?\\]', '', name)
        name = re.sub('\\(.*?\\)', '', name)
        name = ' '.join(name.split())
        return name

    def get_keywords(self, name):
        """将文件名分割为关键词列表"""
        return name.strip().split()

    def get_base_filename(self, filename):
        """获取去除所有标签后的基本文件名"""
        name = os.path.splitext(filename)[0]
        name = re.sub('\\[[^\\]]*\\]', '', name)
        name = re.sub('\\([^)]*\\)', '', name)
        name = re.sub('[\\s!！?？_~～]+', '', name)
        name = UnclassifiedFunctions.normalize_chinese(name)
        return name

    def find_longest_common_keywords(self, keywords1, keywords2):
        """找出两个关键词列表中最长的连续公共部分"""
        matcher = difflib.SequenceMatcher(None, keywords1, keywords2)
        match = matcher.find_longest_match(0, len(keywords1), 0, len(keywords2))
        return keywords1[match.a:match.a + match.size]

    def validate_series_name(self, name):
        """验证和清理系列名称
        
        Args:
            name: 原始系列名称
            
        Returns:
            清理后的有效系列名称，如果无效则返回None
        """
        if not name or len(name) <= 1:
            return None
        name = UnclassifiedFunctions.normalize_chinese(name)
        name = re.sub('[\\s.．。·・+＋\\-－—_＿\\d]+$', '', name)
        name = re.sub('[第章话集卷期篇季部册上中下前后完全][篇话集卷期章节部册全]*$', '', name)
        name = re.sub('(?i)vol\\.?\\s*\\d*$', '', name)
        name = re.sub('(?i)volume\\s*\\d*$', '', name)
        name = re.sub('(?i)part\\s*\\d*$', '', name)
        name = name.strip()
        if re.search('(?i)comic', name):
            return None
        words = name.split()
        if all((len(word) <= 1 for word in words)) and len(''.join(words)) <= 3:
            return None
        if not name or len(name) <= 1 or (len(name) > 0 and len(name.split()[-1]) <= 1):
            return None
        return name

    def timeout(self, seconds):
        """超时装饰器"""
    
        def decorator(self, func):
    
            @functools.wraps(func)
            def wrapper(self, *args, **kwargs):
    
                def handler(self, signum, frame):
                    raise TimeoutError(f'函数执行超时 ({seconds}秒)')
                if sys.platform != 'win32':
                    original_handler = signal.signal(signal.SIGALRM, handler)
                    signal.alarm(seconds)
                else:
                    timer = threading.Timer(seconds, lambda: threading._shutdown())
                    timer.start()
                try:
                    result = func(*args, **kwargs)
                finally:
                    if sys.platform != 'win32':
                        signal.alarm(0)
                        signal.signal(signal.SIGALRM, original_handler)
                    else:
                        timer.cancel()
                return result
            return wrapper
        return decorator

    def normalize_chinese(self, text):
        """标准化中文文本（统一转换为简体）"""
        return text

import os
import logging
import concurrent.futures
from tqdm import tqdm
from datetime import datetime
import json
import regex as re
import threading
import pangu  # 添加 pangu 库
from charset_normalizer import from_bytes
from pathlib import Path
import os
from datetime import datetime
import logging
from colorama import init, Fore, Style
import argparse
import pyperclip
from difflib import Differ  # 添加 difflib 导入
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Header, Footer, Button, RadioSet, RadioButton, Static
from textual.binding import Binding
from textual.screen import Screen
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from nodes.tui.textual_preset import create_config_app

# 初始化 colorama
init()

# 全局配置变量
add_artist_name_enabled = True
# 支持的压缩文件扩展名
ARCHIVE_EXTENSIONS = ('.zip', '.rar', '.7z', '.cbz', '.cbr')

def highlight_diff(old_str: str, new_str: str) -> str:
    """使用 difflib 高亮显示字符串差异"""
    d = Differ()
    diff = list(d.compare(old_str, new_str))
    
    colored = []
    for elem in diff:
        if elem.startswith('-'):
            # 删除部分：红色 + 删除线
            colored.append(f"{Fore.RED}\033[9m{elem[2:]}\033[29m{Style.RESET_ALL}")
        elif elem.startswith('+'):
            # 新增部分：绿色 + 加粗
            colored.append(f"{Fore.GREEN}\033[1m{elem[2:]}\033[22m{Style.RESET_ALL}")
        elif elem.startswith(' '):
            # 未修改部分：原样显示
            colored.append(elem[2:])
    return '🔄 ' + ''.join(colored)

# 日志配置
class ColoredFormatter(logging.Formatter):
    """自定义的彩色日志格式化器"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_msg = None
        self._msg_count = {}
        
    def format(self, record):
        # 如果是重命名消息，检查是否重复
        if "重命名" in record.msg:
            # 如果消息完全相同，不重复显示
            if record.msg == self._last_msg:
                return ""
            self._last_msg = record.msg
            
            # 提取原始路径和新路径
            old_path, new_path = record.msg.split(" -> ")
            old_path = old_path.replace("重命名: ", "")
            
            # 分离路径和文件名
            old_dir, old_name = os.path.split(old_path)
            new_dir, new_name = os.path.split(new_path)
            
            # 如果路径相同，只显示文件名的差异
            if old_dir == new_dir:
                record.msg = highlight_diff(old_name, new_name)
            else:
                # 如果路径不同，分别显示旧路径和新路径
                record.msg = f"🔄 {Fore.RED}\033[9m{old_path}\033[29m{Style.RESET_ALL} -> {Fore.GREEN}\033[1m{new_path}\033[22m{Style.RESET_ALL}"
        elif "出错" in record.msg.lower() or "error" in record.msg.lower():
            # 错误信息处理
            if "codec can't encode" in record.msg or "codec can't decode" in record.msg:
                # 编码错误，简化显示
                filename = record.msg.split("character", 1)[0].split("encode", 1)[0].strip()
                record.msg = f"❌ {Fore.RED}编码错误{Style.RESET_ALL}: {filename}"
            elif "path is on mount" in record.msg:
                # 路径错误，简化显示
                folder = record.msg.split("处理文件夹", 1)[1].split("出错", 1)[0].strip()
                record.msg = f"⚠️ {Fore.YELLOW}跨盘符{Style.RESET_ALL}: {folder}"
            else:
                # 其他错误
                record.msg = f"❌ {Fore.RED}{record.msg}{Style.RESET_ALL}"
        else:
            # 其他类型的日志
            if record.levelno == logging.INFO:
                color = Fore.GREEN
                emoji = "✅ "
            elif record.levelno == logging.WARNING:
                color = Fore.YELLOW
                emoji = "⚠️ "
            elif record.levelno == logging.ERROR:
                color = Fore.RED
                emoji = "❌ "
            else:
                color = Fore.WHITE
                emoji = "ℹ️ "
            record.msg = f"{emoji}{color}{record.msg}{Style.RESET_ALL}"
            
        return super().format(record)

# 配置日志处理器
logging.basicConfig(level=logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColoredFormatter('%(message)s'))
logging.getLogger('').handlers = [console_handler]

# 配置选项
exclude_keywords = ['[00待分类]', '[00去图]', '[01杂]', '[02COS]']
# 禁止添加画师名的关键词，如果文件名中包含这些关键词，也会删除已有的画师名
forbidden_artist_keywords = ['[02COS]']

def detect_and_decode_filename(filename):
    """
    解码文件名，处理特殊字符，统一转换为 UTF-8 编码。
    """
    try:
        # 如果已经是有效的UTF-8字符串，直接返回
        if isinstance(filename, str):
            return filename
            
        # 如果是bytes，尝试解码
        if isinstance(filename, bytes):
            try:
                return filename.decode('utf-8')
            except UnicodeDecodeError:
                pass
            
            # 尝试其他编码
            encodings = ['utf-8', 'gbk', 'shift-jis', 'euc-jp', 'cp932']
            for encoding in encodings:
                try:
                    return filename.decode(encoding)
                except UnicodeDecodeError:
                    continue
                    
            # 如果所有编码都失败，使用 charset_normalizer
            result = from_bytes(filename).best()
            if result:
                return str(result)
                
        return filename
    except Exception as e:
        logging.error(f"解码文件名出错: {filename}")
        return filename

def has_forbidden_keyword(filename):
    """检查文件名是否包含禁止画师名的关键词"""
    return any(keyword in filename for keyword in forbidden_artist_keywords)

def normalize_filename(filename):
    """
    标准化文件名以进行比较
    1. 移除所有空格
    2. 转换为小写
    3. 保留数字和标点符号
    """
    # 移除所有空格并转换为小写
    normalized = ''.join(filename.split()).lower()
    return normalized

def get_unique_filename_with_samename(directory: str, filename: str, original_path: str = None) -> str:
    """
    检查文件名是否存在，如果存在则添加[samename_n]后缀
    Args:
        directory: 文件所在目录
        filename: 完整文件名（包含扩展名）
        original_path: 原始文件的完整路径，用于排除自身
    Returns:
        str: 唯一的文件名
    """
    base, ext = os.path.splitext(filename)
    # 对文件名进行pangu格式化
    base = pangu.spacing_text(base)
    new_filename = f"{base}{ext}"
    
    # 如果文件不存在，或者是自身，直接返回
    new_path = os.path.join(directory, new_filename)
    if not os.path.exists(new_path) or (original_path and os.path.samefile(new_path, original_path)):
        return new_filename
        
    # 如果存在同名文件，添加编号
    counter = 1
    while True:
        current_filename = f"{base}[samename_{counter}]{ext}"
        current_path = os.path.join(directory, current_filename)
        if not os.path.exists(current_path):
            return current_filename
        counter += 1

def get_unique_filename(directory, filename, artist_name, is_excluded=False):
    """生成唯一文件名"""
    base, ext = os.path.splitext(filename)
    
    # 如果包含禁止关键词，删除画师名
    if has_forbidden_keyword(base):
        base = base.replace(artist_name, '')
    # 如果不包含禁止关键词，且存在画师名，则删除以便后续统一处理
    elif artist_name in base:
        base = base.replace(artist_name, '')

    # 使用 pangu 处理文字和数字之间的空格
    base = pangu.spacing_text(base)

    # 如果是排除的文件夹，直接返回处理后的文件名
    if is_excluded:
        filename = f"{base}{ext}"
        return get_unique_filename_with_samename(directory, filename)

    # 修改正则替换模式，更谨慎地处理日文字符
    basic_patterns = [
        # 统一处理各种括号为英文半角括号
        (r'（', '('),
        (r'）', ')'),
        (r'\uff08', '('),  # 全角左括号的 Unicode
        (r'\uff09', ')'),  # 全角右括号的 Unicode
        # 统一处理各种方括号为英文半角方括号
        (r'【', '['),
        (r'】', ']'),
        (r'［', '['),
        (r'］', ']'),
        (r'\uff3b', '['),  # 全角左方括号的 Unicode
        (r'\uff3d', ']'),  # 全角右方括号的 Unicode
        # 统一处理花括号
        (r'｛', '{'),
        (r'｝', '}'),
        (r'〈', '<'),
        (r'〉', '>'),
        # 清理空括号和空方框（包括可能的空格）
        (r'\(\s*\)\s*', r' '),  # 清理空括号
        (r'\[\s*\]\s*', r' '),  # 清理空方框
        (r'\{\s*\}\s*', r' '),  # 清理空花括号
        (r'\<\s*\>\s*', r' '),  # 清理空尖括号
        # 只处理两个及以上的连续空格
        (r'\s{2,}', r' '),
        # 修改可能导致问题的替换模式
        (r'【(?![々〇〈〉《》「」『』【】〔〕］［])([^【】]+)】', r'[\1]'),
        (r'（(?![々〇〈〉《》「」『』【】〔〕］［])([^（）]+)）', r'(\1)'),
        (r'【(.*?)】', r'[\1]'),
        (r'（(.*?)）', r'(\1)'),
        (r'［(.*?)］', r'[\1]'),
        (r'〈(.*?)〉', r'<\1>'),
        (r'｛(.*?)｝', r'{\1}'),
        # 其他清理规则
        (r'(单行本)', r''),
        (r'(同人志)', r''),
        (r'\{(.*?)\}', r''),
        (r'\{\d+w\}', r''),
        (r'\{\d+p\}', r''),
        (r'\{\d+px\}', r''),
        (r'\(\d+px\)', r''),
        (r'\{\d+de\}', r''),
        (r'\{\d+\.?\d*[kKwW]?@PX\}', r''),  # 匹配如 {1.8k@PX}、{215@PX}
        (r'\{\d+\.?\d*[kKwW]?@WD\}', r''),  # 匹配如 {1800w@WD}、{1.8k@WD}
        (r'\{\d+%?@DE\}', r''),  
        # 匹配如 {85%@DE}
        (r'\[multi\]', r''),
        (r'\[trash\]', r''),
        # 清理samename标记，以便重新添加
        (r'\[multi\-main\]', r''),
        (r'\[samename_\d+\]', r''),
    ]
    
    advanced_patterns = [
        (r'Digital', 'DL'),
        # 标准化日期格式
        (r'\[(\d{4})\.(\d{2})\]', r'(\1.\2)'),
        (r'\((\d{4})年(\d{1,2})月\)', r'(\1.\2)'),
        # 标准化C编号格式
        (r'Fate.*Grand.*Order', 'FGO'),
        (r'艦隊これくしょん.*-.*艦これ.*-', '舰C'),
        (r'PIXIV FANBOX', 'FANBOX'),
        (r'\((MJK[^\)]+)\)', ''),
        (r'^\) ', ''),
        (r'ibm5100', ''),
        (r'20(\d+)年(\d+)月号', r'\1-\2'),
        (r'(单行本)', r''),
    ]

    prefix_priority = [
        # 优先处理同人志编号
        r'(C\d+)',
        r'(COMIC1☆\d+)',
        r'(例大祭\d*)',
        r'(FF\d+)',
        # 日期格式
        r'(\d{4}\.\d{2})',  # 标准化后的年月格式
        r'(\d{4}年\d{1,2}月)',  # 日文年月格式
        r'(\d{2}\.\d{2})',
        r'(?<!\d)(\d{4})(?!\d)',
        r'(\d{2}\-\d{2})',
        # 其他格式
        r'([^()]*)COMIC[^()]*',
        r'([^()]*)快楽天[^()]*',
        r'([^()]*)Comic[^()]*',
        r'([^()]*)VOL[^()]*',
        r'([^()]*)永遠娘[^()]*',
        r'(.*?\d+.*?)',
    ]

    suffix_keywords = [
        r'漢化',                # 日语的 "汉"
        r'汉化',              # 汉化
        r'翻訳',              # 翻译
        r'无修',              # 无修正
        r'無修',              # 日语的 "无修正"
        r'DL版',              # 下载版
        r'掃圖',              # 扫图
        r'翻譯',              # 翻译 (繁体字)
        r'Digital',           # 数字版
        r'製作',              # 制作
        r'重嵌',              # 重新嵌入
        r'CG集',              # CG 集合
        r'掃', 
        r'制作', 
        r'排序 ', 
        r'截止',
        r'去码',
        
        r'\d+[GMK]B',         # 文件大小信息（如123MB、45KB等）
    ]

    # 应用基本替换规则
    for pattern, replacement in basic_patterns:
        base = re.sub(pattern, replacement, base)

    # 对非排除文件夹应用高级替换规则
    for pattern, replacement in advanced_patterns:
        base = re.sub(pattern, replacement, base)

    # 以下是非排除文件夹的处理逻辑
    pattern_brackets = re.compile(r'\[([^\[\]]+)\]')
    pattern_parentheses = re.compile(r'\(([^\(\)]+)\)')
    
    # 提取方括号和圆括号中的内容
    group1 = pattern_brackets.findall(base)  # 找到所有方括号内容
    group3 = pattern_brackets.sub('', base)  # 移除所有方括号内容
    group2 = pattern_parentheses.findall(group3)  # 找到所有圆括号内容
    group3 = pattern_parentheses.sub('', group3).strip()  # 移除所有圆括号内容并去除首尾空格
    
    # 将 group1 和 group2 组合为一个完整的列表
    all_groups = group1 + group2
    
    # 分离出 prefix 和 suffix 部分
    prefix_elements = []
    suffix_elements = []
    middle_elements = []

    # 收集所有元素及其优先级
    suffix_candidates = []
    prefix_candidates = []
    artist_elements = []
    remaining_elements = all_groups.copy()  # 创建待处理元素的副本
    
    # 先处理画师名
    for element in all_groups:
        if has_artist_name(element, artist_name):
            artist_elements.append(element)
            remaining_elements.remove(element)
    
    # 处理后缀
    for element in remaining_elements[:]:  # 使用切片创建副本进行迭代
        if any(re.search(kw, element) for kw in suffix_keywords):
            for i, pattern in enumerate(prefix_priority):
                if re.search(pattern, element):
                    suffix_candidates.append((element, i))
                    remaining_elements.remove(element)
                    break
            else:
                suffix_candidates.append((element, len(prefix_priority)))
                remaining_elements.remove(element)
    
    # 处理前缀
    for element in remaining_elements[:]:
        matched = False
        # 检查是否同时包含日期和C编号
        c_match = re.search(r'C(\d+)', element)
        date_match = re.search(r'(\d{4})\.(\d{2})', element)
        
        if c_match and date_match:
            # 如果同时包含，分别处理
            c_num = c_match.group(0)
            date = f"({date_match.group(1)}.{date_match.group(2)})"
            prefix_candidates.append((f"({c_num})", 0))  # C编号优先级最高
            prefix_candidates.append((date, 4))  # 日期次之
            remaining_elements.remove(element)
            matched = True
        else:
            # 如果不是同时包含，按原有逻辑处理
            for i, pattern in enumerate(prefix_priority):
                if re.search(pattern, element):
                    prefix_candidates.append((element, i))
                    remaining_elements.remove(element)
                    matched = True
                    break
        
        if not matched:
            middle_elements.append(f"[{element}]")
    
    # 按优先级排序并添加到前缀列表
    prefix_candidates.sort(key=lambda x: x[1])
    for element, priority in prefix_candidates:
        if f"({element})" not in prefix_elements:
            prefix_elements.append(f"({element})")
    
    # 按优先级排序并添加到后缀列表
    suffix_candidates.sort(key=lambda x: x[1])
    for element, priority in suffix_candidates:
        if f"[{element}]" not in suffix_elements:
            suffix_elements.append(f"[{element}]")
    
    # 最后添加画师元素（只在不包含禁止关键词时添加）
    if not has_forbidden_keyword(base):
        for element in artist_elements:
            if f"[{element}]" not in suffix_elements:
                suffix_elements.append(f"[{element}]")
    
    # 拼接新的文件名，prefix 在前，group3 在中间，suffix 在后
    prefix_part = f"{' '.join(prefix_elements)} " if prefix_elements else ""
    middle_part = f"{group3} {' '.join(middle_elements)}".strip()
    suffix_part = f" {' '.join(suffix_elements)}" if suffix_elements else ""
    
    new_base = f"{prefix_part}{middle_part}{suffix_part}".strip()
    
    # 最后再次清理可能残留的空括号和空方框
    new_base = re.sub(r'\(\s*\)\s*', ' ', new_base)  # 清理空括号
    new_base = re.sub(r'\[\s*\]\s*', ' ', new_base)  # 清理空方框
    new_base = re.sub(r'\s{2,}', ' ', new_base)  # 清理多余空格
    new_base = new_base.strip()
    
    # 检查文件是否存在，如果存在则添加[samename_n]后缀
    filename = f"{new_base}{ext}"
    return get_unique_filename_with_samename(directory, filename)

def has_artist_name(filename, artist_name):
    """检查文件名是否包含画师名"""
    artist_name_lower = artist_name.lower()
    filename_lower = filename.lower()
    keywords = re.split(r'[\[\]\(\)\s]+', artist_name_lower)
    keywords = [keyword for keyword in keywords if keyword]
    return any(keyword in filename_lower for keyword in set(keywords))

def append_artist_name(filename, artist_name):
    """将画师名追加到文件名末尾"""
    base, ext = os.path.splitext(filename)
    return f"{base}{artist_name}{ext}"

def process_files_in_directory(directory, artist_name):
    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f)) and f.lower().endswith(ARCHIVE_EXTENSIONS)]
    
    modified_files_count = 0
    
    # 检查是否是排除的文件夹（仅用于决定是否添加画师名）
    is_excluded = any(keyword in directory for keyword in exclude_keywords)
    
    # 检查是否包含禁止画师名的关键词
    has_forbidden_keyword = any(keyword in directory for keyword in forbidden_artist_keywords)
    
    # 先检查是否有需要修改的文件
    files_to_modify = []
    for filename in files:
        original_file_path = os.path.join(directory, filename)
        filename = detect_and_decode_filename(filename)
        new_filename = filename
        
        # 对所有文件应用格式化，包括排除文件夹中的文件
        # new_filename = get_unique_filename(directory, new_filename, artist_name, is_excluded)
        
        # 只有在非排除文件夹、启用了画师名添加、不包含禁止关键词时才添加画师名
        if not is_excluded and not has_forbidden_keyword and add_artist_name_enabled and artist_name not in exclude_keywords and not has_artist_name(new_filename, artist_name):
            new_filename = append_artist_name(new_filename, artist_name)
        
        # 确保文件名唯一（始终传入原始路径以排除自身）
        final_filename = get_unique_filename_with_samename(directory, new_filename, original_file_path)
        
        if final_filename != filename:
            files_to_modify.append((filename, final_filename, original_file_path))

    # 如果有文件需要修改，显示进度条并处理
    if files_to_modify:
        with tqdm(total=len(files_to_modify), desc=f"重命名文件", unit="file", ncols=0, leave=True) as pbar:
            for filename, new_filename, original_file_path in files_to_modify:
                # 获取原始文件的时间戳
                original_stat = os.stat(original_file_path)
                
                new_file_path = os.path.join(directory, new_filename)
                
                try:
                    # 重命名文件
                    os.rename(original_file_path, new_file_path)
                    
                    # 恢复时间戳
                    os.utime(new_file_path, (original_stat.st_atime, original_stat.st_mtime))
                    
                    try:
                        rel_old_path = os.path.relpath(original_file_path, base_path)
                        rel_new_path = os.path.relpath(new_file_path, base_path)
                    except ValueError:
                        rel_old_path = original_file_path
                        rel_new_path = new_file_path
                        
                    log_message = f"重命名: {rel_old_path} -> {rel_new_path}"
                    logging.info(log_message)
                except OSError as e:
                    logging.error(f"重命名文件失败 {original_file_path}: {str(e)}")
                    continue
                    
                # 更新进度条，但不显示文件名（避免重复）
                pbar.update(1)
                modified_files_count += 1

    return modified_files_count

def format_folder_name(folder_name):
    """格式化文件夹名称"""
    # 先进行基本的替换规则
    patterns_and_replacements = [
        (r'\[\#s\]', '#'),
        (r'（', '('),
        (r'）', ')'),
        (r'【', '['),
        (r'】', ']'),
        (r'［', '['),
        (r'］', ']'),
        (r'｛', '{'),
        (r'｝', '}'),
        (r'｜', '|'),
        (r'～', '~'),
        
    ]
    
    formatted_name = folder_name
    for pattern, replacement in patterns_and_replacements:
        formatted_name = re.sub(pattern, replacement, formatted_name)
    
    # 然后使用 pangu 处理文字和数字之间的空格
    try:
        formatted_name = pangu.spacing_text(formatted_name)
    except Exception as e:
        logging.warning(f"pangu 格式化失败，跳过空格处理: {str(e)}")
    
    # 最后处理多余的空格
    formatted_name = re.sub(r'\s{2,}', ' ', formatted_name)
    
    return formatted_name.strip()

def process_artist_folder(artist_path, artist_name):
    """递归处理画师文件夹及其所有子文件夹"""
    total_modified_files_count = 0

    try:
        # 检查当前文件夹是否在排除列表中
        if any(keyword in artist_path for keyword in exclude_keywords):
            return 0

        for root, dirs, files in os.walk(artist_path, topdown=True):
            # 如果当前目录包含排除关键词，跳过整个目录
            if any(keyword in root for keyword in exclude_keywords):
                continue
            
            # 处理子文件夹名称
            for i, dir_name in enumerate(dirs):
                # 跳过排除的文件夹
                if any(keyword in dir_name for keyword in exclude_keywords):
                    continue
                    
                # 获取完整路径
                old_path = os.path.join(root, dir_name)
                
                # 如果不是一级目录，则应用格式化
                if root != artist_path:
                    new_name = format_folder_name(dir_name)
                    if new_name != dir_name:
                        new_path = os.path.join(root, new_name)
                        try:
                            # 保存原始时间戳
                            dir_stat = os.stat(old_path)
                            # 重命名文件夹
                            os.rename(old_path, new_path)
                            # 恢复时间戳
                            os.utime(new_path, (dir_stat.st_atime, dir_stat.st_mtime))
                            # 更新 dirs 列表中的名称，确保 os.walk 继续正常工作
                            dirs[i] = new_name
                            logging.info(f"重命名文件夹: {old_path} -> {new_path}")
                        except Exception as e:
                            logging.error(f"重命名文件夹出错 {old_path}: {str(e)}")
                
            # 处理当前目录下的所有压缩文件
            modified_files_count = process_files_in_directory(root, artist_name)
            total_modified_files_count += modified_files_count
    except Exception as e:
        logging.error(f"处理文件夹出错: {e}")

    return total_modified_files_count

def process_folders(base_path):
    """
    处理基础路径下的所有画师文件夹。
    不使用多线程，逐个处理每个画师的文件。
    """
    # 获取所有画师文件夹
    artist_folders = [
        folder for folder in os.listdir(base_path)
        if os.path.isdir(os.path.join(base_path, folder))
    ]

    total_processed = 0
    total_modified = 0
    total_files = 0

    # 逐个处理画师文件夹
    for folder in artist_folders:
        try:
            artist_path = os.path.join(base_path, folder)
            artist_name = get_artist_name(base_path, artist_path)
            
            # 处理画师文件夹中的文件，并获取修改文件数量
            modified_files_count = process_artist_folder(artist_path, artist_name)
            total_processed += 1
            total_modified += modified_files_count
            
            # 统计该文件夹中的压缩文件总数
            for root, _, files in os.walk(artist_path):
                total_files += len([f for f in files if f.lower().endswith(ARCHIVE_EXTENSIONS)])
            
        except Exception as e:
            logging.error(f"处理文件夹 {folder} 出错: {e}")
            
    print(f"\n处理完成:")
    print(f"- 总共处理了 {total_processed} 个文件夹")
    print(f"- 扫描了 {total_files} 个压缩文件")
    if total_modified > 0:
        print(f"- 重命名了 {total_modified} 个文件")
    else:
        print(f"- ✨ 所有文件名都符合规范，没有文件需要重命名")

def get_artist_name(target_directory, archive_path):
    """
    从压缩文件路径中提取艺术家名称。
    获取基于相对路径的第一部分作为艺术家名称。
    """
    try:
        # 获取相对路径的第一部分作为艺术家名称
        rel_path = os.path.relpath(archive_path, target_directory)
        artist_name = rel_path.split(os.sep)[0]
        
        # 如果是方括号包围的名称，直接返回
        if artist_name.startswith('[') and artist_name.endswith(']'):
            return artist_name
            
        # 如果不是方括号包围的，加上方括号
        return f"[{artist_name}]"
    except Exception as e:
        logging.error(f"提取艺术家名称时出错: {e}")
        return ""

def record_folder_timestamps(target_directory):
    """记录target_directory下所有文件夹的时间戳。"""
    folder_timestamps = {}
    for root, dirs, files in os.walk(target_directory):
        for dir in dirs:
            try:
                folder_path = os.path.join(root, dir)
                folder_stat = os.stat(folder_path)
                folder_timestamps[folder_path] = (folder_stat.st_atime, folder_stat.st_mtime)
            except FileNotFoundError:
                logging.warning(f"找不到文件夹: {folder_path}")
                continue
            except Exception as e:
                logging.error(f"处理文件夹时出错 {folder_path}: {str(e)}")
                continue
    
    return folder_timestamps

def restore_folder_timestamps(folder_timestamps):
    """恢复之前记录的文件夹时间戳。"""
    for folder_path, (atime, mtime) in folder_timestamps.items():
        try:
            if os.path.exists(folder_path):
                os.utime(folder_path, (atime, mtime))
        except Exception as e:
            logging.error(f"恢复文件夹时间戳时出错 {folder_path}: {str(e)}")
            continue

def main():
    """主函数"""
    # 定义复选框选项
    checkbox_options = [
        ("无画师模式 - 不添加画师名后缀", "no_artist", "--no-artist"),
        ("保持时间戳 - 保持文件的修改时间", "keep_timestamp", "--keep-timestamp", True),
        ("多画师模式 - 处理整个目录", "multi_mode", "--mode multi"),
        ("单画师模式 - 只处理单个画师的文件夹", "single_mode", "--mode single"),
        ("从剪贴板读取路径", "clipboard", "-c", True),  # 默认开启
    ]

    # 定义输入框选项
    input_options = [
        ("路径", "path", "--path", "", "输入要处理的路径，留空使用默认路径"),
    ]

    # 预设配置
    preset_configs = {
        "标准多画师": {
            "description": "标准多画师模式，会添加画师名后缀",
            "checkbox_options": ["keep_timestamp", "multi_mode", "clipboard"],
            "input_values": {"path": ""}
        },
        "标准单画师": {
            "description": "标准单画师模式，会添加画师名后缀", 
            "checkbox_options": ["keep_timestamp", "single_mode", "clipboard"],
            "input_values": {"path": ""}
        },
        "无画师模式": {
            "description": "不添加画师名后缀的重命名模式",
            "checkbox_options": ["no_artist", "keep_timestamp", "clipboard"],
            "input_values": {"path": ""}
        }
    }

    # 创建并运行配置界面
    app = create_config_app(
        program=__file__,
        checkbox_options=checkbox_options,
        input_options=input_options,
        title="自动唯一文件名工具",
        preset_configs=preset_configs
    )
    app.run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='处理文件名重命名')
    parser.add_argument('-c', '--clipboard', action='store_true', help='从剪贴板读取路径')
    parser.add_argument('-m', '--mode', choices=['multi', 'single'], help='处理模式：multi(多人模式)或single(单人模式)')
    parser.add_argument('--path', help='要处理的路径')
    parser.add_argument('--no-artist', action='store_true', help='无画师模式 - 不添加画师名后缀')
    parser.add_argument('--keep-timestamp', action='store_true', help='保持文件的修改时间')
    args = parser.parse_args()

    if len(sys.argv) == 1:  # 如果没有命令行参数，启动TUI界面
        main()
        sys.exit(0)

    # 处理路径参数
    if args.clipboard:
        try:
            path = pyperclip.paste().strip().strip('"')
            if not os.path.exists(path):
                print(f"{Fore.RED}剪贴板中的路径无效: {path}{Style.RESET_ALL}")
                exit(1)
            print(f"{Fore.GREEN}已从剪贴板读取路径: {path}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}从剪贴板读取路径失败: {e}{Style.RESET_ALL}")
            exit(1)
    else:
        path = args.path or r"E:\1EHV"
        print(f"{Fore.GREEN}使用路径: {path}{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}当前模式: {'多人模式' if args.mode == 'multi' else '单人模式'}{Style.RESET_ALL}")
    
    # 根据命令行参数设置全局变量
    add_artist_name_enabled = not args.no_artist

    # 根据模式确定基础路径和处理方式
    if args.mode == 'multi':
        base_path = path
        if args.keep_timestamp:
            older_timestamps = record_folder_timestamps(base_path)
        process_folders(base_path)
        if args.keep_timestamp:
            restore_folder_timestamps(older_timestamps)
    else:  # single mode
        if not os.path.isdir(path):
            print(f"{Fore.RED}无效的路径: {path}{Style.RESET_ALL}")
            sys.exit(1)
            
        # 在单人模式下，path是画师文件夹的路径
        artist_path = path
        base_path = os.path.dirname(artist_path)  # 获取父目录作为base_path
        artist_name = get_artist_name(base_path, artist_path)
        
        print(f"{Fore.CYAN}正在处理画师文件夹: {os.path.basename(artist_path)}{Style.RESET_ALL}")
        
        if args.keep_timestamp:
            older_timestamps = record_folder_timestamps(artist_path)
            
        modified_files_count = process_artist_folder(artist_path, artist_name)
        
        if args.keep_timestamp:
            restore_folder_timestamps(older_timestamps)
        
        # 统计该文件夹中的压缩文件总数
        total_files = sum(len([f for f in files if f.lower().endswith(ARCHIVE_EXTENSIONS)])
                         for _, _, files in os.walk(artist_path))
        
        print(f"\n{Fore.GREEN}处理完成:{Style.RESET_ALL}")
        print(f"- 扫描了 {total_files} 个压缩文件")
        if modified_files_count > 0:
            print(f"- 重命名了 {modified_files_count} 个文件")
        else:
            print(f"- ✨ 所有文件名都符合规范，没有文件需要重命名")

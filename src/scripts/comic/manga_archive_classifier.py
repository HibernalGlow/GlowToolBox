import os
import sys
import re
import subprocess
from pathlib import Path
import shutil
from datetime import datetime
import tempfile
import argparse
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from collections import defaultdict
from rapidfuzz import fuzz, process
import signal
import functools
from opencc import OpenCC
from diff_match_patch import diff_match_patch
import difflib
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from nodes.tui.textual_preset import create_config_app

# 导入自定义工具
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nodes.tui.rich_logger import RichProgressHandler
# from utils.file_operation_monitor import init_file_monitor  # 使用全局文件监控

# # 初始化文件监控器
# monitor = init_file_monitor()

# 初始化全局日志处理器
global_handler = None

def get_handler():
    """获取全局日志处理器，如果不存在则创建一个新的"""
    global global_handler
    if global_handler is None:
        # 自定义布局配置
        layout_config = {
            "stats": {"size": 3, "title": "处理进度"},
            "current_task": {"size": 2, "title": "当前任务"},
            "archive_process": {"size": 3, "title": "压缩包处理"},
            "folder_process": {"size": 3, "title": "文件夹处理"},
            "series_extract": {"size": 4, "title": "系列提取"},  # 新增系列提取面板
            "post_process": {"size": 3, "title": "后续处理"},
            "update_log": {"size": 6, "title": "更新日志"}
        }
        
        # 自定义样式配置
        style_config = {
            "border_style": "cyan",
            "title_style": "yellow bold",
            "padding": (0, 1),
            # 为每个面板设置不同的颜色
            "panel_styles": {
                "stats": "green",
                "current_task": "blue",
                "archive_process": "magenta",
                "folder_process": "cyan",
                "series_extract": "yellow",  # 新增面板的颜色
                "post_process": "yellow",
                "update_log": "white"
            }
        }
        
        global_handler = RichProgressHandler(
            layout_config=layout_config,
            style_config=style_config
        )
        global_handler.__enter__()
    return global_handler

def close_handler():
    """关闭全局日志处理器"""
    global global_handler
    if global_handler is not None:
        global_handler.__exit__(None, None, None)
        global_handler = None

# 初始化OpenCC转换器
cc_t2s = OpenCC('t2s')  # 繁体转简体
cc_s2t = OpenCC('s2t')  # 简体转繁体

def normalize_chinese(text):
    """标准化中文文本（统一转换为简体）"""
    # return cc_t2s.convert(text)
    return text
    
# 设置文件系统编码
if sys.platform == 'win32':
    try:
        import win32api
        def win32_path_exists(path):
            try:
                win32api.GetFileAttributes(path)
                return True
            except:
                print("未安装win32api模块，某些路径可能无法正确处理")
                win32_path_exists = os.path.exists
    except ImportError:
        print("未安装win32api模块，某些路径可能无法正确处理")
        win32_path_exists = os.path.exists

# 定义支持的图片扩展名（扩展支持更多格式）
IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.jxl', '.avif', '.heic', '.heif', '.jfif',
    '.tiff', '.tif', '.psd', '.xcf'
}

# 定义系列前缀集合
SERIES_PREFIXES = {
    '[#s]',  # 标准系列标记
    '#',     # 简单系列标记
}

# 定义路径黑名单关键词
PATH_BLACKLIST = {
    '画集',
    '01视频',
    '02动图',
    '损坏压缩包',
}

# 定义系列提取黑名单规则
SERIES_BLACKLIST_PATTERNS = [
    r'画集',                # 画集
    r'fanbox',     # artbook/art book（不区分大小写）
    r'pixiv',    # artworks/art works（不区分大小写）
    r'・',          # 插画集（日文）
    r'杂图合集',           # 插画集（中文）
    r'01视频',
    r'02动图',
    r'作品集',             # 作品集
    r'01视频',
    r'02动图',
    r'损坏压缩包',
]

def is_series_blacklisted(filename):
    """检查文件名是否在系列提取黑名单中"""
    for pattern in SERIES_BLACKLIST_PATTERNS:
        if re.search(pattern, filename, re.IGNORECASE):
            return True
    return False

def is_path_blacklisted(path):
    """检查路径是否在黑名单中"""
    # 转换为小写进行比较
    path_lower = path.lower()
    return any(keyword.lower() in path_lower for keyword in PATH_BLACKLIST)

class TimeoutError(Exception):
    """超时异常"""
    pass

def timeout(seconds):
    """超时装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            def handler(signum, frame):
                raise TimeoutError(f"函数执行超时 ({seconds}秒)")

            # 设置信号处理器
            if sys.platform != 'win32':  # Unix系统使用信号
                original_handler = signal.signal(signal.SIGALRM, handler)
                signal.alarm(seconds)
            else:  # Windows系统使用线程
                timer = threading.Timer(seconds, lambda: threading._shutdown())
                timer.start()

            try:
                result = func(*args, **kwargs)
            finally:
                if sys.platform != 'win32':  # Unix系统
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, original_handler)
                else:  # Windows系统
                    timer.cancel()

            return result
        return wrapper
    return decorator

@timeout(60)
def run_7z_command(command, archive_path, operation="", additional_args=None, handler=None):
    """运行7z命令并返回输出"""
    try:
        # 基础命令
        cmd = ['7z', command]
        if additional_args:
            cmd.extend(additional_args)
        cmd.append(archive_path)
        
        # 运行命令并捕获输出
        # 使用cp932编码(日文Windows默认编码)来处理输出
        result = subprocess.run(cmd, capture_output=True, text=False, timeout=55)  # 设置subprocess超时为55秒
        try:
            # 首先尝试使用cp932解码
            output = result.stdout.decode('cp932')
        except UnicodeDecodeError:
            try:
                # 如果cp932失败，尝试utf-8
                output = result.stdout.decode('utf-8')
            except UnicodeDecodeError:
                # 如果都失败，使用errors='replace'来替换无法解码的字符
                output = result.stdout.decode('utf-8', errors='replace')
        
        return output if output else ""
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"7z命令执行超时: {archive_path}")
    except Exception as e:
        if handler:
            handler.update_panel("update_log", f"❌ 执行7z命令时出错 {archive_path}: {str(e)}")
        return ""

@timeout(60)
def is_archive_corrupted(archive_path):
    """检查压缩包是否损坏"""
    try:
        # 使用7z测试压缩包完整性
        cmd = ['7z', 't', archive_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=55)
        return result.returncode != 0
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"检查压缩包完整性超时: {archive_path}")
    except Exception:
        return True

@timeout(60)
def count_images_in_archive(archive_path, handler=None):
    """使用7z的列表模式统计压缩包中的图片数量"""
    try:
        if handler is None:
            handler = get_handler()
            
        # 首先检查压缩包是否损坏
        if is_archive_corrupted(archive_path):
            handler.update_panel("update_log", f"⚠️ 压缩包已损坏，跳过处理: {archive_path}")
            return -1
            
        # 使用7z的列表命令，添加-slt参数来获取详细信息
        output = run_7z_command('l', archive_path, additional_args=['-slt'], handler=handler)
        
        # 确保输出不为空
        if not output:
            handler.update_panel("update_log", f"❌ 无法获取压缩包内容列表: {archive_path}")
            return 0
            
        # 使用更高效的方式统计图片数量
        image_count = sum(1 for ext in IMAGE_EXTENSIONS if ext in output.lower())
        
        # 添加到更新日志
        handler.update_panel("update_log", f"📦 压缩包 '{os.path.basename(archive_path)}' 中包含 {image_count} 张图片")
        
        return image_count
    except TimeoutError as e:
        if handler:
            handler.update_panel("update_log", f"❌ 处理压缩包超时 {archive_path}: {str(e)}")
        return -1
    except Exception as e:
        if handler:
            handler.update_panel("update_log", f"❌ 处理压缩包时出错 {archive_path}: {str(e)}")
        return -1

def is_archive(path):
    """检查文件是否为支持的压缩包格式"""
    return Path(path).suffix.lower() in {'.zip', '.rar', '.7z', '.cbz', '.cbr'}

# 定义分类规则
CATEGORY_RULES = {
    "1. 同人志": {
        "patterns": [
            r'\[C\d+\]',           # [C97], [C98] 等
            r'\(C\d+\)',           # (C97), (C98) 等
            r'コミケ\d+',           # コミケ97 等
            r'COMIC\s*MARKET',      # COMIC MARKET
            r'COMIC1',              # COMIC1
            r'同人誌',              # 同人志（日文）
            r'同人志',              # 同人志（中文）
            r'コミケ',              # コミケ
            r'コミックマーケット',   # コミックマーケット
            r'例大祭',              # 例大祭
            r'サンクリ',            # サンクリ
            r'(?i)doujin',         # doujin（不区分大小写）
            r'COMIC1☆\d+',         # COMIC1☆17等
        ],
        "exclude_patterns": [
            r'画集',                # 排除画集
            r'artbook',
            r'art\s*works',
            r'01视频',
            r'02动图',
            r'art\s*works'
        ]
    },
    "2. 商业志": {
        "patterns": [
            r'(?i)magazine',        # magazine（不区分大小写）
            r'(?i)COMIC',      # commercial（不区分大小写）
            r'雑誌',                # 杂志（日文）
            r'杂志',                # 杂志（中文）
            r'商业',
            r'週刊',                # 周刊
            r'月刊',                # 月刊
            r'月号',                # 月号
            r'COMIC\s*REX',         # COMIC REX
            r'コミック',      # 青年JUMP
            r'ヤングマガジン',      # 青年Magazine
            r'\d{4}年\d{1,2}月号',  # yyyy年m月号
        ],
        "exclude_patterns": [
            r'同人',
            r'(?i)doujin',
            r'単行本',
            r'画集'
        ]
    },
    "3. 单行本": {
        "patterns": [
            r'単行本',              # 单行本（日文）
            r'单行本',              # 单行本（中文）
            r'(?i)tankoubon',       # tankoubon（不区分大小写）
            r'第\d+巻',             # 第X巻
            r'vol\.?\d+',          # vol.X 或 volX
            r'volume\s*\d+'        # volume X
        ],
        "exclude_patterns": [
            r'画集',
            r'artbook',
            r'art\s*works'
        ]
    },
    "4. 画集": {
        "patterns": [
            r'画集',                # 画集
            r'(?i)art\s*book',     # artbook/art book（不区分大小写）
            r'(?i)art\s*works',    # artworks/art works（不区分大小写）
            r'イラスト集',          # 插画集（日文）
            r'杂图合集',              # 插画集（中文）
            r'作品集',              # 作品集
            r'illustrations?',      # illustration/illustrations
            r'(?i)illust\s*collection'  # Illust Collection
        ],
        "exclude_patterns": []
    },
    "5. 同人CG": {
        "patterns": [
            r'同人CG',
        ],
        "exclude_patterns": []
    }
}

def get_category(path, handler=None):
    """根据路径名判断类别，使用正则表达式进行匹配"""
    if handler is None:
        handler = get_handler()
        
    filename = os.path.basename(path)
    
    # 首先检查是否为压缩包
    if not is_archive(path):
        return "未分类"
        
    # 检查压缩包是否损坏
    if is_archive_corrupted(path):
        return "损坏"
        
    # 检查是否为画集
    for pattern in CATEGORY_RULES["4. 画集"]["patterns"]:
        if re.search(pattern, filename, re.IGNORECASE):
            return "4. 画集"
    
    # 统计压缩包中的图片数量
    image_count = count_images_in_archive(path, handler)
    if image_count == -1:  # 表示压缩包损坏
        return "损坏"
        
    handler.update_panel("update_log", f"压缩包 '{filename}' 中包含 {image_count} 张图片")
    
    # 如果图片数量超过100且不是画集，检查其他分类规则
    if image_count >= 100:
        # 检查其他明确的分类规则
        for category, rules in CATEGORY_RULES.items():
            if category == "4. 画集":  # 跳过画集分类
                continue
                
            # 检查排除规则
            excluded = False
            for exclude_pattern in rules["exclude_patterns"]:
                if re.search(exclude_pattern, filename, re.IGNORECASE):
                    excluded = True
                    break
            
            if excluded:
                continue
                
            # 检查包含规则
            for pattern in rules["patterns"]:
                if re.search(pattern, filename, re.IGNORECASE):
                    return category
        
        # 如果没有匹配其他规则，则归类为单行本
        return "3. 单行本"
    
    # 如果图片数量不超过100，检查其他分类规则
    for category, rules in CATEGORY_RULES.items():
        if category == "4. 画集":  # 跳过画集分类，因为已经检查过了
            continue
            
        # 检查排除规则
        excluded = False
        for exclude_pattern in rules["exclude_patterns"]:
            if re.search(exclude_pattern, filename, re.IGNORECASE):
                excluded = True
                break
        
        if excluded:
            continue
            
        # 检查包含规则
        for pattern in rules["patterns"]:
            if re.search(pattern, filename, re.IGNORECASE):
                return category
                
    return "未分类"

def create_category_folders(base_path, handler=None):
    """在指定路径创建分类文件夹"""
    # 创建分类文件夹
    for category in CATEGORY_RULES.keys():
        category_path = os.path.join(base_path, category)
        if not os.path.exists(category_path):
            os.makedirs(category_path)
            if handler:
                handler.update_panel("update_log", f"📁 创建分类文件夹: {category}")
    
    # 创建损坏压缩包文件夹
    corrupted_path = os.path.join(base_path, "损坏压缩包")
    if not os.path.exists(corrupted_path):
        os.makedirs(corrupted_path)
        if handler:
            handler.update_panel("update_log", f"📁 创建损坏压缩包文件夹")

def move_file_to_category(file_path, category, handler=None):
    """将文件移动到对应的分类文件夹"""
    if category == "未分类":
        if handler:
            handler.update_panel("update_log", f"文件 '{file_path}' 未能匹配任何分类规则，保持原位置")
        return
        
    target_dir = os.path.join(os.path.dirname(file_path), category)
    target_path = os.path.join(target_dir, os.path.basename(file_path))
    
    if not os.path.exists(target_path):
        shutil.move(file_path, target_path)
        if handler:
            handler.update_panel("update_log", f"已移动到: {target_path}")
    else:
        if handler:
            handler.update_panel("update_log", f"目标路径已存在文件: {target_path}")

def move_corrupted_archive(file_path, base_path, handler=None):
    """移动损坏的压缩包到损坏压缩包文件夹，保持原有目录结构"""
    try:
        # 获取相对路径
        rel_path = os.path.relpath(os.path.dirname(file_path), base_path)
        # 构建目标路径
        corrupted_base = os.path.join(base_path, "损坏压缩包")
        target_dir = os.path.join(corrupted_base, rel_path)
        
        # 确保目标目录存在
        os.makedirs(target_dir, exist_ok=True)
        
        # 构建目标文件路径
        target_path = os.path.join(target_dir, os.path.basename(file_path))
        
        # 如果目标路径已存在，添加数字后缀
        if os.path.exists(target_path):
            base, ext = os.path.splitext(target_path)
            counter = 1
            while os.path.exists(f"{base}_{counter}{ext}"):
                counter += 1
            target_path = f"{base}_{counter}{ext}"
        
        # 移动文件
        shutil.move(file_path, target_path)
        if handler:
            handler.update_panel("update_log", f"📦 已移动损坏压缩包: {os.path.basename(file_path)} -> 损坏压缩包/{rel_path}")
            
    except Exception as e:
        if handler:
            handler.update_panel("update_log", f"❌ 移动损坏压缩包失败 {file_path}: {str(e)}")

def process_single_file(abs_path, handler=None):
    """处理单个文件"""
    try:
        if not os.path.exists(abs_path):
            if handler:
                handler.update_panel("update_log", f"❌ 路径不存在: {abs_path}")
            return
            
        if handler:
            handler.update_panel("current_task", f"处理文件: {os.path.basename(abs_path)}")
            handler.update_panel("archive_process", f"分析: {os.path.basename(abs_path)}")
        
        # 确保分类文件夹存在
        create_category_folders(os.path.dirname(abs_path))
        
        # 获取文件分类
        category = get_category(abs_path)
        
        # 如果是损坏的压缩包，移动到损坏压缩包文件夹
        if category == "损坏":
            if handler:
                handler.update_panel("update_log", f"⚠️ 压缩包已损坏: {os.path.basename(abs_path)}")
                handler.update_panel("archive_process", f"❌ 损坏: {os.path.basename(abs_path)}")
            move_corrupted_archive(abs_path, os.path.dirname(abs_path), handler)
            return
        
        # 移动文件到对应分类
        move_file_to_category(abs_path, category, handler)
        
        if handler:
            handler.update_panel("archive_process", f"✅ 完成: {os.path.basename(abs_path)} -> {category}")
        
    except Exception as e:
        if handler:
            handler.update_panel("update_log", f"❌ 处理文件时出错 {abs_path}: {str(e)}")
            handler.update_panel("archive_process", f"❌ 错误: {os.path.basename(abs_path)}")

def normalize_filename(filename):
    """去除文件名中的圆括号、方括号及其内容，返回规范化的文件名"""
    # 去掉扩展名
    name = os.path.splitext(filename)[0]
    
    # 去除方括号及其内容
    name = re.sub(r'\[[^\]]*\]', '', name)
    # 去除圆括号及其内容
    name = re.sub(r'\([^)]*\)', '', name)
    
    # 去除卷号标记，但保留数字
    name = re.sub(r'vol\.?|第|巻|卷', '', name, flags=re.IGNORECASE)
    
    # 去除多余的空格和标点
    name = re.sub(r'[\s!！?？_~～]+', ' ', name)
    name = name.strip()
    
    return name

# 相似度配置
SIMILARITY_CONFIG = {
    'THRESHOLD': 75,  # 基本相似度阈值
    'LENGTH_DIFF_MAX': 0.3,  # 长度差异最大值
    'RATIO_THRESHOLD': 75,  # 完全匹配阈值
    'PARTIAL_THRESHOLD': 85,  # 部分匹配阈值
    'TOKEN_THRESHOLD': 80,  # 标记匹配阈值
}

def is_in_series_folder(file_path):
    """检查文件是否已经在系列文件夹内"""
    parent_dir = os.path.dirname(file_path)
    parent_name = os.path.basename(parent_dir)
    
    # 检查是否有系列标记
    for prefix in SERIES_PREFIXES:
        if parent_name.startswith(prefix):
            # 提取系列名称并重新用 get_series_key 处理
            series_name = parent_name[len(prefix):]  # 去掉前缀
            parent_key = get_series_key(series_name)
            file_key = get_series_key(os.path.basename(file_path))
            return parent_key == file_key
    
    # 如果父目录名称是文件名的一部分（去除数字和括号后），则认为已在系列文件夹内
    parent_key = get_series_key(parent_name)
    file_key = get_series_key(os.path.basename(file_path))
    
    if parent_key and parent_key in file_key:
        return True
    return False

def calculate_similarity(str1, str2, handler=None):
    """计算两个字符串的相似度"""
    # 标准化中文（转换为简体）后再比较
    str1 = normalize_chinese(str1)
    str2 = normalize_chinese(str2)
    
    ratio = fuzz.ratio(str1.lower(), str2.lower())
    partial = fuzz.partial_ratio(str1.lower(), str2.lower())
    token = fuzz.token_sort_ratio(str1.lower(), str2.lower())
    
    max_similarity = max(ratio, partial, token)
    if handler and max_similarity >= SIMILARITY_CONFIG['THRESHOLD']:
        handler.update_panel("update_log", f"🔍 相似度: {max_similarity}%")
    return max_similarity

def is_similar_to_existing_folder(dir_path, series_name, handler=None):
    """检查是否存在相似的文件夹名称"""
    try:
        existing_folders = [d for d in os.listdir(dir_path) 
                          if os.path.isdir(os.path.join(dir_path, d))]
    except Exception as e:
        if handler:
            handler.update_panel("update_log", f"❌ 读取目录失败: {dir_path}")
        return False
    
    series_key = get_series_key(series_name, handler)
    
    for folder in existing_folders:
        # 检查所有支持的系列前缀
        is_series_folder = False
        folder_name = folder
        for prefix in SERIES_PREFIXES:
            if folder.startswith(prefix):
                # 对已有的系列文件夹使用相同的处理标准
                folder_name = folder[len(prefix):]  # 去掉前缀
                is_series_folder = True
                break
        
        if is_series_folder:
            folder_key = get_series_key(folder_name, handler)
            
            # 如果系列键完全相同，直接返回True
            if series_key == folder_key:
                if handler:
                    handler.update_panel("update_log", f"📁 找到相同系列文件夹: '{folder}'")
                return True
            
            # 否则计算相似度
            similarity = calculate_similarity(series_key, folder_key, handler)
            if similarity >= SIMILARITY_CONFIG['THRESHOLD']:
                if handler:
                    handler.update_panel("update_log", f"📁 找到相似文件夹: '{folder}'")
                return True
        else:
            # 对非系列文件夹使用原有的相似度检查
            similarity = calculate_similarity(series_name, folder, handler)
            if similarity >= SIMILARITY_CONFIG['THRESHOLD']:
                if handler:
                    handler.update_panel("update_log", f"📁 找到相似文件夹: '{folder}'")
                return True
    return False

def get_series_key(filename, handler=None):
    """获取用于系列比较的键值"""
    if handler:
        handler.update_panel("series_extract", f"处理文件: {filename}")
    
    # 创建一个虚拟的对比组，包含当前文件和自身的副本
    # 这样可以利用 find_series_groups 的逻辑来提取系列名称
    test_group = [filename, filename]
    series_groups = find_series_groups(test_group, handler)
    
    # 如果能找到系列名称，使用它
    if series_groups:
        series_name = next(iter(series_groups.keys()))
        if handler:
            handler.update_panel("series_extract", f"找到系列名称: {series_name}")
        return series_name
    
    # 如果找不到系列名称，退回到基本的预处理
    name = preprocess_filename(filename)
    name = normalize_chinese(name)
    
    if handler:
        handler.update_panel("series_extract", f"使用预处理结果: {name}")
    
    return name.strip()

def update_series_folder_name(old_path, handler=None):
    """更新系列文件夹名称为最新标准"""
    try:
        dir_name = os.path.basename(old_path)
        is_series = False
        prefix_used = None
        
        # 检查是否是系列文件夹
        for prefix in SERIES_PREFIXES:
            if dir_name.startswith(prefix):
                is_series = True
                prefix_used = prefix
                break
                
        if not is_series:
            return False
            
        # 提取原始系列名
        old_series_name = dir_name[len(prefix_used):]
        # 使用新标准处理系列名
        new_series_name = get_series_key(old_series_name)
        
        if not new_series_name or new_series_name == old_series_name:
            return False
            
        # 创建新路径（使用标准系列标记[#s]）
        new_path = os.path.join(os.path.dirname(old_path), f'[#s]{new_series_name}')
        
        # 如果新路径已存在，检查是否为不同路径
        if os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(old_path):
            if handler:
                handler.update_panel("update_log", f"⚠️ 目标路径已存在: {new_path}")
            return False
            
        # 重命名文件夹
        os.rename(old_path, new_path)
        if handler:
            handler.update_panel("update_log", f"📁 更新系列文件夹名称: {dir_name} -> [#s]{new_series_name}")
        return True
        
    except Exception as e:
        if handler:
            handler.update_panel("update_log", f"❌ 更新系列文件夹名称失败 {old_path}: {str(e)}")
        return False

def update_all_series_folders(directory_path, handler=None):
    """更新目录下所有的系列文件夹名称"""
    try:
        updated_count = 0
        for root, dirs, _ in os.walk(directory_path):
            for dir_name in dirs:
                if dir_name.startswith('[#s]'):
                    full_path = os.path.join(root, dir_name)
                    if update_series_folder_name(full_path, handler):
                        updated_count += 1
        
        if handler and updated_count > 0:
            handler.update_panel("update_log", f"✨ 更新了 {updated_count} 个系列文件夹名称")
            
        return updated_count
        
    except Exception as e:
        if handler:
            handler.update_panel("update_log", f"❌ 更新系列文件夹失败: {str(e)}")
        return 0

def preprocess_filenames(files, handler=None):
    """预处理所有文件名"""
    file_keys = {}
    for file_path in files:
        key = get_series_key(os.path.basename(file_path))
        file_keys[file_path] = key
        if handler:
            handler.update_panel("update_log", f"🔄 预处理: {os.path.basename(file_path)} -> {key}")
    return file_keys

def get_base_filename(filename):
    """获取去除所有标签后的基本文件名"""
    # 去掉扩展名
    name = os.path.splitext(filename)[0]
    
    # 去除所有方括号及其内容
    name = re.sub(r'\[[^\]]*\]', '', name)
    # 去除所有圆括号及其内容
    name = re.sub(r'\([^)]*\)', '', name)
    # 去除所有空格和标点
    name = re.sub(r'[\s!！?？_~～]+', '', name)
    # 标准化中文（转换为简体）
    name = normalize_chinese(name)
    
    return name

def is_essentially_same_file(file1, file2):
    """检查两个文件是否本质上是同一个文件（只是标签不同）"""
    # 获取文件名（不含路径和扩展名）
    name1 = os.path.splitext(os.path.basename(file1))[0]
    name2 = os.path.splitext(os.path.basename(file2))[0]
    
    # 如果原始文件名完全相同，则认为是同一个文件
    if name1 == name2:
        return True
        
    # 去除所有标签、空格和标点
    base1 = re.sub(r'\[[^\]]*\]|\([^)]*\)', '', name1)  # 去除标签
    base2 = re.sub(r'\[[^\]]*\]|\([^)]*\)', '', name2)  # 去除标签
    
    # 去除所有空格和标点
    base1 = re.sub(r'[\s]+', '', base1).lower()
    base2 = re.sub(r'[\s]+', '', base2).lower()
    
    # 标准化中文（转换为简体）
    base1 = normalize_chinese(base1)
    base2 = normalize_chinese(base2)
    
    # 完全相同的基础名称才认为是同一个文件
    return base1 == base2

def find_similar_files(current_file, files, file_keys, processed_files, handler=None):
    """查找与当前文件相似的文件"""
    current_key = file_keys[current_file]
    similar_files = [current_file]
    to_process = set()  # 创建临时集合存储要处理的文件
    
    if not current_key.strip():
        return similar_files, to_process
    
    for other_file in files:
        if other_file in processed_files or other_file == current_file:
            continue
            
        if is_in_series_folder(other_file):
            continue
            
        if is_essentially_same_file(current_file, other_file):
            to_process.add(other_file)  # 添加到临时集合
            continue
            
        other_key = file_keys[other_file]
        if not other_key.strip():
            continue
            
        ratio = fuzz.ratio(current_key.lower(), other_key.lower())
        partial = fuzz.partial_ratio(current_key.lower(), other_key.lower())
        token = fuzz.token_sort_ratio(current_key.lower(), other_key.lower())
        
        len_diff = abs(len(current_key) - len(other_key)) / max(len(current_key), len(other_key))
        
        is_similar = (
            ratio >= SIMILARITY_CONFIG['RATIO_THRESHOLD'] and
            partial >= SIMILARITY_CONFIG['PARTIAL_THRESHOLD'] and
            token >= SIMILARITY_CONFIG['TOKEN_THRESHOLD'] and
            len_diff <= SIMILARITY_CONFIG['LENGTH_DIFF_MAX']
        )
        
        if is_similar:
            if handler:
                handler.update_panel("update_log", f"✨ 发现相似文件: {os.path.basename(other_file)} (相似度: {max(ratio, partial, token)}%)")
            similar_files.append(other_file)
            to_process.add(other_file)  # 添加到临时集合
            
    return similar_files, to_process

def extract_keywords(filename):
    """从文件名中提取关键词"""
    # 去掉扩展名和方括号内容
    name = get_base_filename(filename)
    
    # 使用多种分隔符分割文件名
    separators = r'[\s]+'
    keywords = []
    
    # 分割前先去除其他方括号和圆括号的内容
    name = re.sub(r'\[[^\]]*\]|\([^)]*\)', ' ', name)
    
    # 分割并过滤空字符串
    parts = [p.strip() for p in re.split(separators, name) if p.strip()]
    
    # 对于每个部分，如果长度大于1，则添加到关键词列表
    for part in parts:
        if len(part) > 1:  # 忽略单个字符
            keywords.append(part)
    
    return keywords

def find_keyword_based_groups(remaining_files, file_keys, processed_files, handler=None):
    """基于关键词查找系列组"""
    keyword_groups = defaultdict(list)
    file_keywords = {}
    to_process = set()  # 创建临时集合存储要处理的文件
    
    # 预处理文件关键词
    for file_path in remaining_files:
        if file_path in processed_files:
            continue
        keywords = extract_keywords(os.path.basename(file_path))
        if len(keywords) >= 1:
            file_keywords[file_path] = keywords
            # if handler:
                # handler.add_status_log(f"🔍 提取关键词: {os.path.basename(file_path)} -> {', '.join(keywords)}")
    
    def process_file_keywords(args):
        file_path, keywords = args
        if file_path in processed_files:
            return None
            
        current_group = [file_path]
        group_keywords = set(keywords)
        current_to_process = set()  # 当前处理的文件集合
        
        for other_path, other_keywords in file_keywords.items():
            if other_path == file_path or other_path in processed_files:
                continue
                
            common_keywords = set(keywords) & set(other_keywords)
            if common_keywords and any(len(k) > 1 for k in common_keywords):
                current_group.append(other_path)
                current_to_process.add(other_path)  # 添加到临时集合
                group_keywords &= set(other_keywords)
        
        if len(current_group) > 1:
            series_name = max(group_keywords, key=len) if group_keywords else max(keywords, key=len)
            return (series_name, current_group, current_to_process)
        return None
    
    # 使用线程池处理关键词匹配
    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(process_file_keywords, file_keywords.items()))
    
    for result in results:
        if result:
            series_name, group, current_to_process = result
            if handler:
                handler.update_panel("update_log", f"📚 发现系列: {series_name} ({len(group)}个文件)")
                for file_path in group:
                    handler.update_panel("update_log", f"  └─ {os.path.basename(file_path)}")
            keyword_groups[series_name] = group
            to_process.update(current_to_process)  # 更新总的处理集合
            to_process.add(group[0])
    
    return keyword_groups, to_process

def preprocess_filename(filename):
    """预处理文件名"""
    # 获取文件名（不含路径）
    name = os.path.basename(filename)
    # 去除扩展名
    name = name.rsplit('.', 1)[0]
    
    # 检查是否有系列标记前缀，如果有则去除
    for prefix in SERIES_PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
            
    # 去除方括号内容
    name = re.sub(r'\[.*?\]', '', name)
    # 去除圆括号内容
    name = re.sub(r'\(.*?\)', '', name)
    # 去除多余空格
    name = ' '.join(name.split())
    return name

def get_keywords(name):
    """将文件名分割为关键词列表"""
    return name.strip().split()

def find_longest_common_keywords(keywords1, keywords2):
    """找出两个关键词列表中最长的连续公共部分"""
    matcher = difflib.SequenceMatcher(None, keywords1, keywords2)
    match = matcher.find_longest_match(0, len(keywords1), 0, len(keywords2))
    return keywords1[match.a:match.a + match.size]

def validate_series_name(name):
    """验证和清理系列名称
    
    Args:
        name: 原始系列名称
        
    Returns:
        清理后的有效系列名称，如果无效则返回None
    """
    if not name or len(name) <= 1:
        return None
        
    # 标准化中文（转换为简体）
    name = normalize_chinese(name)
    
    # 去除末尾的特殊字符、数字和单字
    name = re.sub(r'[\s.．。·・+＋\-－—_＿\d]+$', '', name)  # 去除末尾的特殊符号和数字
    name = re.sub(r'[第章话集卷期篇季部册上中下前后完全][篇话集卷期章节部册全]*$', '', name)  # 去除末尾特殊词
    name = re.sub(r'(?i)vol\.?\s*\d*$', '', name)  # 去除末尾的vol.xxx
    name = re.sub(r'(?i)volume\s*\d*$', '', name)  # 去除末尾的volume xxx
    name = re.sub(r'(?i)part\s*\d*$', '', name)  # 去除末尾的part xxx
    name = name.strip()
    
    # 检查是否包含comic关键词
    if re.search(r'(?i)comic', name):
        return None
    
    # 检查是否只包含3个或更少的单字母
    words = name.split()
    if all(len(word) <= 1 for word in words) and len(''.join(words)) <= 3:
        return None
    
    # 最终检查：结果必须长度大于1且不能以单字结尾
    if not name or len(name) <= 1 or (len(name) > 0 and len(name.split()[-1]) <= 1):
        return None
        
    return name

def find_series_groups(filenames, handler=None):
    """查找属于同一系列的文件组，使用三阶段匹配策略"""
    # 预处理所有文件名
    processed_names = {f: preprocess_filename(f) for f in filenames}
    processed_keywords = {f: get_keywords(processed_names[f]) for f in filenames}
    # 为比较创建简体版本
    simplified_names = {f: normalize_chinese(n) for f, n in processed_names.items()}
    simplified_keywords = {f: [normalize_chinese(k) for k in kws] for f, kws in processed_keywords.items()}
    
    # 存储系列分组
    series_groups = defaultdict(list)
    # 待处理的文件集合
    remaining_files = set(filenames)
    # 记录已匹配的文件
    matched_files = set()
    
    # 预处理阶段：检查已标记的系列
    if handler:
        handler.update_panel("series_extract", "🔍 预处理阶段：检查已标记的系列")
    
    for file_path in list(remaining_files):
        if file_path in matched_files:
            continue
            
        file_name = os.path.basename(file_path)
        for prefix in SERIES_PREFIXES:
            if file_name.startswith(prefix):
                # 提取系列名
                series_name = file_name[len(prefix):]
                # 去除可能的其他标记
                series_name = re.sub(r'\[.*?\]|\(.*?\)', '', series_name)
                series_name = series_name.strip()
                if series_name:
                    series_groups[series_name].append(file_path)
                    matched_files.add(file_path)
                    remaining_files.remove(file_path)
                    if handler:
                        handler.update_panel("series_extract", f"✨ 预处理阶段：文件 '{os.path.basename(file_path)}' 已标记为系列 '{series_name}'")
                break
    
    # 第一阶段：风格匹配（关键词匹配）
    if handler:
        handler.update_panel("series_extract", "🔍 第一阶段：风格匹配（关键词匹配）")
    
    while remaining_files:
        best_length = 0
        best_common = None
        best_pair = None
        best_series_name = None
        
        for file1 in remaining_files:
            if file1 in matched_files:
                continue
                
            keywords1 = simplified_keywords[file1]  # 使用简体版本比较
            base_name1 = get_base_filename(os.path.basename(file1))  # 获取基础名
            
            for file2 in remaining_files - {file1}:
                if file2 in matched_files:
                    continue
                    
                # 检查基础名是否完全相同
                base_name2 = get_base_filename(os.path.basename(file2))
                if base_name1 == base_name2:
                    handler.update_panel("series_extract", f"✨ 第一阶段：文件 '{os.path.basename(file1)}' 和 '{os.path.basename(file2)}' 基础名完全相同，跳过")
                    continue  # 如果基础名完全相同,跳过这对文件
                    
                keywords2 = simplified_keywords[file2]  # 使用简体版本比较
                common = find_longest_common_keywords(keywords1, keywords2)
                # 使用原始关键词获取系列名
                if common:
                    original_kw1 = processed_keywords[file1]
                    original_common = original_kw1[keywords1.index(common[0]):keywords1.index(common[-1])+1]
                    series_name = validate_series_name(' '.join(original_common))
                    if series_name and len(common) > best_length:
                        best_length = len(common)
                        best_common = common
                        best_pair = (file1, file2)
                        best_series_name = series_name
        
        if best_pair and best_series_name:
            matched_files_this_round = set(best_pair)
            base_name1 = get_base_filename(os.path.basename(best_pair[0]))
            
            for other_file in remaining_files - matched_files_this_round - matched_files:
                # 检查基础名是否与第一个文件相同
                other_base_name = get_base_filename(os.path.basename(other_file))
                if base_name1 == other_base_name:
                    continue  # 如果基础名相同,跳过这个文件
                    
                other_keywords = simplified_keywords[other_file]  # 使用简体版本比较
                common = find_longest_common_keywords(simplified_keywords[best_pair[0]], other_keywords)
                if common == best_common:
                    matched_files_this_round.add(other_file)
            
            # 使用最佳系列名
            series_groups[best_series_name].extend(matched_files_this_round)
            remaining_files -= matched_files_this_round
            matched_files.update(matched_files_this_round)
            
            if handler:
                handler.update_panel("series_extract", f"✨ 第一阶段：通过关键词匹配找到系列 '{best_series_name}'")
                for file_path in matched_files_this_round:
                    handler.update_panel("series_extract", f"  └─ 文件 '{os.path.basename(file_path)}' 匹配到系列（关键词：{' '.join(best_common)}）")
        else:
            break  # 没有找到匹配，进入第二阶段
    
    # 第二阶段：完全基础名匹配
    if remaining_files:
        if handler:
            handler.update_panel("series_extract", "🔍 第二阶段：完全基础名匹配")
        
        # 获取所有已存在的系列名
        existing_series = list(series_groups.keys())
        
        # 从目录中获取已有的系列文件夹名称
        dir_path = os.path.dirname(list(remaining_files)[0])  # 获取第一个文件的目录路径
        try:
            for folder_name in os.listdir(dir_path):
                if os.path.isdir(os.path.join(dir_path, folder_name)):
                    # 检查是否有系列标记
                    for prefix in SERIES_PREFIXES:
                        if folder_name.startswith(prefix):
                            series_name = folder_name[len(prefix):]  # 去掉前缀
                            if series_name not in existing_series:
                                existing_series.append(series_name)
                                if handler:
                                    handler.update_panel("series_extract", f"📁 第二阶段：从目录中找到已有系列 '{series_name}'")
                            break
        except Exception:
            pass  # 如果读取目录失败，仅使用已有的系列名
        
        # 检查剩余文件是否包含已有系列名
        matched_files_by_series = defaultdict(list)
        for file in list(remaining_files):
            if file in matched_files:
                continue
                
            base_name = simplified_names[file]  # 使用简体版本比较
            base_name_no_space = re.sub(r'\s+', '', base_name)
            for series_name in existing_series:
                series_base = normalize_chinese(series_name)  # 只在比较时转换为简体
                series_base_no_space = re.sub(r'\s+', '', series_base)
                # 只要文件名中包含系列名就匹配
                if series_base_no_space in base_name_no_space:
                    # 检查是否有基础名相同的文件已经在这个系列中
                    base_name_current = get_base_filename(os.path.basename(file))
                    has_same_base = False
                    for existing_file in matched_files_by_series[series_name]:
                        if get_base_filename(os.path.basename(existing_file)) == base_name_current:
                            has_same_base = True
                            break
                    
                    if not has_same_base:
                        matched_files_by_series[series_name].append(file)  # 使用原始系列名
                        matched_files.add(file)
                        remaining_files.remove(file)
                        if handler:
                            handler.update_panel("series_extract", f"✨ 第二阶段：文件 '{os.path.basename(file)}' 匹配到已有系列 '{series_name}'（包含系列名）")
                    break
        
        # 将匹配的文件添加到对应的系列组
        for series_name, files in matched_files_by_series.items():
            series_groups[series_name].extend(files)
            if handler:
                handler.update_panel("series_extract", f"✨ 第二阶段：将 {len(files)} 个文件添加到系列 '{series_name}'")
                for file_path in files:
                    handler.update_panel("series_extract", f"  └─ {os.path.basename(file_path)}")
    
    # 第三阶段：最长公共子串匹配
    if remaining_files:
        if handler:
            handler.update_panel("series_extract", "🔍 第三阶段：最长公共子串匹配")
            
        while remaining_files:
            best_ratio = 0
            best_pair = None
            best_common = None
            original_form = None  # 保存原始大小写形式
            
            # 对剩余文件进行两两比较
            for file1 in remaining_files:
                if file1 in matched_files:
                    continue
                    
                base1 = simplified_names[file1]  # 使用简体版本比较
                base1_lower = base1.lower()
                original1 = processed_names[file1]  # 保存原始形式
                base_name1 = get_base_filename(os.path.basename(file1))
                
                for file2 in remaining_files - {file1}:
                    if file2 in matched_files:
                        continue
                        
                    # 检查基础名是否完全相同
                    base_name2 = get_base_filename(os.path.basename(file2))
                    if base_name1 == base_name2:
                        continue  # 如果基础名完全相同,跳过这对文件
                        
                    base2 = simplified_names[file2]  # 使用简体版本比较
                    base2_lower = base2.lower()
                    
                    # 使用小写形式进行比较
                    matcher = difflib.SequenceMatcher(None, base1_lower, base2_lower)
                    ratio = matcher.ratio()
                    if ratio > best_ratio and ratio > 0.6:
                        best_ratio = ratio
                        best_pair = (file1, file2)
                        match = matcher.find_longest_match(0, len(base1_lower), 0, len(base2_lower))
                        best_common = base1_lower[match.a:match.a + match.size]
                        # 保存原始形式
                        original_form = original1[match.a:match.a + match.size]
            
            if best_pair and best_common and len(best_common.strip()) > 1:
                matched_files_this_round = set(best_pair)
                base_name1 = get_base_filename(os.path.basename(best_pair[0]))
                
                for other_file in remaining_files - matched_files_this_round - matched_files:
                    # 检查基础名是否与第一个文件相同
                    other_base_name = get_base_filename(os.path.basename(other_file))
                    if base_name1 == other_base_name:
                        continue  # 如果基础名相同,跳过这个文件
                        
                    other_base = simplified_names[other_file].lower()  # 使用简体小写版本比较
                    if best_common in other_base:
                        matched_files_this_round.add(other_file)
                
                # 使用原始形式作为系列名
                series_name = validate_series_name(original_form)
                if series_name:
                    series_groups[series_name].extend(matched_files_this_round)
                    remaining_files -= matched_files_this_round
                    matched_files.update(matched_files_this_round)
                    if handler:
                        handler.update_panel("series_extract", f"✨ 第三阶段：通过公共子串匹配找到系列 '{series_name}'")
                        handler.update_panel("series_extract", f"  └─ 公共子串：'{best_common}' (相似度: {best_ratio:.2%})")
                        for file_path in matched_files_this_round:
                            handler.update_panel("series_extract", f"  └─ 文件 '{os.path.basename(file_path)}'")
                else:
                    remaining_files.remove(best_pair[0])
                    matched_files.add(best_pair[0])
            else:
                break
    
    if handler and remaining_files:
        handler.update_panel("series_extract", f"⚠️ 还有 {len(remaining_files)} 个文件未能匹配到任何系列")
        # for file_path in remaining_files:
        #     handler.update_panel("series_extract", f"  └─ {os.path.basename(file_path)}")
    
    return dict(series_groups)

def create_series_folders(directory_path, archives, handler=None):
    """为同一系列的文件创建文件夹"""
    dir_groups = defaultdict(list)
    # 只处理压缩包文件
    archives = [f for f in archives if os.path.isfile(f) and is_archive(f)]
    
    for archive in archives:
        dir_path = os.path.dirname(archive)
        # 检查父目录是否有系列标记
        parent_name = os.path.basename(dir_path)
        is_series_dir = any(parent_name.startswith(prefix) for prefix in SERIES_PREFIXES)
        if is_series_dir:
            continue
        dir_groups[dir_path].append(archive)
    
    for dir_path, dir_archives in dir_groups.items():
        if len(dir_archives) <= 1:
            continue
            
        if handler:
            # 更新处理状态
            handler.process_log_lines.clear()
            handler.process_log_lines.append(f"分析目录: {os.path.basename(dir_path)}")
            handler.update_panel("update_log", f"找到 {len(dir_archives)} 个压缩包")
        
        series_groups = find_series_groups(dir_archives, handler)
        
        if series_groups:
            if handler:
                handler.update_panel("update_log", f"📚 找到 {len(series_groups)} 个系列")
            
            # 检查是否所有文件都会被移动到同一个系列
            total_files = len(dir_archives)
            for series_name, files in series_groups.items():
                if series_name == "其他":
                    continue
                if len(files) == total_files:
                    if handler:
                        handler.update_panel("update_log", f"⚠️ 所有文件都属于同一个系列，跳过创建子文件夹")
                    return
            
            # 创建一个字典来记录每个系列的文件夹路径
            series_folders = {}
            
            # 首先创建所有需要的系列文件夹
            for series_name, files in series_groups.items():
                # 跳过"其他"分类和只有一个文件的系列
                if series_name == "其他" or len(files) <= 1:
                    if handler:
                        if series_name == "其他":
                            handler.update_panel("update_log", f"⚠️ {len(files)} 个文件未能匹配到系列")
                        else:
                            handler.update_panel("update_log", f"⚠️ 系列 '{series_name}' 只有一个文件，跳过创建文件夹")
                    continue
                
                # 添加系列标记（使用标准系列标记[#s]）
                series_folder = os.path.join(dir_path, f'[#s]{series_name.strip()}')
                if not os.path.exists(series_folder):
                    os.makedirs(series_folder)
                    if handler:
                        handler.update_panel("update_log", f"📁 创建系列文件夹: [#s]{series_name}")
                series_folders[series_name] = series_folder
            
            # 然后移动每个系列的文件
            for series_name, folder_path in series_folders.items():
                files = series_groups[series_name]
                if handler:
                    handler.update_panel("update_log", f"📦 开始移动系列 '{series_name}' 的文件...")
                
                for file_path in files:
                    # 更新处理状态
                    if handler:
                        handler.process_log_lines.clear()
                        handler.process_log_lines.append(f"移动: {os.path.basename(file_path)}")
                    
                    target_path = os.path.join(folder_path, os.path.basename(file_path))
                    if not os.path.exists(target_path):
                        shutil.move(file_path, target_path)
                        if handler:
                            handler.update_panel("update_log", f"  └─ 移动: {os.path.basename(file_path)}")
                    else:
                        if handler:
                            handler.update_panel("update_log", f"⚠️ 文件已存在于系列 '{series_name}': {os.path.basename(file_path)}")
            
            if handler:
                handler.update_panel("current_task", "系列提取完成")
        
        if handler:
            handler.update_panel("folder_process", f"✨ 目录处理完成: {dir_path}")

# 新增的辅助函数
def validate_directory(directory_path, handler=None):
    """验证目录是否有效且不在黑名单中"""
    abs_dir_path = os.path.abspath(directory_path)
    if not os.path.isdir(abs_dir_path):
        if handler:
            handler.update_panel("update_log", f"❌ 不是有效的目录路径: {abs_dir_path}")
        return None
    
    if is_path_blacklisted(abs_dir_path):
        if handler:
            handler.update_panel("update_log", f"⚠️ 目录在黑名单中，跳过处理: {abs_dir_path}")
        return None
        
    return abs_dir_path

def collect_archives_for_category(directory_path, category_folders, handler=None):
    """收集用于分类的压缩包"""
    archives = []
    archives_to_check = []
    
    with os.scandir(directory_path) as entries:
        for entry in entries:
            if entry.is_file() and is_archive(entry.name):
                parent_dir = os.path.basename(os.path.dirname(entry.path))
                # 跳过损坏压缩包文件夹和分类文件夹中的文件
                if parent_dir == "损坏压缩包" or parent_dir in category_folders:
                    continue
                archives_to_check.append(entry.path)
    
    if archives_to_check:
        if handler:
            handler.update_panel("update_log", f"🔍 正在检查 {len(archives_to_check)} 个压缩包的完整性...")
        
        # 使用线程池检查压缩包
        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = {executor.submit(is_archive_corrupted, path): path for path in archives_to_check}
            for i, future in enumerate(futures, 1):
                path = futures[future]
                if handler:
                    # 更新当前任务状态
                    percentage = i / len(archives_to_check) * 100
                    handler.update_panel("current_task", f"检测压缩包完整性... ({i}/{len(archives_to_check)}) {percentage:.1f}%")
                try:
                    is_corrupted = future.result()
                    if not is_corrupted:
                        archives.append(path)
                    elif handler:
                        handler.update_panel("update_log", f"⚠️ 压缩包已损坏，跳过: {os.path.basename(path)}")
                except TimeoutError:
                    if handler:
                        handler.update_panel("update_log", f"⚠️ 压缩包处理超时，跳过: {os.path.basename(path)}")
                except Exception as e:
                    if handler:
                        handler.update_panel("update_log", f"❌ 检查压缩包时出错: {os.path.basename(path)}")
    
    return archives

def collect_archives_for_series(directory_path, category_folders, handler=None):
    """收集用于系列提取的压缩包"""
    base_level = len(Path(directory_path).parts)
    archives = []
    archives_to_check = []
    
    for root, _, files in os.walk(directory_path):
        current_level = len(Path(root).parts)
        if current_level - base_level > 1:
            continue
            
        if is_path_blacklisted(root):
            if handler:
                handler.update_panel("update_log", f"⚠️ 目录在黑名单中，跳过: {root}")
            continue
            
        # 检查当前目录是否有系列标记或是损坏压缩包文件夹
        current_dir = os.path.basename(root)
        if current_dir.startswith('[#s]') or current_dir == "损坏压缩包":
            continue
            
        for file in files:
            if is_archive(file):
                file_path = os.path.join(root, file)
                # 检查文件名是否在系列提取黑名单中
                if is_series_blacklisted(file):
                    if handler:
                        handler.update_panel("update_log", f"⚠️ 文件在系列提取黑名单中，跳过: {file}")
                    continue
                if is_path_blacklisted(file):
                    if handler:
                        handler.update_panel("update_log", f"⚠️ 文件在黑名单中，跳过: {file}")
                    continue
                archives_to_check.append(file_path)
    
    if archives_to_check:
        if handler:
            handler.update_panel("update_log", f"🔍 正在检查 {len(archives_to_check)} 个压缩包的完整性...")
        
        # 使用线程池检查压缩包
        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = {executor.submit(is_archive_corrupted, path): path for path in archives_to_check}
            for i, future in enumerate(futures, 1):
                path = futures[future]
                if handler:
                    # 更新当前任务状态
                    percentage = i / len(archives_to_check) * 100
                    handler.update_panel("current_task", f"检测压缩包完整性... ({i}/{len(archives_to_check)}) {percentage:.1f}%")
                try:
                    is_corrupted = future.result()
                    if is_corrupted:
                        if handler:
                            handler.update_panel("update_log", f"⚠️ 压缩包已损坏: {os.path.basename(path)}")
                        # 移动损坏的压缩包
                        move_corrupted_archive(path, directory_path, handler)
                    else:
                        archives.append(path)
                except TimeoutError:
                    if handler:
                        handler.update_panel("update_log", f"⚠️ 压缩包处理超时: {os.path.basename(path)}")
                    # 将超时的压缩包也视为损坏
                    move_corrupted_archive(path, directory_path, handler)
                except Exception as e:
                    if handler:
                        handler.update_panel("update_log", f"❌ 检查压缩包时出错: {os.path.basename(path)}")
                    # 将出错的压缩包也视为损坏
                    move_corrupted_archive(path, directory_path, handler)
                    
    return archives

def run_post_processing(directory_path, enabled_features, handler=None):
    """运行后续处理脚本（删除空文件夹和序号修复）"""
    if 3 in enabled_features:
        try:
            handler.update_panel("post_process", "🗑️ 正在删除空文件夹...")
            # 运行子进程
            result = subprocess.run(
                f'python "D:\\1VSCODE\\1ehv\\archive\\013-删除空文件夹释放单独文件夹.py" "{directory_path}" -r', 
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, result.args)
            
            handler.update_panel("post_process", "✅ 空文件夹处理完成")
                
        except subprocess.CalledProcessError as e:
            if handler:
                handler.update_panel("update_log", f"❌ 运行删除空文件夹脚本失败: {str(e)}")
                handler.update_panel("post_process", "❌ 空文件夹处理失败")
    
    if 4 in enabled_features:
        try:
            handler.update_panel("post_process", "🔧 正在修复序号...")
            # 运行子进程
            result = subprocess.run(
                f'python "D:\\1VSCODE\\1ehv\\other\\012-文件夹序号修复工具.py" "{directory_path}"', 
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, result.args)
            
            handler.update_panel("post_process", "✅ 序号修复完成")
                
        except subprocess.CalledProcessError as e:
            if handler:
                handler.update_panel("update_log", f"❌ 运行序号修复脚本失败: {str(e)}")
                handler.update_panel("post_process", "❌ 序号修复失败")

def process_directory(directory_path, progress_task=None, enabled_features=None, handler=None):
    """处理目录下的压缩包"""
    try:
        if enabled_features is None:
            enabled_features = {1, 2, 3, 4}
            
        # 验证目录
        abs_dir_path = validate_directory(directory_path)
        if not abs_dir_path:
            return []

        # 如果没有传入 handler，创建一个新的
        handler_created = False
        if handler is None:
            handler = get_handler()
            handler_created = True

        try:
            # 更新文件夹处理状态
            handler.update_panel("folder_process", f"📂 开始处理目录: {abs_dir_path}")
            
            # 更新旧的系列文件夹名称
            if 2 in enabled_features:
                handler.update_panel("folder_process", "🔄 检查并更新旧的系列文件夹名称...")
                update_all_series_folders(abs_dir_path, handler)
            
            # 创建分类文件夹（功能1）
            if 1 in enabled_features:
                create_category_folders(abs_dir_path)
            
            category_folders = set(CATEGORY_RULES.keys())
            found_archives = False
            
            # 功能2（系列提取）
            if 2 in enabled_features:
                handler.update_panel("folder_process", "🔍 开始查找可提取系列的压缩包...")
                archives = collect_archives_for_series(abs_dir_path, category_folders, handler)
                if archives:
                    found_archives = True
                    total_archives = len(archives)
                    handler.set_total(total_archives)
                    handler.update_panel("update_log", f"✨ 在目录 '{abs_dir_path}' 及其子文件夹下找到 {total_archives} 个有效压缩包")
                    
                    # 直接处理所有压缩包
                    create_series_folders(abs_dir_path, archives, handler)
                    
                    # 更新进度
                    handler.update_panel("current_task", "系列提取完成")
                else:
                    handler.update_panel("folder_process", "没有找到可提取系列的压缩包")
            
            # 功能1（分类）
            if 1 in enabled_features:
                handler.update_panel("folder_process", "🔍 开始查找需要分类的压缩包...")
                archives = collect_archives_for_category(abs_dir_path, category_folders, handler)
                if archives:
                    found_archives = True
                    total_archives = len(archives)
                    handler.set_total(total_archives)
                    handler.update_panel("update_log", f"✨ 在目录 '{abs_dir_path}' 下找到 {total_archives} 个有效压缩包")
                    
                    # 构建进度条
                    for i, archive in enumerate(archives, 1):
                        percentage = i / total_archives * 100
                        bar_width = 50
                        completed_width = int(bar_width * percentage / 100)
                        progress_bar = f"[{'=' * completed_width}{' ' * (bar_width - completed_width)}]"
                        progress_text = f"正在分类压缩包... {progress_bar} {percentage:.1f}% ({i}/{total_archives})"
                        handler.update_panel("current_task", progress_text)
                        
                        # 更新处理状态
                        handler.update_panel("archive_process", f"处理: {os.path.basename(archive)}")
                        process_single_file(archive, handler)
                else:
                    handler.update_panel("folder_process", "没有找到需要分类的压缩包")
            
            # 运行后续处理
            if 3 in enabled_features or 4 in enabled_features:
                handler.update_panel("post_process", "🔧 开始运行后续处理...")
                # run_post_processing(abs_dir_path, enabled_features, handler)
            
            if not found_archives:
                handler.update_panel("folder_process", f"在目录 '{abs_dir_path}' 下没有找到需要处理的压缩包")
            
            handler.update_panel("folder_process", f"✨ 目录处理完成: {abs_dir_path}")
            
        finally:
            # 如果是我们创建的 handler，需要关闭它
            if handler_created:
                close_handler()
        
        return []
            
    except Exception as e:
        if handler:
            handler.update_panel("update_log", f"❌ 处理目录时出错 {directory_path}: {str(e)}")
            handler.update_panel("folder_process", f"❌ 处理出错: {os.path.basename(directory_path)}")
        return []

def process_paths(paths, enabled_features=None, similarity_config=None, wait_for_confirm=False):
    """处理输入的路径列表"""
    if similarity_config:
        SIMILARITY_CONFIG.update(similarity_config)
        
    valid_paths = []
    for path in paths:
        path = path.strip().strip('"').strip("'")
        if path:
            try:
                if sys.platform == 'win32':
                    if win32_path_exists(path):
                        valid_paths.append(path)
                    else:
                        print(f"❌ 路径不存在或无法访问: {path}")
                else:
                    if os.path.exists(path):
                        valid_paths.append(path)
                    else:
                        print(f"❌ 路径不存在: {path}")
            except Exception as e:
                print(f"❌ 处理路径时出错: {path}, 错误: {str(e)}")
    
    if not valid_paths:
        print("❌ 没有有效的路径")
        return
    
    total_paths = len(valid_paths)
    print(f"\n🚀 开始{'处理' if wait_for_confirm else '批量处理'} {total_paths} 个路径...")
    if not wait_for_confirm:
        print("路径列表:")
        for path in valid_paths:
            print(f"  - {path}")
        print()
    
    # 只有在开始实际处理时才创建 handler
    with get_handler() as handler:
        for i, path in enumerate(valid_paths, 1):
            try:
                if wait_for_confirm:
                    handler.update_panel("current_task", f"📍 处理第 {i}/{total_paths} 个路径: {path}")
                else:
                    handler.update_panel("current_task", f"处理: {os.path.basename(path)}")
                    
                if sys.platform == 'win32':
                    if win32_path_exists(path):
                        if os.path.isdir(path):
                            process_directory(path, enabled_features=enabled_features, handler=handler)
                        elif os.path.isfile(path) and is_archive(path):
                            if 1 in enabled_features:
                                if wait_for_confirm:
                                    handler.update_panel("current_task", f"📦 处理单个文件: {path}")
                                process_single_file(path, handler)
                                if wait_for_confirm:
                                    handler.update_panel("update_log", "✨ 文件处理完成")
                else:
                    if os.path.isdir(path):
                        process_directory(path, enabled_features=enabled_features, handler=handler)
                    elif os.path.isfile(path) and is_archive(path):
                        if 1 in enabled_features:
                            if wait_for_confirm:
                                handler.update_panel("current_task", f"📦 处理单个文件: {path}")
                            process_single_file(path, handler)
                            if wait_for_confirm:
                                handler.update_panel("update_log", "✨ 文件处理完成")
                
                if wait_for_confirm and i < total_paths:
                    handler.update_panel("current_task", f"⏸️ 已处理完第 {i}/{total_paths} 个路径")
                    input("按回车键继续处理下一个路径...")
                    
            except Exception as e:
                handler.update_panel("update_log", f"❌ 处理路径时出错: {path}, 错误: {str(e)}")
                if wait_for_confirm and i < total_paths:
                    handler.update_panel("update_log", f"⚠️ 处理出错，是否继续？")
                    input("按回车键继续处理下一个路径，按 Ctrl+C 终止程序...")
        
        if wait_for_confirm:
            handler.update_panel("update_log", "✅ 所有路径处理完成！")
        else:
            handler.update_panel("update_log", f"✅ 批量处理完成！共处理 {total_paths} 个路径")

def process_args():
    """处理命令行参数"""
    parser = argparse.ArgumentParser(description='漫画压缩包分类工具')
    parser.add_argument('paths', nargs='*', help='要处理的路径列表')
    parser.add_argument('-c', '--clipboard', action='store_true', help='从剪贴板读取路径')
    parser.add_argument('-f', '--features', type=str, default='',
                      help='启用的功能（1-4，用逗号分隔）：1=分类，2=系列提取，3=删除空文件夹，4=序号修复。默认全部启用')
    parser.add_argument('--similarity', type=float, default=80,
                      help='设置基本相似度阈值(0-100)，默认80')
    parser.add_argument('--ratio', type=float, default=75,
                      help='设置完全匹配阈值(0-100)，默认75')
    parser.add_argument('--partial', type=float, default=85,
                      help='设置部分匹配阈值(0-100)，默认85')
    parser.add_argument('--token', type=float, default=80,
                      help='设置标记匹配阈值(0-100)，默认80')
    parser.add_argument('--length-diff', type=float, default=0.3,
                      help='设置长度差异最大值(0-1)，默认0.3')
    parser.add_argument('--wait', action='store_true', help='处理完每个路径后等待用户确认')

    # 如果没有参数或只有-c参数，使用TUI
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ['-c', '--clipboard']):
        # 预设配置
        presets = {
            "默认配置": {
                "features": "1,2,3,4",
                "similarity": "80",
                "ratio": "75",
                "partial": "85",
                "token": "80",
                "length_diff": "0.3",
                "clipboard": True,
                "wait": False
            },
            "仅分类": {
                "features": "1",
                "similarity": "80",
                "ratio": "75",
                "partial": "85",
                "token": "80",
                "length_diff": "0.3",
                "clipboard": True,
                "wait": False
            },
            "仅系列提取": {
                "features": "2",
                "similarity": "80",
                "ratio": "75",
                "partial": "85",
                "token": "80",
                "length_diff": "0.3",
                "clipboard": True,
                "wait": False
            },
            "分类+系列": {
                "features": "1,2",
                "similarity": "80",
                "ratio": "75",
                "partial": "85",
                "token": "80",
                "length_diff": "0.3",
                "clipboard": True,
                "wait": False
            }
        }

        # 创建TUI配置界面
        checkbox_options = [
            ("从剪贴板读取", "clipboard", "-c", True),
            ("分类功能", "feature1", "-f 1"),
            ("系列提取", "feature2", "-f 2"),
            ("删除空文件夹", "feature3", "-f 3"),
            ("序号修复", "feature4", "-f 4"),
            ("等待确认", "wait", "--wait", False),
        ]

        input_options = [
            ("基本相似度阈值", "similarity", "--similarity", "80", "0-100"),
            ("完全匹配阈值", "ratio", "--ratio", "75", "0-100"),
            ("部分匹配阈值", "partial", "--partial", "85", "0-100"),
            ("标记匹配阈值", "token", "--token", "80", "0-100"),
            ("长度差异最大值", "length_diff", "--length-diff", "0.3", "0-1"),
        ]

        app = create_config_app(
            program=__file__,
            checkbox_options=checkbox_options,
            input_options=input_options,
            title="漫画压缩包分类工具配置",
            preset_configs=presets
        )
        app.run()
        return None, None

    args = parser.parse_args()
    
    # 如果使用了 -c 参数，从剪贴板读取路径
    if args.clipboard:
        try:
            import pyperclip
            clipboard_content = pyperclip.paste().strip()
            if clipboard_content:
                args.paths.extend([p.strip() for p in clipboard_content.replace('\r\n', '\n').split('\n') if p.strip()])
                print("从剪贴板读取到以下路径：")
                for path in args.paths:
                    print(path)
        except ImportError:
            print("未安装 pyperclip 模块，无法从剪贴板读取路径")

    return args.paths, args

def run_classifier(paths, args):
    """运行分类器主逻辑"""
    if not paths or not args:
        return

    # 更新相似度配置
    similarity_config = {
        'THRESHOLD': args.similarity,
        'RATIO_THRESHOLD': args.ratio,
        'PARTIAL_THRESHOLD': args.partial,
        'TOKEN_THRESHOLD': args.token,
        'LENGTH_DIFF_MAX': args.length_diff
    }
    SIMILARITY_CONFIG.update(similarity_config)

    # 解析启用的功能
    enabled_features = set()
    if args.features:
        try:
            enabled_features = {int(f.strip()) for f in args.features.split(',') if f.strip()}
            for f in enabled_features.copy():
                if f not in {1, 2, 3, 4}:
                    print(f"无效的功能编号: {f}")
                    enabled_features.remove(f)
        except ValueError:
            print("无效的功能编号格式，将启用所有功能")
            enabled_features = {1, 2, 3, 4}
    else:
        enabled_features = {1, 2, 3, 4}

    # 处理路径
    process_paths(paths, enabled_features=enabled_features, wait_for_confirm=args.wait)

def main():
    # 设置控制台编码为UTF-8
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleCP(65001)
            kernel32.SetConsoleOutputCP(65001)
        except:
            print("无法设置控制台编码为UTF-8")

    paths, args = process_args()
    run_classifier(paths, args)

if __name__ == "__main__":
    main()
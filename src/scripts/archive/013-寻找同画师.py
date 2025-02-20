import os
import re
import shutil
from datetime import datetime
import logging
from pathlib import Path
import argparse
import pyperclip
from collections import defaultdict
from typing import List, Set, Dict, Tuple
from colorama import init, Fore, Style
from opencc import OpenCC
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.rich_logger import RichProgressHandler
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from tui.config import create_config_app
# 初始化 colorama 和 OpenCC
init()
cc_s2t = OpenCC('s2t')  # 简体到繁体
cc_t2s = OpenCC('t2s')  # 繁体到简体

# 黑名单关键词
BLACKLIST_KEYWORDS = {
    '已找到',
    'unknown',  # 未知画师
    # 画集/图集相关
    'trash', '画集', '畫集', 'artbook', 'art book', 'art works', 'illustrations',
    '图集', '圖集', 'illust', 'collection',
    '杂图', '雜圖', '杂图合集', '雜圖合集',
    # 其他不需要处理的类型
    'pixiv', 'fanbox', 'gumroad', 'twitter',
    '待分类', '待處理', '待分類',
    '图包', '圖包',
    '图片', '圖片',
    'cg', 'CG',
    r'v\d+',  # v2, v3 等版本号
    # 常见标签
    'R18', 'COMIC', 'VOL', '汉化', '漢化', '中国翻訳',
    # 日期标记
    r'\d{4}', r'\d{2}\.\d{2}',
    # 其他通用标记
    'DL版', 'Digital', '無修正',
    # 翻译相关关键词
    '中国翻译', '中国翻訳', '中国語', '中国语',
    '中文', '中文翻译', '中文翻訳',
    '日語', '日语', '翻訳', '翻译',
    '汉化组', '漢化組', '汉化社', '漢化社',
    '汉化', '漢化', '翻译版', '翻訳版',
    '机翻', '機翻', '人工翻译', '人工翻訳',
    '中国', '中國', '日本語', '日本语'
    '汉化', '漢化',  # 汉化/漢化
    '翻译', '翻訳', '翻譯', # 翻译相关
    '中国翻译', '中国翻訳', '中国語','chinese','中文','中国', # 中文翻译
    '嵌字',  # 嵌字
    '掃圖', '掃', # 扫图相关
    '制作', '製作', # 制作相关
    '重嵌',  # 重新嵌入
    '个人', # 个人翻译
    '修正',  # 修正版本
    '去码',
    '日语社',
    '制作',
    '机翻',
    '赞助',
    '汉', '漢', # 汉字相关
    '数位', '未来数位', '新视界', # 汉化相关
    '出版', '青文出版', # 翻译相关
    '脸肿', '无毒', '空気系', '夢之行蹤', '萌幻鴿鄉', '绅士仓库', 'Lolipoi', '靴下','CE家族社',
    '不可视', '一匙咖啡豆', '无邪气', '洨五', '白杨', '瑞树',  # 常见汉化组名
    '汉化组', '漢化組', '汉化社', '漢化社', 'CE 家族社', 'CE 家族社',  # 常见后缀
    '个人汉化', '個人漢化'  # 个人汉化
}

# 添加路径黑名单关键词
PATH_BLACKLIST = {
    '[00画师分类]',  # 已经分类的画师目录
    '[00待分类]',    # 待分类目录
    '[00去图]',      # 去图目录
    '已找到',        # 杂项目录
    '[02COS]',       # COS目录
    'trash',         # 垃圾箱
    'temp',          # 临时目录
    '待处理',        # 待处理目录
    '新建文件夹'     # 临时文件夹
}

def preprocess_keywords(keywords: Set[str]) -> Set[str]:
    """预处理关键词集合，添加繁简体变体"""
    processed = set()
    for keyword in keywords:
        # 添加原始关键词（小写）
        processed.add(keyword.lower())
        # 添加繁体版本
        traditional = cc_s2t.convert(keyword)
        processed.add(traditional.lower())
        # 添加简体版本
        simplified = cc_t2s.convert(keyword)
        processed.add(simplified.lower())
    return processed

# 预处理黑名单关键词
_BLACKLIST_KEYWORDS_FULL = preprocess_keywords(BLACKLIST_KEYWORDS)

def extract_artist_info(filename: str) -> List[Tuple[str, str]]:
    """
    从文件名中提取画师信息
    返回格式: [(社团名, 画师名), ...]
    """
    # 匹配[社团名 (画师名)]格式
    pattern1 = r'\[(.*?)\s*\((.*?)\)\]'
    matches1 = re.findall(pattern1, filename)
    if matches1:
        return [(group, artist) for group, artist in matches1]
    
    # 匹配所有方括号内容
    pattern2 = r'\[(.*?)\]'
    matches2 = re.findall(pattern2, filename)
    
    # 过滤黑名单关键词和特殊模式
    filtered_matches = []
    for match in matches2:
        match_lower = match.lower()
        
        # 跳过纯数字
        if match.isdigit():
            continue
            
        # 跳过日期格式 (YYYYMMDD)
        if re.match(r'^\d{8}$', match):
            continue
            
        # 跳过日期格式 (YYYYMM)
        if re.match(r'^\d{6}$', match):
            continue
            
        # 跳过类似[013]这样的短数字
        if re.match(r'^\d{1,3}$', match):
            continue
            
        # 跳过版本号格式
        if re.match(r'^v\d+$', match.lower()):
            continue
            
        # 跳过数字字母混合的短标记
        if re.match(r'^[0-9a-zA-Z]{1,6}$', match):
            continue
            
        # 跳过黑名单关键词
        if any(keyword in match_lower for keyword in _BLACKLIST_KEYWORDS_FULL):
            continue
            
        filtered_matches.append(('', match))
            
    return filtered_matches

def find_common_artists(files: List[str], min_occurrences: int = 2) -> Dict[str, List[str]]:
    """
    找出文件列表中重复出现的画师名
    返回: {画师名: [相关文件列表]}
    """
    artist_files = defaultdict(list)
    artist_occurrences = defaultdict(int)
    
    for file in files:
        artist_infos = extract_artist_info(file)
        for group, artist in artist_infos:
            key = f"{group}_{artist}" if group else artist
            artist_files[key].append(file)
            artist_occurrences[key] += 1
    
    # 只保留出现次数达到阈值的画师
    common_artists = {
        artist: files 
        for artist, files in artist_files.items() 
        if artist_occurrences[artist] >= min_occurrences
    }
    
    return common_artists

def setup_logging():
    """配置日志处理"""
    handler = RichProgressHandler(
        layout_config={
            "stats": {"ratio": 2, "title": "📊 处理统计"},
            "process": {"ratio": 2, "title": "🔄 进度"},
            "file_ops": {"ratio": 3, "title": "📂 文件操作"},
            "artist_info": {"ratio": 3, "title": "🎨 画师信息"},
            "error_log": {"ratio": 3, "title": "⚠️ 错误日志"}
        },
        style_config={
            "border_style": "cyan",
            "title_style": "yellow bold",
            "padding": (0, 1),
            "panel_styles": {
                "stats": "green",
                "process": "cyan",
                "file_ops": "blue",
                "artist_info": "magenta",
                "error_log": "red"
            }
        }
    )
    return handler

def update_panel_log(handler: RichProgressHandler, panel: str, message: str, append: bool = True):
    """更新面板日志"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    handler.update_panel(panel, log_message, append=append)

def is_path_blacklisted(path: str) -> bool:
    """检查路径是否在黑名单中"""
    path_lower = path.lower()
    return any(keyword.lower() in path_lower for keyword in PATH_BLACKLIST)

def process_directory(directory: str, handler: RichProgressHandler, ignore_blacklist: bool = False) -> None:
    """处理单个目录"""
    # 检查目录本身是否在黑名单中
    if not ignore_blacklist and is_path_blacklisted(directory):
        update_panel_log(handler, "error_log", f"⚠️ 跳过黑名单目录: {directory}")
        return

    # 创建画师分类总目录
    artists_base_dir = os.path.join(directory, "[00画师分类]")
    try:
        os.makedirs(artists_base_dir, exist_ok=True)
    except Exception as e:
        update_panel_log(handler, "error_log", f"❌ 创建画师分类目录失败: {str(e)}")
        return

    # 收集所有压缩文件（跳过黑名单目录）
    all_files = []
    scan_task = handler.create_progress_task(total=0, description="🔍 扫描文件...")
    update_panel_log(handler, "process", "🔍 正在扫描文件...")
    
    for root, _, files in os.walk(directory):
        # 跳过黑名单目录
        if not ignore_blacklist and is_path_blacklisted(root):
            update_panel_log(handler, "file_ops", f"⏭️ 跳过目录: {os.path.basename(root)}")
            continue
            
        for file in files:
            if file.lower().endswith(('.zip', '.rar', '.7z')):
                try:
                    # 检查文件名是否包含黑名单关键词
                    if not ignore_blacklist and is_path_blacklisted(file):
                        update_panel_log(handler, "file_ops", f"⏭️ 跳过文件: {file}")
                        continue
                        
                    rel_path = os.path.relpath(os.path.join(root, file), directory)
                    all_files.append(rel_path)
                    handler.progress.update(scan_task, total=len(all_files), completed=len(all_files))
                except Exception as e:
                    update_panel_log(handler, "error_log", f"⚠️ 处理文件路径失败 {file}: {str(e)}")
                    continue
    
    if not all_files:
        update_panel_log(handler, "error_log", f"⚠️ 目录 {directory} 中未找到压缩文件")
        return
    
    # 查找共同画师
    update_panel_log(handler, "process", "🔍 正在分析画师信息...")
    artist_groups = find_common_artists(all_files)
    
    if not artist_groups:
        update_panel_log(handler, "error_log", "⚠️ 未找到重复出现的画师")
        return
    
    # 创建画师目录并移动文件
    for artist_key, files in artist_groups.items():
        try:
            group, artist = artist_key.split('_') if '_' in artist_key else ('', artist_key)
            artist_name = f"[{group} ({artist})]" if group else f"[{artist}]"
            artist_dir = os.path.join(artists_base_dir, artist_name)
            
            update_panel_log(handler, "artist_info", f"🎨 处理画师: {artist_name}")
            update_panel_log(handler, "stats", f"📊 找到 {len(files)} 个相关文件")
            
            # 创建画师目录
            try:
                os.makedirs(artist_dir, exist_ok=True)
            except Exception as e:
                update_panel_log(handler, "error_log", f"❌ 创建画师目录失败 {artist_name}: {str(e)}")
                continue
            
            # 移动文件
            success_count = 0
            error_count = 0
            for file in files:
                try:
                    src_path = os.path.join(directory, file)
                    if not os.path.exists(src_path):
                        update_panel_log(handler, "error_log", f"⚠️ 源文件不存在: {file}")
                        error_count += 1
                        continue
                        
                    dst_path = os.path.join(artist_dir, os.path.basename(file))
                    if os.path.exists(dst_path):
                        update_panel_log(handler, "error_log", f"⚠️ 目标文件已存在: {os.path.basename(dst_path)}")
                        error_count += 1
                        continue
                    
                    shutil.move(src_path, dst_path)
                    success_count += 1
                    update_panel_log(handler, "file_ops", f"✅ 已移动: {file} -> [00画师分类]/{artist_name}/")
                    
                except Exception as e:
                    error_count += 1
                    update_panel_log(handler, "error_log", f"⚠️ 移动失败 {os.path.basename(file)}: {str(e)}")
                    continue
            
            # 显示处理结果统计
            if success_count > 0 or error_count > 0:
                status = []
                if success_count > 0:
                    status.append(f"✅ 成功: {success_count}")
                if error_count > 0:
                    status.append(f"⚠️ 失败: {error_count}")
                update_panel_log(handler, "stats", f"📊 {artist_name} 处理完成 - " + ", ".join(status))
                
        except Exception as e:
            update_panel_log(handler, "error_log", f"⚠️ 处理画师 {artist_key} 时出错: {str(e)}")
            continue

def get_paths_from_clipboard(handler: RichProgressHandler):
    """从剪贴板读取多行路径"""
    try:
        clipboard_content = pyperclip.paste()
        if not clipboard_content:
            return []
        
        paths = [
            path.strip().strip('"').strip("'")
            for path in clipboard_content.splitlines() 
            if path.strip()
        ]
        
        valid_paths = [
            path for path in paths 
            if os.path.exists(path)
        ]
        
        if valid_paths:
            update_panel_log(handler, "file_ops", f"📋 从剪贴板读取到 {len(valid_paths)} 个有效路径")
        else:
            update_panel_log(handler, "error_log", "⚠️ 剪贴板中没有有效路径")
            
        return valid_paths
        
    except Exception as e:
        update_panel_log(handler, "error_log", f"❌ 读取剪贴板时出错: {e}")
        return []

def main():
    """主函数"""
    # 如果有命令行参数，则使用命令行模式
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description='寻找同画师的压缩包文件')
        parser.add_argument('-c', '--clipboard', action='store_true', help='从剪贴板读取路径')
        parser.add_argument('--ignore-blacklist', action='store_true', help='忽略路径黑名单')
        parser.add_argument('--path', help='要处理的路径')
        args = parser.parse_args()
    else:
        # 否则使用TUI界面
        # 定义复选框选项
        checkbox_options = [
            ("从剪贴板读取路径", "clipboard", "-c", True),  # 默认开启
            ("忽略路径黑名单", "ignore_blacklist", "--ignore-blacklist"),
        ]

        # 定义输入框选项
        input_options = [
            ("路径", "path", "--path", "", "输入要处理的路径，留空使用默认路径"),
        ]

        # 预设配置
        preset_configs = {
            "标准模式": {
                "description": "标准处理模式，遵循黑名单规则",
                "checkbox_options": ["clipboard"],
                "input_values": {"path": ""}
            },
            "完全模式": {
                "description": "处理所有文件，忽略黑名单规则",
                "checkbox_options": ["clipboard", "ignore_blacklist"],
                "input_values": {"path": ""}
            }
        }

        # 创建并运行配置界面
        app = create_config_app(
            program=__file__,
            checkbox_options=checkbox_options,
            input_options=input_options,
            title="寻找同画师工具",
            preset_configs=preset_configs
        )
        # 运行TUI并获取结果
        app.run()
        # 将TUI的选择转换为类似命令行参数的格式
        class Args:
            pass
        args = Args()
        args.clipboard = app.get_checkbox_state("clipboard")
        args.ignore_blacklist = app.get_checkbox_state("ignore_blacklist")
        args.path = app.get_input_value("path")

    # 获取路径
    paths = []
    if args.clipboard:
        try:
            clipboard_content = pyperclip.paste()
            if clipboard_content:
                paths.extend([
                    path.strip().strip('"').strip("'")
                    for path in clipboard_content.splitlines() 
                    if path.strip()
                ])
        except Exception as e:
            print(f"❌ 读取剪贴板时出错: {e}")
    elif args.path:
        paths.append(args.path)
    else:
        print("请输入要处理的路径（每行一个，输入空行结束）：")
        while True:
            try:
                line = input().strip()
                if not line:
                    break
                paths.append(line)
            except (EOFError, KeyboardInterrupt):
                print("用户取消输入")
                return

    if not paths:
        print("❌ 未提供任何路径")
        return

    # 验证路径
    valid_paths = [path for path in paths if os.path.exists(path)]
    if not valid_paths:
        print("❌ 没有有效的路径")
        return

    # 处理路径
    with setup_logging() as handler:
        for path in valid_paths:
            update_panel_log(handler, "process", f"🚀 开始处理目录: {path}")
            process_directory(path, handler, ignore_blacklist=args.ignore_blacklist)
            update_panel_log(handler, "process", f"✨ 目录处理完成: {path}")

if __name__ == "__main__":
    main()

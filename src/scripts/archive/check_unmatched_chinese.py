import os
import re
import argparse
import logging
from pathlib import Path
from colorama import init, Fore, Style
from opencc import OpenCC
import pyperclip
import datetime
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from functools import partial

# 初始化colorama和OpenCC
init()
cc = OpenCC('s2t')  # 创建简体到繁体转换器

# 预处理关键词列表
def preprocess_keywords(keywords: list) -> set:
    """预处理关键词列表，生成所有变体（简体、繁体）"""
    all_variants = set()
    for keyword in keywords:
        # 添加原始关键词（小写）
        all_variants.add(keyword.lower())
        # 添加繁体版本（小写）
        all_variants.add(cc.convert(keyword).lower())
        # 添加简体版本（小写）
        simplified = OpenCC('t2s').convert(keyword).lower()
        if simplified != keyword.lower():
            all_variants.add(simplified)
    return all_variants

# 预处理关键词
CHINESE_KEYWORDS_SET = preprocess_keywords([
    '汉化', '漢化',  # 汉化/漢化
    '翻译', '翻訳', '翻譯',  # 翻译相关
    '中国翻译', '中国翻訳', '中国語', 'chinese', '中文', '中国',  # 中文翻译
    '嵌字',  # 嵌字
    '掃圖', '掃',  # 扫图相关
    '制作', '製作',  # 制作相关
    '重嵌',  # 重新嵌入
    '个人',  # 个人翻译
    '修正',  # 修正版本
    '汉', '漢',  # 汉字相关
    '譯', '訳',  # 译字相关
    '数位', '未来数位',  # 汉化相关
    '出版', '青文出版',  # 翻译相关
    '脸肿', '无毒', '空気系', '夢之行蹤', '萌幻鴿鄉', '绅士仓库', 'Lolipoi', '靴下',
    '不可视', '一匙咖啡豆', '无邪气', '洨五', '白杨', '瑞树',  # 常见汉化组名
    '汉化组', '漢化組', '汉化社', '漢化社', 'CE 家族社',  # 常见后缀
    '个人汉化', '個人漢化'  # 个人汉化
])

BLACKLIST_KEYWORDS_SET = preprocess_keywords([
    'trash', '画集', '畫集', 'artbook', 'art book', 'art works', 'illustrations',
    '图集', '圖集', 'illust', 'collection',
    '杂图', '雜圖', '杂图合集', '雜圖合集',
    'pixiv', 'fanbox', 'gumroad', 'twitter',
    '待分类', '待處理', '待分類',
    '图包', '圖包',
    '图片', '圖片',
    'cg', 'CG',
])

class ColoredFormatter(logging.Formatter):
    """自定义的彩色日志格式化器"""
    def format(self, record):
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

def setup_logging():
    """配置日志处理"""
    logging.basicConfig(level=logging.INFO)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter('%(message)s'))
    logging.getLogger('').handlers = [console_handler]

def extract_brackets_content(filename: str) -> list:
    """提取文件名中方括号内的内容"""
    pattern = r'\[(.*?)\]'
    return re.findall(pattern, filename)

def is_in_blacklist(filepath: str) -> bool:
    """检查文件名或路径是否包含黑名单关键词"""
    filepath_lower = str(Path(filepath)).lower()
    return any(keyword in filepath_lower for keyword in BLACKLIST_KEYWORDS_SET)

def has_chinese_keywords(brackets_content: list) -> bool:
    """检查方括号内容是否包含汉化关键词"""
    for content in brackets_content:
        content_lower = content.lower()
        if any(keyword in content_lower for keyword in CHINESE_KEYWORDS_SET):
            return True
    return False

def get_paths_from_clipboard():
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
            logging.info(f"从剪贴板读取到 {len(valid_paths)} 个有效路径")
        else:
            logging.warning("剪贴板中没有有效路径")
        
        return valid_paths
        
    except Exception as e:
        logging.error(f"读取剪贴板时出错: {e}")
        return []

def collect_files(directory: str) -> list:
    """收集目录中的所有压缩文件"""
    files_to_process = []
    logging.info("正在收集文件列表...")
    
    for root, _, files in os.walk(directory):
        if 'trash' in root:  # 跳过trash目录
            continue
            
        for file in files:
            if file.lower().endswith(('.zip', '.rar', '.7z')):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, directory)
                files_to_process.append((full_path, rel_path))
    
    logging.info(f"找到 {len(files_to_process)} 个压缩文件")
    return files_to_process

def process_single_file(file_info: tuple) -> tuple:
    """处理单个文件，返回未匹配状态和方括号内容"""
    full_path, rel_path = file_info
    
    # 检查是否在黑名单中
    if is_in_blacklist(full_path):
        return None, []
    
    # 提取方括号内容
    brackets_content = extract_brackets_content(os.path.basename(full_path))
    
    # 如果没有方括号内容，或者方括号内容不包含汉化关键词
    if not brackets_content or not has_chinese_keywords(brackets_content):
        return rel_path, brackets_content
    
    return None, brackets_content

def check_directory(directory: str) -> list:
    """检查目录中的压缩文件，返回未匹配的文件列表和所有方括号内容"""
    unmatched_files = []
    all_brackets_content = []
    
    # 收集所有文件
    files_to_process = collect_files(directory)
    
    if not files_to_process:
        return [], []
    
    # 创建进度条
    with tqdm(total=len(files_to_process), desc="检查文件", unit="个") as pbar:
        # 使用线程池处理文件
        with ThreadPoolExecutor(max_workers=min(32, os.cpu_count() * 4)) as executor:
            # 创建任务
            futures = []
            for file_info in files_to_process:
                future = executor.submit(process_single_file, file_info)
                futures.append((future, file_info))
            
            # 处理完成的任务
            for future, file_info in futures:
                try:
                    unmatched_file, brackets_content = future.result()
                    if unmatched_file:
                        unmatched_files.append(unmatched_file)
                    all_brackets_content.extend(brackets_content)
                    
                    # 更新进度条
                    pbar.set_description(f"检查文件: {os.path.basename(file_info[1])}")
                    pbar.update(1)
                    
                except Exception as e:
                    logging.error(f"处理文件出错 {file_info[1]}: {str(e)}")
                    pbar.update(1)
    
    return unmatched_files, all_brackets_content

def analyze_brackets_content(all_brackets_content: list) -> None:
    """分析所有方括号内容，找出重复出现的词组"""
    # 将方括号内容分割成单词
    word_count = {}
    
    # 使用线程池加速处理
    def process_content(content):
        result = {}
        words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z0-9]+', content)
        for word in words:
            if len(word) >= 2:  # 只统计长度大于等于2的词
                word = word.lower()  # 转换为小写
                if word not in result:
                    result[word] = set()
                result[word].add(content)
        return result
    
    # 创建进度条
    pbar = tqdm(total=len(all_brackets_content), desc="分析方括号内容", unit="个")
    
    # 使用线程池处理
    with ThreadPoolExecutor(max_workers=min(32, os.cpu_count() * 4)) as executor:
        # 提交所有任务
        future_to_content = {
            executor.submit(process_content, content): content
            for content in all_brackets_content
        }
        
        # 处理结果
        for future in as_completed(future_to_content):
            try:
                result = future.result()
                # 合并结果到主字典
                for word, contents in result.items():
                    if word not in word_count:
                        word_count[word] = set()
                    word_count[word].update(contents)
                pbar.update(1)
            except Exception as e:
                logging.error(f"处理方括号内容时出错: {str(e)}")
                pbar.update(1)
    
    pbar.close()
    
    # 找出在不同方括号内容中重复出现的词
    repeated_words = {
        word: contents 
        for word, contents in word_count.items() 
        if len(contents) >= 3  # 在三个以上不同的方括号内容中出现
    }
    
    # 按出现次数排序
    sorted_words = sorted(
        repeated_words.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )
    
    # 输出结果
    if sorted_words:
        print("\n" + "="*50)
        logging.info(f"发现以下词在三个以上不同方括号中重复出现：")
        for word, contents in sorted_words:
            if len(contents) >= 2:  # 只显示出现两次以上的
                print(f"{Fore.CYAN}  {word}: 出现 {len(contents)} 次{Style.RESET_ALL}")
        print("="*50)
    else:
        logging.info("未发现重复出现的词")

def save_unmatched_files(unmatched_files: list, directory: str) -> None:
    """保存未匹配的文件列表到文本文件"""
    if not unmatched_files:
        return
        
    # 创建输出目录
    output_dir = os.path.join(directory, "unmatched_files")
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成输出文件名（使用时间戳）
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"unmatched_files_{timestamp}.txt")
    
    # 保存文件列表
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"未匹配文件数量: {len(unmatched_files)}\n")
        f.write("="*50 + "\n")
        for file in unmatched_files:
            f.write(f"{file}\n")
    
    logging.info(f"未匹配文件列表已保存到: {output_file}")

def get_input_paths():
    """从终端获取路径输入"""
    print(f"{Fore.CYAN}请输入要处理的路径（每行一个，输入空行结束）：{Style.RESET_ALL}")
    paths = []
    while True:
        try:
            line = input().strip()
            if not line:  # 如果输入空行，结束输入
                break
            # 移除引号
            line = line.strip('"').strip("'")
            if os.path.exists(line):
                paths.append(line)
            else:
                logging.error(f"路径不存在: {line}")
        except EOFError:
            break
        except KeyboardInterrupt:
            print("\n已取消输入")
            break
    return paths

def main():
    parser = argparse.ArgumentParser(description='检测未匹配汉化关键词的压缩包')
    parser.add_argument('paths', nargs='*', help='要处理的目录路径')
    parser.add_argument('-c', '--clipboard', action='store_true', help='从剪贴板读取路径')
    parser.add_argument('-i', '--input', action='store_true', help='从终端输入路径')
    args = parser.parse_args()
    
    # 设置日志
    setup_logging()
    
    # 获取要处理的路径
    paths = []
    if args.input:
        paths.extend(get_input_paths())
    elif args.clipboard:
        paths.extend(get_paths_from_clipboard())
    elif args.paths:
        paths.extend(args.paths)
    else:
        # 如果没有提供任何参数，默认使用终端输入
        paths.extend(get_input_paths())
    
    if not paths:
        logging.error("未提供任何路径")
        return
    
    # 收集所有目录的方括号内容
    all_brackets_content = []
    
    # 显示总体进度
    with tqdm(total=len(paths), desc="处理目录", unit="个", position=0) as pbar:
        # 处理每个路径
        for path in paths:
            if os.path.exists(path):
                pbar.set_description(f"处理目录: {os.path.basename(path)}")
                logging.info(f"\n开始检查目录: {path}")
                
                unmatched_files, brackets_content = check_directory(path)
                all_brackets_content.extend(brackets_content)
                
                # 保存未匹配文件列表
                if unmatched_files:
                    logging.warning(f"发现 {len(unmatched_files)} 个未匹配的文件")
                    save_unmatched_files(unmatched_files, path)
                else:
                    logging.info("未发现未匹配的文件")
                    
                logging.info(f"目录检查完成: {path}")
            else:
                logging.error(f"路径不存在: {path}")
            
            pbar.update(1)
    
    # 分析所有方括号内容
    if all_brackets_content:
        analyze_brackets_content(all_brackets_content)

if __name__ == "__main__":
    main() 
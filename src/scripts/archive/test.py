import re
import os
from collections import defaultdict
import difflib
import sys

def preprocess_filename(filename):
    """预处理文件名"""
    # 获取文件名（不含路径）
    name = os.path.basename(filename)
    # 去除扩展名
    name = name.rsplit('.', 1)[0]
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

def find_series_groups(input_data):
    """查找文件系列
    
    Args:
        input_data: 可以是文件路径列表，或者是多行字符串
    """
    # 处理输入数据
    if isinstance(input_data, str):
        # 如果是多行字符串，按行分割
        filenames = [line.strip() for line in input_data.splitlines() if line.strip()]
    else:
        # 如果是列表，直接使用
        filenames = input_data
    
    # 预处理所有文件名
    processed_names = {f: preprocess_filename(f) for f in filenames}
    processed_keywords = {f: get_keywords(processed_names[f]) for f in filenames}
    
    # 存储系列分组
    series_groups = defaultdict(list)
    # 待处理的文件集合
    remaining_files = set(filenames)
    
    while remaining_files:
        # 找出当前剩余文件中最长的公共关键词序列
        best_length = 0
        best_common = None
        best_pair = None
        
        # 遍历所有可能的文件对，找出最长匹配
        for file1 in remaining_files:
            keywords1 = processed_keywords[file1]
            for file2 in remaining_files - {file1}:
                keywords2 = processed_keywords[file2]
                common = find_longest_common_keywords(keywords1, keywords2)
                if len(common) > best_length:
                    best_length = len(common)
                    best_common = common
                    best_pair = (file1, file2)
        
        # 如果找到了匹配
        if best_pair:
            matched_files = set(best_pair)
            # 用这个最长序列查找其他匹配的文件
            for other_file in remaining_files - matched_files:
                other_keywords = processed_keywords[other_file]
                common = find_longest_common_keywords(processed_keywords[best_pair[0]], other_keywords)
                if common == best_common:
                    matched_files.add(other_file)
            
            # 添加到系列组
            series_name = ' '.join(best_common)
            series_groups[series_name].extend(matched_files)
            # 从待处理集合中移除
            remaining_files -= matched_files
        else:
            # 没有找到匹配，将剩余文件归类为"其他"
            series_groups["其他"].extend(remaining_files)
            remaining_files.clear()
    
    return series_groups

def print_series_groups(series_groups):
    """打印系列分组结果"""
    print("找到的系列：")
    for series_name, files in series_groups.items():
        if series_name != "其他":
            print(f"\n{series_name}:")
            for f in sorted(files):
                print(f"  - {f}")

    if "其他" in series_groups and series_groups["其他"]:
        print("\n其他未分类文件:")
        for f in sorted(series_groups["其他"]):
            print(f"  - {f}")

def main():
    print("=== 测试开始 ===")
    print(f"Python版本: {sys.version}")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"命令行参数: {sys.argv}")
    
    test_path = "E:/1EHV/[Ballistic onahole (Б、Deadflow)]"
    print(f"测试路径: {test_path}")
    
    if os.path.exists(test_path):
        print("✅ 路径存在")
        # 列出目录内容
        try:
            files = os.listdir(test_path)
            print(f"目录内容: {files}")
        except Exception as e:
            print(f"❌ 列出目录失败: {e}")
    else:
        print("❌ 路径不存在")

if __name__ == "__main__":
    main()
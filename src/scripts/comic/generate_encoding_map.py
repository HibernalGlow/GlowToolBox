import os
import json
import argparse
import logging
from collections import defaultdict
from typing import Dict, List, Tuple
import chardet

def setup_logger(verbose=False):
    """设置日志记录器"""
    logger = logging.getLogger('EncodingMapGenerator')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def detect_encoding(text: bytes) -> str:
    """检测文本的编码"""
    result = chardet.detect(text)
    return result['encoding'] or 'unknown'

def try_decode_with_encodings(text: bytes, encodings: List[str]) -> List[Tuple[str, str]]:
    """尝试使用不同的编码解码文本"""
    results = []
    for encoding in encodings:
        try:
            decoded = text.decode(encoding)
            results.append((decoded, encoding))
        except UnicodeDecodeError:
            continue
    return results

def analyze_filename(filename: str) -> Dict:
    """分析文件名并尝试不同的编码方式"""
    filename_bytes = filename.encode('raw_unicode_escape')
    common_encodings = [
        'utf-8', 'gbk', 'gb2312', 'big5', 'shift_jis',
        'euc-jp', 'euc-kr', 'latin1', 'ascii'
    ]
    
    # 检测可能的编码
    detected_encoding = detect_encoding(filename_bytes)
    if detected_encoding not in common_encodings:
        common_encodings.insert(0, detected_encoding)
    
    # 尝试所有编码
    decoding_results = try_decode_with_encodings(filename_bytes, common_encodings)
    
    return {
        'original': filename,
        'detected_encoding': detected_encoding,
        'decoded_versions': [
            {'text': decoded, 'encoding': encoding}
            for decoded, encoding in decoding_results
        ]
    }

def generate_character_mappings(filenames: List[str]) -> Dict:
    """生成字符映射表"""
    char_mappings = defaultdict(list)
    example_conversions = {}
    
    for filename in filenames:
        analysis = analyze_filename(filename)
        original = analysis['original']
        
        # 记录示例转换
        example_conversions[original] = {
            'original': original,
            'encoding': analysis['detected_encoding'],
            'decoded_versions': analysis['decoded_versions']
        }
        
        # 分析每个字符
        for char in original:
            if ord(char) > 127:  # 非ASCII字符
                for decoded_version in analysis['decoded_versions']:
                    decoded_text = decoded_version['text']
                    if len(decoded_text) == len(original):
                        char_index = original.index(char)
                        if char_index < len(decoded_text):
                            decoded_char = decoded_text[char_index]
                            if decoded_char != char:
                                char_mappings[char].append(decoded_char)
    
    # 选择最常见的映射
    final_mappings = {}
    for char, mappings in char_mappings.items():
        if mappings:
            # 选择出现次数最多的映射
            most_common = max(set(mappings), key=mappings.count)
            final_mappings[char] = most_common
    
    return {
        'character_mappings': final_mappings,
        'example_conversions': example_conversions
    }

def save_mapping_file(mapping_data: Dict, output_file: str):
    """保存映射数据到JSON文件"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(mapping_data, f, ensure_ascii=False, indent=4)

def main():
    parser = argparse.ArgumentParser(description='生成文件名编码映射表')
    parser.add_argument('files', nargs='+', help='要分析的文件列表')
    parser.add_argument('--output', '-o', default='encoding_map.json', help='输出的JSON文件路径')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示详细信息')
    args = parser.parse_args()
    
    logger = setup_logger(args.verbose)
    
    # 生成映射表
    logger.info("开始分析文件名...")
    mapping_data = generate_character_mappings(args.files)
    
    # 保存结果
    logger.info(f"保存映射表到 {args.output}")
    save_mapping_file(mapping_data, args.output)
    
    # 显示结果统计
    logger.info(f"共生成 {len(mapping_data['character_mappings'])} 个字符映射")
    logger.info(f"记录了 {len(mapping_data['example_conversions'])} 个示例转换")

if __name__ == "__main__":
    main() 
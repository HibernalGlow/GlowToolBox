import os
import sys
import argparse
from typing import Optional, Tuple, List
import unicodedata
import logging
from pathlib import Path
import codecs
import ftfy  # 用于修复Unicode文本
import unidecode  # 用于ASCII转换
import jaconv  # 用于日文编码转换
import re
from functools import lru_cache
import mojimoji  # 用于全角半角转换
import pykakasi  # 用于假名转换
# import fugashi  # 用于日文分词

class EncodingFixer:
    """文件名编码修复类，使用多种Python编码库"""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.logger = self._setup_logger()
        self.kakasi = pykakasi.kakasi()
        # self.tagger = fugashi.Tagger()
        
        # 扩展编码列表
        self.common_encodings = [
            'shift_jis', 'cp932', 'euc_jp', 'iso2022_jp',  # 日文编码
            'cp437', 'cp1252', 'latin1', 'ascii',          # 西文编码
            'gbk', 'big5', 'gb2312',                       # 中文编码
            'utf-8', 'utf-16', 'utf-32',                   # Unicode编码
            'cp949', 'euc_kr',                             # 韩文编码
            'koi8_r', 'cp866'                              # 俄文编码
        ]
        
        # 特殊字符映射
        self.special_chars = {
            '㌀': 'アパート',
            '㌁': 'アルファ',
            '㌂': 'アンペア',
            # ... 可以添加更多特殊字符映射
        }
        
        # 添加非法字符集
        self.invalid_chars = set(''.join([
            '├╢┼Θ╤╕╪╜┤',  # 常见乱码字符
            '╚╦Ñ╩⌐û╖┴π≤',
            '╛╨╩°╞│╗▐╟',
            '▒╫▓░║╔╗╝╜'
        ]))
        
        # 添加合法字符范围
        self.valid_ranges = [
            (0x3040, 0x309F),  # 平假名
            (0x30A0, 0x30FF),  # 片假名
            (0x4E00, 0x9FFF),  # 汉字
            (0xFF00, 0xFFEF),  # 全角字符
            (0x0020, 0x007E),  # 基本ASCII
            (0x3000, 0x303F),  # CJK符号和标点
        ]

    def _setup_logger(self):
        """设置日志"""
        logger = logging.getLogger('EncodingFixer')
        logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)
        
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger

    def is_valid_char(self, char: str) -> bool:
        """检查单个字符是否合法"""
        if char in self.invalid_chars:
            return False
            
        code = ord(char)
        return any(start <= code <= end for start, end in self.valid_ranges)

    def is_japanese_text(self, text: str) -> bool:
        """增强的日文文本检测"""
        if not text:
            return False
            
        # 检查是否包含非法字符
        if any(c in self.invalid_chars for c in text):
            return False
            
        # 检查所有字符是否合法
        if not all(self.is_valid_char(c) for c in text):
            return False
            
        # 检查是否包含至少一个日文字符
        has_jp = any(
            '\u3040' <= c <= '\u309F' or  # 平假名
            '\u30A0' <= c <= '\u30FF' or  # 片假名
            '\u4E00' <= c <= '\u9FFF'     # 汉字
            for c in text
        )
        
        # 文件名中必须包含日文字符
        if not has_jp:
            return False
            
        # 检查乱码特征
        weird_patterns = [
            r'[ﾈﾋﾊｩ]{3,}',  # 连续的半角片假名
            r'[｡｢｣､]{3,}',  # 连续的特殊符号
            r'[亦凪楓]{2,}',  # 不常见汉字连续出现
            r'[\?]{2,}',    # 连续的问号
            r'[･]{2,}',     # 连续的中点
        ]
        
        if any(re.search(pattern, text) for pattern in weird_patterns):
            return False
            
        return True

    def try_ftfy(self, text: str) -> Optional[str]:
        """使用ftfy库尝试修复编码"""
        try:
            fixed = ftfy.fix_text(text)
            return fixed if self.is_japanese_text(fixed) else None
        except Exception as e:
            self.logger.debug(f"ftfy处理失败: {e}")
            return None

    def try_jaconv(self, text: str) -> Optional[str]:
        """使用jaconv库尝试转换"""
        try:
            # 尝试不同的日文编码转换
            conversions = [
                jaconv.z2h,  # 全角转半角
                jaconv.h2z,  # 半角转全角
                jaconv.normalize,  # 标准化
            ]
            
            for conv in conversions:
                result = conv(text)
                if self.is_japanese_text(result):
                    return result
            return None
        except Exception as e:
            self.logger.debug(f"jaconv处理失败: {e}")
            return None

    def try_encode_decode(self, text: str) -> Optional[str]:
        """改进的编码转换尝试"""
        # 优化编码组合顺序
        encode_decode_pairs = [
            ('cp932', 'utf-8'),      # 最常见的情况
            ('shift_jis', 'utf-8'),  # 标准日文编码
            ('cp437', 'cp932'),      # DOS编码
            ('cp1252', 'cp932'),     # Windows编码
            ('latin1', 'cp932'),     # 西欧编码
        ]
        
        best_result = None
        best_score = 0
        
        for enc_from, enc_to in encode_decode_pairs:
            try:
                # 尝试编码转换
                decoded = text.encode(enc_from, errors='replace').decode(enc_to, errors='replace')
                
                # 计算结果质量分数
                score = self._calculate_text_score(decoded)
                
                if score > best_score:
                    best_score = score
                    best_result = decoded
                    
            except Exception:
                continue
        
        return best_result if best_score > 0.5 else None

    def _calculate_text_score(self, text: str) -> float:
        """计算文本的日文特征分数"""
        if not text:
            return 0.0
            
        # 统计字符类型
        jp_chars = sum(1 for c in text if '\u3040' <= c <= '\u309F' or  # 平假名
                                        '\u30A0' <= c <= '\u30FF' or     # 片假名
                                        '\u4E00' <= c <= '\u9FFF')       # 汉字
                                        
        valid_chars = sum(1 for c in text if self.is_valid_char(c))
        total_chars = len(text)
        
        # 计算分数
        jp_ratio = jp_chars / total_chars if total_chars > 0 else 0
        valid_ratio = valid_chars / total_chars if total_chars > 0 else 0
        
        # 综合评分
        score = (jp_ratio * 0.7 + valid_ratio * 0.3)
        
        return score

    def try_codecs_recovery(self, text: str) -> Optional[str]:
        """使用codecs尝试恢复"""
        for encoding in self.common_encodings:
            try:
                # 使用codecs进行编码转换
                decoded = codecs.decode(text.encode(encoding, errors='replace'), 
                                     'shift_jis', errors='replace')
                if self.is_japanese_text(decoded):
                    return decoded
            except Exception:
                continue
        return None

    def try_mojimoji(self, text: str) -> Optional[str]:
        """使用mojimoji进行全角半角转换"""
        try:
            # 尝试不同的转换组合
            conversions = [
                mojimoji.han_to_zen,  # 半角转全角
                mojimoji.zen_to_han,  # 全角转半角
                lambda x: mojimoji.han_to_zen(mojimoji.zen_to_han(x)),  # 标准化
            ]
            
            for conv in conversions:
                result = conv(text)
                if self.is_japanese_text(result):
                    return result
            return None
        except Exception as e:
            self.logger.debug(f"mojimoji处理失败: {e}")
            return None

    def try_kakasi(self, text: str) -> Optional[str]:
        """使用pykakasi进行假名转换"""
        try:
            result = self.kakasi.convert(text)
            converted = ''.join(item['orig'] for item in result)
            return converted if self.is_japanese_text(converted) else None
        except Exception as e:
            self.logger.debug(f"kakasi处理失败: {e}")
            return None

    def try_special_chars(self, text: str) -> Optional[str]:
        """处理特殊字符"""
        changed = False
        result = text
        for char, replacement in self.special_chars.items():
            if char in text:
                result = result.replace(char, replacement)
                changed = True
        return result if changed else None

    def try_advanced_combinations(self, text: str) -> Optional[str]:
        """尝试更复杂的编码组合"""
        combinations = [
            ('cp437', 'shift_jis', 'utf-8'),
            ('cp1252', 'cp932', 'utf-8'),
            ('latin1', 'euc_jp', 'utf-8'),
            ('gbk', 'shift_jis', 'cp932'),
        ]
        
        for enc1, enc2, enc3 in combinations:
            try:
                # 三重编码转换
                step1 = text.encode(enc1, errors='replace')
                step2 = step1.decode(enc2, errors='replace')
                step3 = step2.encode(enc3, errors='replace')
                result = step3.decode('utf-8', errors='replace')
                
                if self.is_japanese_text(result):
                    return result
            except Exception:
                continue
        return None

    def fix_filename(self, filename: str) -> Tuple[str, str]:
        """修复文件名"""
        if self.is_japanese_text(filename):
            return filename, 'utf-8 (已是正确编码)'
            
        # 尝试所有方法
        methods = [
            ('encode_decode', self.try_encode_decode),  # 优先使用基本编码转换
            ('jaconv', self.try_jaconv),               # 日文专用转换
            ('mojimoji', self.try_mojimoji),           # 全角半角转换
            ('special_chars', self.try_special_chars),  # 特殊字符处理
            ('advanced_combinations', self.try_advanced_combinations),  # 复杂组合
        ]
        
        for method_name, method_func in methods:
            result = method_func(filename)
            if result and self.is_japanese_text(result):
                return result, method_name
                
        return filename, '未能修复'

def demo_fix():
    """演示功能"""
    test_cases = [
        "【例】日本語のファイル名.txt",     # 正确的日文
        "ｱｲｳｴｵ漢字かきくけこ.txt",        # 混合假名
        "(C100) [サークル名] 作品名.zip",  # 同人志格式
        "第01巻.zip",                      # 简单数字和日文
        "úñ3000ííüä╚╦Ñ╩⌐ûÑ╖ñ┴ñπñ≤╛╨╩°ñ╖ñ╞",  # 乱码
        "2021-05-14 ╢╣╝╜╥╙╨╞╖╓▒╫.zip",    # 乱码
        "├╢┼Θ╤╕╪╜┤я╛я╖я┐╛╨╩°я╖я╞│╗я▐я╟",  # 乱码
    ]
    
    fixer = EncodingFixer(verbose=True)
    print("\n=== 编码修复演示 ===")
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}:")
        print(f"原始文件名: {case}")
        fixed, method = fixer.fix_filename(case)
        print(f"修复后文件名: {fixed}")
        print(f"使用的方法: {method}")
        print("-" * 50)

def main():
    parser = argparse.ArgumentParser(description='修复日文文件名乱码')
    parser.add_argument('filename', nargs='?', help='要修复的文件名')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示详细信息')
    parser.add_argument('--demo', '-d', action='store_true', help='运行演示')
    args = parser.parse_args()
    
    if args.demo:
        demo_fix()
        return
        
    if not args.filename:
        parser.print_help()
        return
        
    fixer = EncodingFixer(verbose=args.verbose)
    fixed_name, method = fixer.fix_filename(args.filename)
    
    if args.verbose:
        print(f"原始文件名: {args.filename}")
        print(f"修复后文件名: {fixed_name}")
        print(f"使用的方法: {method}")
    else:
        print(fixed_name)

if __name__ == "__main__":
    demo_fix()
    # main() 
    
import os
import sys
import subprocess
import argparse
from typing import Optional, Tuple
import chardet
from pathlib import Path
import re
import logging

class EncodingFixer:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.logger = self._setup_logger()
        self.tools_dir = self._get_tools_dir()
        self._check_tools()

    def _setup_logger(self):
        logger = logging.getLogger('EncodingFixer')
        logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def _get_tools_dir(self) -> Path:
        """获取外部工具目录"""
        script_dir = Path(__file__).parent
        tools_dir = script_dir / 'tools'
        tools_dir.mkdir(exist_ok=True)
        return tools_dir

    def _check_tools(self):
        """检查必要的工具是否存在"""
        nkf_path = self.tools_dir / 'nkf.exe'
        if not nkf_path.exists():
            self.logger.warning(f"未找到nkf.exe，请从 https://github.com/erw7/nkf/releases 下载并放到 {self.tools_dir} 目录")

    def _run_nkf(self, text: str, args: list) -> Optional[str]:
        """运行nkf命令"""
        nkf_path = self.tools_dir / 'nkf.exe'
        if not nkf_path.exists():
            return None

        try:
            # 创建临时文件
            temp_file = self.tools_dir / f'temp_{hash(text)}.txt'
            temp_file.write_text(text, encoding='utf-8', errors='ignore')

            # 运行nkf
            cmd = [str(nkf_path)] + args + [str(temp_file)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # 清理临时文件
            temp_file.unlink()
            
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            self.logger.debug(f"nkf处理失败: {e}")
        return None

    def detect_encoding(self, text: str) -> str:
        """使用多种方法检测编码"""
        # 1. 使用nkf检测
        nkf_result = self._run_nkf(text, ['-g'])
        if nkf_result:
            return nkf_result

        # 2. 使用chardet检测
        try:
            raw_bytes = text.encode('cp437', errors='replace')
            result = chardet.detect(raw_bytes)
            if result['confidence'] > 0.7:
                return result['encoding']
        except Exception:
            pass

        return 'unknown'

    def fix_filename(self, filename: str) -> Tuple[str, str]:
        """修复文件名编码"""
        # 如果文件名看起来是正确的日文，直接返回
        if self._is_valid_japanese(filename):
            return filename, 'utf-8 (已是正确编码)'

        # 检测编码
        detected_encoding = self.detect_encoding(filename)
        self.logger.debug(f"检测到的编码: {detected_encoding}")

        # 尝试使用nkf修复
        fixed = self._run_nkf(filename, ['-w', '--no-cp932'])
        if fixed and self._is_valid_japanese(fixed):
            return fixed, 'nkf'

        # 尝试其他编码组合
        encodings = ['cp437', 'cp932', 'shift_jis', 'euc_jp', 'iso2022_jp']
        for enc_from in encodings:
            try:
                # 转换为bytes
                raw_bytes = filename.encode(enc_from, errors='replace')
                # 尝试不同的解码方式
                for enc_to in ['cp932', 'shift_jis', 'utf-8']:
                    try:
                        decoded = raw_bytes.decode(enc_to, errors='replace')
                        if self._is_valid_japanese(decoded):
                            return decoded, f'{enc_from}->{enc_to}'
                    except Exception:
                        continue
            except Exception:
                continue

        return filename, '未能修复'

    def _is_valid_japanese(self, text: str) -> bool:
        """检查是否是有效的日文文件名"""
        # 检查是否包含日文字符
        has_jp = any(
            '\u3040' <= c <= '\u309F' or  # 平假名
            '\u30A0' <= c <= '\u30FF' or  # 片假名
            '\u4E00' <= c <= '\u9FFF'     # 汉字
            for c in text
        )

        # 检查是否是常见的日文文件名格式
        common_patterns = [
            r'\[.*?\]',          # [xxx]
            r'\(.*?\)',          # (xxx)
            r'第\d+[巻話]',      # 第xx巻/話
            r'Vol\.\d+',         # Vol.xx
            r'[上中下]巻',       # 上巻/中巻/下巻
        ]

        matches_pattern = any(re.search(pattern, text) for pattern in common_patterns)

        # 如果包含日文字符或匹配常见模式，且不包含明显的乱码字符
        if (has_jp or matches_pattern) and not re.search(r'[├╢┼Θ╤╕╪╜┤]', text):
            return True

        return False

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
    
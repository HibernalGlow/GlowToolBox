import re
import os
import logging
from typing import List, Tuple, Optional
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('markdown_processor.log', encoding='utf-8')
    ]
)

class MarkdownProcessor:
    def __init__(self, input_path: str, output_path: Optional[str] = None):
        """
        初始化 Markdown 处理器
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径（可选，默认覆盖输入文件）
        """
        self.input_path = Path(input_path)
        self.output_path = Path(output_path) if output_path else self.input_path
        self.patterns_and_replacements = [
            (r'(#{1,6} .*?。)', r'\1\n\n'),  # 每个标题行之后的句号处添加换行符
        ]
        # 配置参数
        self.max_blank_lines_between_headers = 3  # 允许标题之间的最大空行数

    def process_file(self) -> bool:
        """
        处理 Markdown 文件的主函数
        
        Returns:
            bool: 处理是否成功
        """
        try:
            if not self.input_path.exists():
                logging.error(f"输入文件不存在: {self.input_path}")
                return False

            # 处理连续标题
            self._process_headers()
            
            # 应用正则表达式替换
            self._apply_regex_patterns()
            
            logging.info(f"文件处理成功: {self.output_path}")
            return True
            
        except Exception as e:
            logging.error(f"处理文件时发生错误: {str(e)}")
            return False

    def _is_header_line(self, line: str) -> bool:
        """
        判断是否为标题行
        
        Args:
            line: 输入行
            
        Returns:
            bool: 是否为标题行
        """
        return line.strip().startswith('#')

    def _get_header_level(self, line: str) -> int:
        """
        获取标题级别
        
        Args:
            line: 标题行
            
        Returns:
            int: 标题级别（1-6）
        """
        return len(line) - len(line.lstrip('#'))

    def _is_consecutive_header(self, current_level: int, prev_level: int, 
                             blank_lines_count: int) -> bool:
        """
        判断是否为连续标题
        
        Args:
            current_level: 当前标题级别
            prev_level: 上一个标题级别
            blank_lines_count: 之间的空行数
            
        Returns:
            bool: 是否为连续标题
        """
        return (current_level == prev_level and 
                blank_lines_count <= self.max_blank_lines_between_headers)

    def _strip_headers_between_adjacent_same_level(self, lines: List[str]) -> List[str]:
        """
        处理连续的同级标题
        
        Args:
            lines: 输入的文件行列表
            
        Returns:
            List[str]: 处理后的文件行列表
        """
        cleaned_lines = []
        prev_level = 0
        consecutive_headers = []
        blank_lines_count = 0
        
        for line in lines:
            current_line = line.rstrip('\n')
            
            if self._is_header_line(current_line):
                current_level = self._get_header_level(current_line)
                
                # 判断是否为连续标题
                if consecutive_headers and self._is_consecutive_header(
                    current_level, prev_level, blank_lines_count):
                    consecutive_headers.append(len(cleaned_lines))
                    logging.debug(f"发现连续标题: {current_line}")
                else:
                    # 处理之前的连续标题
                    self._process_consecutive_headers(cleaned_lines, consecutive_headers)
                    consecutive_headers = [len(cleaned_lines)]
                
                prev_level = current_level
                blank_lines_count = 0
            else:
                if not current_line.strip():
                    blank_lines_count += 1
                else:
                    # 非空非标题行，处理之前的连续标题
                    self._process_consecutive_headers(cleaned_lines, consecutive_headers)
                    consecutive_headers = []
                    blank_lines_count = 0
            
            cleaned_lines.append(line)

        # 处理文件末尾的连续标题
        self._process_consecutive_headers(cleaned_lines, consecutive_headers)
        return cleaned_lines

    def _process_consecutive_headers(self, cleaned_lines: List[str], consecutive_headers: List[int]) -> None:
        """
        处理连续标题列表
        
        Args:
            cleaned_lines: 处理后的行列表
            consecutive_headers: 连续标题的索引列表
        """
        if len(consecutive_headers) > 1:
            for index in consecutive_headers:
                original_line = cleaned_lines[index]
                cleaned_lines[index] = original_line.lstrip('#').lstrip()
                logging.debug(f"处理连续标题: {original_line.strip()} -> {cleaned_lines[index].strip()}")

    def _process_headers(self) -> None:
        """处理连续的同级标题"""
        try:
            with open(self.input_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()

            processed_lines = self._strip_headers_between_adjacent_same_level(lines)

            with open(self.output_path, 'w', encoding='utf-8') as file:
                file.writelines(processed_lines)

        except Exception as e:
            logging.error(f"处理标题时发生错误: {str(e)}")
            raise

    def _apply_regex_patterns(self) -> None:
        """应用正则表达式模式"""
        try:
            with open(self.output_path, 'r', encoding='utf-8') as file:
                content = file.read()

            for pattern, replacement in self.patterns_and_replacements:
                content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

            with open(self.output_path, 'w', encoding='utf-8') as file:
                file.write(content)

        except Exception as e:
            logging.error(f"应用正则表达式时发生错误: {str(e)}")
            raise

def main():
    # 文件路径配置
    input_path = r'D:\1STUDY\3-Resource\NBU\教材\目录\1.md'
    
    # 创建处理器实例并执行处理
    processor = MarkdownProcessor(input_path)
    if processor.process_file():
        logging.info("文件处理完成")
    else:
        logging.error("文件处理失败")

if __name__ == '__main__':
    main()

import re
import cn2an
import pangu  # 新增
import logging
import os
from datetime import datetime

# 设置日志
def setup_logging():
    """设置日志配置"""
    # 创建logs目录（如果不存在）
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 生成日志文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'format_log_{timestamp}.log')
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

# 获取logger
logger = setup_logging()

class CodeBlockProtector:
    def __init__(self):
        self.code_block_pattern = re.compile(r'```[\s\S]*?```')
        self.inline_code_pattern = re.compile(r'`[^`]+`')
    
    def protect_codes(self, text):
        """保护代码块和行内代码"""
        self.code_blocks = []
        self.inline_codes = []
        
        # 保护代码块
        def save_code_block(match):
            self.code_blocks.append(match.group(0))
            logger.debug(f"保护代码块: {match.group(0)[:50]}...")
            return f'CODE_BLOCK_{len(self.code_blocks)-1}'
        
        # 保护行内代码
        def save_inline_code(match):
            self.inline_codes.append(match.group(0))
            logger.debug(f"保护行内代码: {match.group(0)}")
            return f'INLINE_CODE_{len(self.inline_codes)-1}'
        
        text = self.code_block_pattern.sub(save_code_block, text)
        text = self.inline_code_pattern.sub(save_inline_code, text)
        return text
    
    def restore_codes(self, text):
        """恢复代码块和行内代码"""
        # 先恢复行内代码，再恢复代码块
        for i, code in enumerate(self.inline_codes):
            text = text.replace(f'INLINE_CODE_{i}', code)
        
        for i, block in enumerate(self.code_blocks):
            text = text.replace(f'CODE_BLOCK_{i}', block)
        
        return text

class TextFormatter:
    def __init__(self):
        self.code_protector = CodeBlockProtector()
    
    def format_text(self, text):
        """格式化文本：处理中英文间距、标点符号等"""
        # 保护代码块
        text = self.code_protector.protect_codes(text)
        
        # 使用 pangu 处理中英文格式
        text = pangu.spacing_text(text)  # 自动处理中英文间距
        
        # 处理全角字符转半角
        text = self.full_to_half(text)
        
        # 恢复代码块
        text = self.code_protector.restore_codes(text)
        return text
    
    def full_to_half(self, text):
        """全角转半角"""
        full_half_map = {
            # '：': ':',
            # '；': ';',
            # '，': ',',
            # '。': '.',
            # '！': '!',
            # '？': '?',
            '（': '(',
            '）': ')',
            '［': '[',
            '］': ']',
            '【': '[',
            '】': ']',
            '｛': '{',
            '｝': '}',
            '"': '"',
            '"': '"',
            ''': "'",
            ''': "'",
            '｜': '|',
            '＼': '\\',
            '／': '/',
            # '《': '<',
            # '》': '>',
            '％': '%',
            '＃': '#',
            '＆': '&',
            '＊': '*',
            '＠': '@',
            '＾': '^',
            '～': '~',
            '｀': '`',
            ' 、':'、'
        }
        for full, half in full_half_map.items():
            text = text.replace(full, half)
        return text

# 定义你的文件路径
import os
current_dir = os.path.dirname(__file__)
file_path = os.path.join(current_dir, '1.md')

def convert_number(match, format_type):
    """
    通用的中文数字转换函数
    format_type: 
        'chapter': 章标题
        'section': 节标题
        'subsection': 子节标题
        'subsubsection': 小节标题
    """
    try:
        chinese_num = match.group(1)
        # 检查是否是特殊字符
        special_chars = {'〇': '零', '两': '二'}
        if chinese_num in special_chars:
            chinese_num = special_chars[chinese_num]
            
        logger.debug(f"尝试转换数字: {chinese_num}")
        arabic_num = cn2an.cn2an(chinese_num, mode='smart')
        standard_chinese = cn2an.an2cn(arabic_num)
        
        formats = {
            'chapter': f'# 第{standard_chinese}章 ',
            'section': f'## 第{standard_chinese}节 ',
            'subsection': f'### {standard_chinese}、',
            'subsubsection': f'#### ({standard_chinese}) '
        }
        result = formats.get(format_type, match.group(0))
        logger.info(f"转换标题成功: {match.group(0)} -> {result}")
        return result
    except Exception as e:
        logger.error(f"转换标题失败: {match.group(0)}, 错误: {str(e)}")
        # 如果转换失败，保持原样
        return match.group(0)

# 定义你的正则替换规则
patterns_and_replacements = [
    # 1. 基础格式清理
    (r'^ ',r''),  # 删除行首空格
    (r'(?:\r?\n){3,}', r'\n\n'),  # 将连续3个以上空行替换为两个空行
    (r'^.*?目\s{0,10}录.*$\n?', r''),  # 新增：修复"目 录"错误 spacing
    
    # 2. 标题格式化（使用函数处理中文数字）
    (r'^第([一二三四五六七八九十百千万零两]+)章(?:\s*)',  lambda m: convert_number(m, 'chapter')),  # 章标题
    (r'^第([一二三四五六七八九十百千万零两]+)节(?:\s*)',  lambda m: convert_number(m, 'section')),  # 节标题
    (r'^([一二三四五六七八九十百千万零两]+)、(?:\s*)',    lambda m: convert_number(m, 'subsection')),  # 中文数字标题
    (r'^\(([一二三四五六七八九十百千万零两]+)\)(?:\s*)',  lambda m: convert_number(m, 'subsubsection')),  # 带括号的中文数字标题
    # (r'^(\d+)\.(?:\s*)', r'##### \1. '),  # 数字标题
    # (r'^((\d+)\.(?:\s*))', r'###### \1. '),
    
    # 3. 中英文标点符号统一
    (r'\（', r'('),  # 中文括号转英文
    (r'\）', r')'),
    (r'\「', r'['),  # 中文引号转方括号
    (r'\」', r']'),
    (r'\【', r'['),  # 中文方括号转英文
    (r'\】', r']'),
    (r'\．', r'.'),  # 中文点号转英文
    (r'\。', r'.'),  # 句号转点号
    (r'\，', r', '),  # 中文逗号转英文
    (r'\；', r'; '),  # 中文分号转英文
    (r'\：', r': '),  # 中文冒号转英文
    (r'\！', r'!'),  # 中文感叹号转英文
    (r'\？', r'?'),  # 中文问号转英文
    (r'\"\"|\"', r'"'),  # 中文引号转英文
    (r'\'\'|\'', r"'"),
    
    # 4. 表格格式优化
    (r'([^|])\n\|(.*?\|.*?\|.*?\n)',r'\1\n\n|\2'),  # 在表格前文字后添加换行
    (r'\|\n([^|])',r'|\n\n\1'),  # 表格最后一行后添加空行
    (r':(-{1,1000}):',r'\1'),  # 修复表格分割线重复问题
    
    # 5. HTML标签清理
    (r'</body></html> ',r''),  # 删除HTML结束标签
    (r'<html><body>',r''),  # 删除HTML开始标签
    
    # 6. 数学符号和特殊字符处理
    (r'\$\\rightarrow\$',r'→'),  # LaTeX箭头转Unicode
    (r'\$\\leftarrow\$',r'←'),
    (r'\$=\$',r'='),  # LaTeX等号转普通等号
    (r'\^',r'+'),  # 处理上标符号
    (r'\$\+\$',r'+'),  # LaTeX加号转普通加号
    (r'\^\+',r'+'),
    (r'\$\\mathrm\{([a-z])\}\$',r'\1'),  # 简化LaTeX数学模式文本
    
    # 7. 代码和标记格式化
    (r'^\[([\u4e00-\u9fa5A-Za-z0-9]+)\]',r'`[\1]`'),  # 将方括号内容转为代码格式
]

def remove_empty_table_rows(text):
    """处理表格中的连续空行和首尾空行"""
    lines = text.split('\n')
    result = []
    table_lines = []
    in_table = False
    
    for line in lines:
        # 检查是否是表格行
        if '|' in line:
            if not in_table:
                in_table = True
            table_lines.append(line)
        else:
            if in_table:
                # 处理表格结束
                processed_table = process_table(table_lines)
                result.extend(processed_table)
                table_lines = []
                in_table = False
            result.append(line)
    
    # 处理文件末尾的表格
    if table_lines:
        processed_table = process_table(table_lines)
        result.extend(processed_table)
    
    return '\n'.join(result)

def process_table(table_lines):
    """处理单个表格的行"""
    if not table_lines:
        return []
    
    original_length = len(table_lines)
    logger.info(f"开始处理表格，原始行数: {original_length}")
    
    # 移除首尾的空行
    while table_lines and is_empty_table_row(table_lines[0]):
        logger.debug("移除表格首部空行")
        table_lines.pop(0)
    while table_lines and is_empty_table_row(table_lines[-1]):
        logger.debug("移除表格尾部空行")
        table_lines.pop()
    
    # 处理中间的连续空行和重复行
    result = []
    prev_line = None
    prev_empty = False
    removed_empty = 0
    removed_duplicate = 0
    
    for line in table_lines:
        # 处理空行
        if is_empty_table_row(line):
            if not prev_empty:
                result.append(line)
                prev_empty = True
            else:
                removed_empty += 1
                logger.debug("移除连续空行")
            continue
        
        # 处理重复行
        if line == prev_line:
            removed_duplicate += 1
            logger.debug(f"移除重复行: {line}")
            continue
        
        result.append(line)
        prev_line = line
        prev_empty = False
    
    logger.info(f"表格处理完成: 移除了 {removed_empty} 个连续空行, {removed_duplicate} 个重复行")
    logger.info(f"表格行数变化: {original_length} -> {len(result)}")
    return result

def is_empty_table_row(line):
    """检查是否是空的表格行"""
    if not line.strip():
        return True
    parts = line.split('|')[1:-1]  # 去掉首尾的|
    return all(cell.strip() == '' for cell in parts)

def process_text(text, patterns_and_replacements):
    """处理文本的核心函数"""
    logger.info("开始处理文本")
    formatter = TextFormatter()
    
    try:
        # 先进行基础文本格式化
        logger.info("进行基础文本格式化")
        text = formatter.format_text(text)
        
        # 处理表格空行和重复行
        logger.info("处理表格空行和重复行")
        text = remove_empty_table_rows(text)
        
        # 再应用其他替换规则
        logger.info("应用替换规则")
        for pattern, replacement in patterns_and_replacements:
            try:
                if callable(replacement):
                    text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
                else:
                    text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
                logger.debug(f"成功应用替换规则: {pattern}")
            except Exception as e:
                logger.error(f"应用替换规则失败: {pattern}, 错误: {str(e)}")
                continue
        
        logger.info("文本处理完成")
        return text
    except Exception as e:
        logger.error(f"处理文本时发生错误: {str(e)}")
        return text  # 返回原文本

def main():
    logger.info("=== 开始执行脚本 ===")
    
    # 定义文件路径（使用脚本所在目录）
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, '1.md')
    
    logger.info(f"处理文件: {file_path}")
    
    try:
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as file:
            text = file.read()
        logger.info(f"成功读取文件，字符数: {len(text)}")
        
        # 处理文本
        text = process_text(text, patterns_and_replacements)
        
        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(text)
        logger.info(f"成功写入文件，字符数: {len(text)}")
        
    except Exception as e:
        logger.error(f"处理失败: {str(e)}", exc_info=True)
    
    logger.info("=== 脚本执行完成 ===")

if __name__ == '__main__':
    main()
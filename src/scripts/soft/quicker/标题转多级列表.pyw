import re
import pyperclip

def convert_headings_to_list(text):
    lines = text.splitlines()
    result = []
    counters = [0] * 6
    last_level = 0
    content_block = []
    
    for line in lines:
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        
        if heading_match:
            # 处理之前累积的内容块
            if content_block:
                indent = "    " * (last_level)  # 内容块缩进比标题多一级
                result.extend(indent + line for line in content_block)
                content_block = []
            
            level = len(heading_match.group(1))
            content = heading_match.group(2)
            
            # 重置更深层级的计数器
            for i in range(level, 6):
                counters[i] = 0
            
            counters[level-1] += 1
            
            # 标题的缩进
            indent = "    " * (level - 1)
            number = str(counters[level-1]) + "."
            
            result.append(f"{indent}{number} {content}")
            last_level = level
        else:
            # 收集非标题行到内容块
            if line.strip():
                content_block.append(line)
            else:
                if content_block:
                    indent = "    " * last_level
                    result.extend(indent + line for line in content_block)
                    content_block = []
                result.append(line)
    
    # 处理最后的内容块
    if content_block:
        indent = "    " * last_level
        result.extend(indent + line for line in content_block)
    
    return "\n".join(result)

def adjust_indentation(text):
    lines = text.splitlines()
    # 检查是否存在无缩进的行
    has_zero_indent = any(not line.startswith(' ') and line.strip() for line in lines)
    
    if not has_zero_indent:
        # 找到最小缩进级别（最大标题级别）
        min_indent = float('inf')
        for line in lines:
            if line.strip():  # 跳过空行
                indent_count = len(line) - len(line.lstrip())
                min_indent = min(min_indent, indent_count)
        
        # 如果找到了缩进，从每行中删除对应数量的空格
        if min_indent != float('inf'):
            lines = [line[min_indent:] if line.strip() else line for line in lines]
    
    return '\n'.join(lines)

# 获取剪贴板内容
clipboard_text = pyperclip.paste()

# 转换内容
converted_text = convert_headings_to_list(clipboard_text)
# 调整缩进
converted_text = adjust_indentation(converted_text)

# 写回剪贴板
pyperclip.copy(converted_text)
import re
import pyperclip

def convert_headings_to_list(text):
    lines = text.splitlines()
    result = []
    counters = [0] * 6  # 每个级别的计数器
    level_stack = []    # 用于跟踪标题层级
    current_indent = 0  # 当前缩进级别
    in_list = False     # 是否在处理列表
    list_block = []     # 当前列表块
    content_indent = 0  # 内容的缩进级别（标题缩进+1）
    
    for line in lines:
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        list_match = re.match(r'^(\s*)((?:\d+\.|\*|\-)\s+)(.+)$', line)
        
        # 处理标题
        if heading_match:
            # 如果有未处理的列表，先处理它
            if list_block:
                result.extend(list_block)
                list_block = []
                in_list = False
            
            level = len(heading_match.group(1))
            content = heading_match.group(2)
            
            # 更新层级栈
            while level_stack and level_stack[-1] >= level:
                level_stack.pop()
            level_stack.append(level)
            
            # 计算标题缩进
            current_indent = len(level_stack) - 1
            # 内容缩进比标题多一级
            content_indent = current_indent + 1
            
            # 更新计数器
            counters[current_indent] += 1
            for i in range(current_indent + 1, 6):
                counters[i] = 0
                
            # 生成标题行
            indent = "    " * current_indent
            number = str(counters[current_indent]) + "."
            
            if '**' in content:
                result.append(f"{indent}{number} {content}")
            else:
                result.append(f"{indent}{number} **{content}**")
            
        # 处理列表
        elif list_match or (in_list and line.strip() and line.startswith('    ')):
            if not in_list:
                in_list = True
                list_block = []
            
            # 列表项在内容缩进级别的基础上保持原有的相对缩进
            base_indent = "    " * content_indent
            extra_indent = " " * (len(line) - len(line.lstrip()))
            list_block.append(base_indent + extra_indent + line.lstrip())
            
        # 处理空行
        elif not line.strip():
            if list_block:
                result.extend(list_block)
                list_block = []
                in_list = False
            result.append(line)
            
        # 处理其他行
        else:
            if list_block:
                result.extend(list_block)
                list_block = []
                in_list = False
            # 其他内容也使用内容缩进级别
            result.append("    " * content_indent + line)
    
    # 处理最后的列表块
    if list_block:
        result.extend(list_block)
    
    return "\n".join(result)

# 获取剪贴板内容
clipboard_text = pyperclip.paste()

# 转换内容
converted_text = convert_headings_to_list(clipboard_text)

# 写回剪贴板
pyperclip.copy(converted_text)
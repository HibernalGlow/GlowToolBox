import re

# 正则表达式，去掉方括号和圆括号中的内容
patterns = [
    (re.compile(r'\[([^\]]+)\]'), ''),
    (re.compile(r'\(([^)]+)\)'), ''),
    (re.compile(r'\s'), ''),
]

# 排除关键词列表
exclude_keywords = ["单行本","作品集","图集", "同人志","画集","合刊", "商业志"]  # 根据需要替换为实际的关键词

def remove_brackets(line):
    # 去掉括号和方框内容
    for pattern, replacement in patterns:
        line = pattern.sub(replacement, line)
    return line.strip()

def should_exclude(line):
    # 判断该行是否包含排除关键词
    for keyword in exclude_keywords:
        if keyword in line:
            return True
    return False

def replace_lines(a1_file, b1_file):
    # 读取a1文件中的所有行
    with open(a1_file, 'r', encoding='utf-8') as f:
        a1_lines = f.readlines()

    # 读取b1文件中的所有行
    with open(b1_file, 'r', encoding='utf-8') as f:
        b1_lines = f.readlines()

    # 创建一个包含去掉括号内容后的a1文件行的字典，以便快速查找
    a1_dict = {}
    for a1_line in a1_lines:
        # 如果a1行中包含排除关键词，则跳过该行
        if should_exclude(a1_line):
            continue
        
        # 去掉括号和方框内容后的行作为字典的键，原始行作为值
        modified_a1_line = remove_brackets(a1_line)
        a1_dict[modified_a1_line] = a1_line

    # 遍历b1文件中的每一行
    for i in range(len(b1_lines)):
        b1_line = b1_lines[i].strip()

        # 遍历a1_dict字典查找是否有匹配的文件名
        for modified_a1_line, original_a1_line in a1_dict.items():
            if modified_a1_line in b1_line:
                # 替换b1行内容为a1文件中的原始行
                b1_lines[i] = original_a1_line
                break

    # 将更新后的内容写回b1文件，保持顺序不变
    with open(b1_file, 'w', encoding='utf-8') as f:
        f.writelines(b1_lines)

# 调用函数进行替换操作
a1_file = 'a1.txt'  # a1文件路径
b1_file = 'b1.txt'  # b1文件路径

replace_lines(a1_file, b1_file)

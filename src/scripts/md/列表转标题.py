import re

# 定义你的文件路径
file_path = r'D:\1STUDY\3-Resource\NBU\教材\目录\2.md'  # 或者 'path_to_your_file.txt'

# 定义你的正则替换规则
patterns_and_replacements = [
#    (r'\*\*(.*?)\*\*',r'\1'),
#    (r'\[\d+\]\(#.+?\)', ''),
    (r'          \*',r'######'),
    (r'        \*',r'#####'),
    (r'      \*',r'####'),
    (r'    \*', r'###'),
    (r'  \*', r'##'),
    (r'\*', r'#'),
    (r'\n\s*\n', r'\n'),
    # 更多的模式和替换对...
]

# 读取文件内容
with open(file_path, 'r', encoding='utf-8') as file:
    text = file.read()

# 对文本进行正则替换
for pattern, replacement in patterns_and_replacements:
    text = re.sub(pattern, replacement, text)

# 将替换后的内容写回文件（假设是原地替换）
with open(file_path, 'w', encoding='utf-8') as file:
    file.write(text)
print(text)
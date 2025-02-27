import re

def extract_headings_and_write_to_file(input_filename, output_filename):
    # 读取输入文件
    with open(input_filename, 'r', encoding='utf-8') as file:
        content = file.read()

    # 正则表达式匹配以 '#' 开头的行
    pattern = r'^#\s*(.+)\n'
    # 使用 re.MULTILINE 使得 ^ 和 $ 能够匹配每一行的开始和结束
    headings = re.findall(pattern, content, re.MULTILINE)

    # 重新构造标题字符串，包括原始的 # 和换行符
    formatted_headings = [f"#{heading}\n" for heading in headings]

    # 写入输出文件
    with open(output_filename, 'w', encoding='utf-8') as file:
        for heading in formatted_headings:
            file.write(heading)

# 指定输入和输出文件名
input_filename = r'D:\1STUDY\3-Resource\NBU\教材\目录\2.md'
output_filename = '3.md'

# 执行提取和写入操作
extract_headings_and_write_to_file(input_filename, output_filename)
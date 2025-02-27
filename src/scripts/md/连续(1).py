import re

def convert_to_ordered_list(text):
    # 使用正则表达式匹配所有的(数字)行
    pattern = r'\((\d+)\)\s*(.*)'
    matches = re.findall(pattern, text, re.MULTILINE)

    # 创建一个新的列表来存储转换后的结果
    ordered_list = []

    # 当前数字
    current_number = 1

    # 遍历匹配到的所有行
    for i, (number, content) in enumerate(matches):
        if number == current_number:
            # 构建有序列表的格式
            ordered_list.append(f"{current_number}. {content.strip()}")
            current_number += 1
        else:
            # 如果数字不连续，则重新开始查找"(1)"
            ordered_list = []  # 清空已有的列表
            current_number = 1
            if number == 1:
                ordered_list.append(f"{current_number}. {content.strip()}")
                current_number += 1

    # 将列表转换为字符串
    return "\n\n".join(ordered_list)

def process_file(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as file:
        text = file.read()

    # 转换文本
    converted_text = convert_to_ordered_list(text)

    with open(output_file, 'w', encoding='utf-8') as file:
        file.write(converted_text)

# 指定输入和输出文件名
input_filename = r'D:\1STUDY\3-Resource\NBU\教材\目录\1.md'
output_filename = r'D:\1STUDY\3-Resource\NBU\教材\目录\2.md'

# 处理文件
process_file(input_filename, output_filename)
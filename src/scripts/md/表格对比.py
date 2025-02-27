import re

def read_file(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        return file.read()

def write_file(filename, content):
    with open(filename, 'w', encoding='utf-8') as file:
        file.write(content)

def split_tables(content):
    lines = content.split('\n')
    new_content = []
    in_table = False

    for i, line in enumerate(lines):
        if re.match(r'\|.*\|', line):  # Detects table rows
            if re.match(r'\|.*:\---:.*\|', line):  # Detects table header separator line
                if in_table:
                    new_content.append('')
                in_table = True
            new_content.append(line)
        else:
            in_table = False
            new_content.append(line)
    
    return '\n'.join(new_content)

def process_file(input_file, output_file):
    content = read_file(input_file)
    modified_content = split_tables(content)
    write_file(output_file, modified_content)

# 文件路径
input_file = r'D:\1STUDY\3-Resource\NBU\教材\目录\1.md'
output_file = r'D:\1STUDY\3-Resource\NBU\教材\目录\1.md'

# 处理文件，拆分错误连在一起的表格
process_file(input_file, output_file)

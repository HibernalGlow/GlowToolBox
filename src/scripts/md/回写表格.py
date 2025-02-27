import re

def read_file(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        return file.read()

def write_file(filename, content):
    with open(filename, 'w', encoding='utf-8') as file:
        file.write(content)

def replace_markers_with_tables(content, tables, markers):
    for marker, table in zip(markers, tables):
        content = content.replace(marker, table)
    return content

def insert_tables_into_file(input_file, output_file, tables_file):
    content = read_file(input_file)
    tables_content = read_file(tables_file)
    markers = re.findall(r'(🌟表格\d+🌟)', tables_content)
    tables = re.split(r'🌟表格\d+🌟\n', tables_content)[1:]
    new_content = replace_markers_with_tables(content, tables, markers)
    write_file(output_file, new_content)

# 文件路径
input_file = r'D:\1STUDY\3-Resource\NBU\教材\目录\updated_1.md'
output_file = r'D:\1STUDY\3-Resource\NBU\教材\目录\final_output1.md'
tables_file = r'D:\1STUDY\3-Resource\NBU\教材\目录\extracted_tables2.md'

# 将新表格写回原文
insert_tables_into_file(input_file, output_file, tables_file)

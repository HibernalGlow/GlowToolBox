import re

def read_file(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        return file.read()

def write_file(filename, content):
    with open(filename, 'w', encoding='utf-8') as file:
        file.write(content)

def generate_emoji_markers(n):
    base_emoji = "🌟表格"
    return [f"{base_emoji}{i+1}🌟" for i in range(n)]

def extract_tables(content, delete_tables=True):
    tables = []
    table_markers = []
    table_count = 0
    in_table = False
    table = []
    new_content = []

    lines = content.split('\n')
    for line in lines:
        if line.startswith('|'):
            if not in_table:
                in_table = True
                table_marker = f"🌟表格{table_count+1}🌟"
                table_count += 1
                table_markers.append(table_marker)
                if delete_tables:
                    new_content.append(table_marker)
            table.append(line)
        else:
            if in_table:
                tables.append('\n'.join(table))
                table = []
                in_table = False
            new_content.append(line)
    
    if table:
        tables.append('\n'.join(table))
    
    return '\n'.join(new_content), tables, table_markers

def extract_tables_from_file(input_file, output_file, tables_file, delete_tables=True):
    content = read_file(input_file)
    new_content, tables, table_markers = extract_tables(content, delete_tables)
    write_file(output_file, new_content)
    
    with open(tables_file, 'w', encoding='utf-8') as file:
        for marker, table in zip(table_markers, tables):
            file.write(f"{marker}\n{table}\n\n")

# 文件路径
input_file = r'D:\1STUDY\3-Resource\NBU\教材\目录\2.md'
output_file = r'D:\1STUDY\3-Resource\NBU\教材\目录\updated_21.md'
tables_file = r'D:\1STUDY\3-Resource\NBU\教材\目录\extracted_tables.md'

# 提取表格并留下Emoji标记符
extract_tables_from_file(input_file, output_file, tables_file, delete_tables=True)

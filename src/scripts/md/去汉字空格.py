import re

def remove_spaces_between_chinese_characters(text):
    def replacer(match):
        if match.group(1).startswith('#'):
            return match.group(0)
        else:
            pattern = re.compile(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])')
            return pattern.sub(r'\1\2', match.group(0))
    
    # 使用re.sub()，并在回调函数中进行替换
    modified_text = re.sub(r'(^.*$)', replacer, text, flags=re.MULTILINE)
    return modified_text

def read_file(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        return file.read()

def write_file(filename, content):
    with open(filename, 'w', encoding='utf-8') as file:
        file.write(content)

def process_file(input_file, output_file):
    content = read_file(input_file)
    modified_content = remove_spaces_between_chinese_characters(content)
    write_file(output_file, modified_content)

# 文件路径
input_file = r'D:\1STUDY\3-Resource\NBU\教材\目录\1.md'
output_file = r'D:\1STUDY\3-Resource\NBU\教材\目录\1.md'

# 处理文件，去掉中文汉字间的空格
process_file(input_file, output_file)



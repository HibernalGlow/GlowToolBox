def html_conversion_function():
    import re
    from lxml import etree
    
    def convert_html_table_to_markdown(html_table):
        # 解析 HTML 表格
        separator_added = True
        parser = etree.HTMLParser()
        try:
            root = etree.fromstring(html_table, parser)
        except etree.XMLSyntaxError as e:
            return f"解析HTML出错: {str(e)}"
        
        # 获取所有行
        all_trs = root.xpath('//tr')
        
        if all_trs:
            row_num = len(all_trs)
            col_num = 0
            
            # 计算最大列数
            for td in all_trs[0].xpath('./th|./td'):
                col_num += int(td.get('colspan', 1))
            
            # 创建一个二维列表来存放表格数据
            table_data = [['' for _ in range(col_num)] for _ in range(row_num)]
            
            # 用于填充合并单元格的字符串
            empty_data = '{: class=\'fn__none\'}'
            
            # 逐行解析表格
            for r in range(row_num):
                c = 0
                for td in all_trs[r].xpath('./th|./td'):
                    gap = 0
                    
                    row_span = int(td.get('rowspan', 1))
                    col_span = int(td.get('colspan', 1))
                    
                    # 使用 itertext() 获取文本内容
                    content = ''.join(td.itertext()).replace('\n', '<br />')
                    
                    # 确保不会超出当前行的边界
                    while c + gap < len(table_data[r]) and table_data[r][c + gap] == empty_data:
                        gap += 1
                    
                    if row_span == 1 and col_span == 1:
                        if c + gap < len(table_data[r]):
                            table_data[r][c + gap] = content
                    else:
                        for i in range(row_span):
                            for j in range(col_span):
                                if r + i < len(table_data) and c + gap + j < len(table_data[r + i]):
                                    table_data[r + i][c + gap + j] = empty_data
                        if c + gap < len(table_data[r]):
                            table_data[r][c + gap] = f"{{: colspan='{col_span}' rowspan='{row_span}'}}" + content
                    
                    c += gap + col_span
            
            # 将数组中的数据组合成 Markdown 表格模板
            template_str = ""
            for r in range(row_num):
                template_str += '|'
                for c in range(col_num):
                    template_str += ' ' + table_data[r][c] + ' |'
                template_str += '\n'
                
                # 添加分隔线在表头行之后或第一行之后
                if (r == 0 or (r == 1 and len(root.xpath('//thead/tr')) > 0)) and separator_added == True:
                    template_str += '|' + '|'.join([' :---: ' for _ in range(col_num)]) + '|\n'
                    separator_added = False
            
            return template_str
        else:
            return "未找到表格"

    def replace_html_tables_with_markdown(filename):
        with open(filename, 'r', encoding='utf-8') as file:
            content = file.read()
    
        # 查找所有的 HTML 表格
        html_tables = re.findall(r'<table.*?>.*?</table>', content, re.DOTALL)
    
        # 为每一个 HTML 表格生成 Markdown 表格并替换
        for html_table in html_tables:
            markdown_table = convert_html_table_to_markdown(html_table)
            content = content.replace(html_table, markdown_table)
    
        # 写入更新后的内容到文件
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(content)
    
    # 替换指定文件中的 HTML 表格
    filename = r'D:\1STUDY\3-Resource\NBU\教材\目录\1.md'
    replace_html_tables_with_markdown(filename)

def directory_replacement_function():
    import re
    
    # 定义你的文件路径
    file_path = r'D:\1STUDY\3-Resource\NBU\教材\目录\1.md'  # 或者 'path_to_your_file.txt'
    
    # 定义你的正则替换规则
    patterns_and_replacements = [
        # (r'^#{1,6} ',r''),
        (r'^ ',r''),
        # (r'\[\d+\]\(#.+?\)', ''),
        # (r'\d', ''),
        # (r'\\*', r''),#\\
        # (r'^.*?◎.*$\n?', r''),#删除包含某个字符
        # (r'\*', r''),#\*
        # (r'!\[+\]+(\(.*\))', r''),#替换图片
        # (r'((?<=\S|^)!\[.*?\]\(.*?\)(?=\S|$))', r'\1\n'),#图片+\n
        # (r'> ',r''),#替换引述
        # (r'>',r''),#替换引述
        (r'（',r'('),#替换引述
        (r'）',r')'),#替换引述
        (r'\|\n([^|])',r'|\n\n\1'),#表格最后一行加\n
        # (r'^\|(.*?)\|\|\|{1,99}',r'\n\1'),
        # (r'\[TABLE\]',r''),#替换\[TABLE\]
        #  --- ||
        # (r'^第([\u4e00-\u9fa5A-Za-z0-9]+)讲', r'# 第\1讲 '),
        # (r'^第([\u4e00-\u9fa5A-Za-z0-9]+)部分', r'# 🌟第\1部分'),
        # (r'^.*?目录.*$\n?', r'\n'),
        # (r'^第([\u4e00-\u9fa5A-Za-z0-9]+)章', r'# 第\1章 '),
        # (r'^第([\u4e00-\u9fa5A-Za-z0-9]+)节', r'## 第\1节 '),
        # (r'^专题([\u4e00-\u9fa5A-Za-z0-9]+)', r'# 专题\1 '),
        (r'^(一|二|三|四|五|六|七|八|九|十|十一|十二|十三|十四)、', r'### \1、'),
        (r'^\((一|二|三|四|五|六|七|八|九|十|十一|十二|十三|十四)\)',r'#### (\1) '),
        (r'^(\d+)\.',r'##### \1.'),
        (r'^序言',r'## 序言'),
        # (r'(^\(\d+\)[^()]*)',r'**\1**'),#u慎用，6级标题后(1)的小标题加粗
        # (r'#####\s*(\d+\.\s*.+)\n\n##### ',r'\1\n'),#用连续同级标题防漏
        # (r'####\s*(\((一|二|三|四|五|六|七|八|九)\)\s*.+)\n\n#### ',r'\1\n'),
    
        # (r'^(\d+)\.',r'\1. '),
        # 加空格.py
        # (r'^\((\d+)\)',r'\1. '),#(1)变列表
        # (r'(?<=\D)(\d+)\.',r'\n\n\1. '),#慎用，会影响表格和图片 非开头1.变列表
        # (r'(#{1,6} .*?。)',r'\1\n\n'),#慎用，每个标题行之后，首次出现的中文句号（。）处添加换行符
        # (r'(\n+)', r'\n\n'),
        
        # (r'([\u4e00-\u9fa5A-Za-z0-9]+)\n    ([\u4e00-\u9fa5A-Za-z0-9]+)', r'\1\2'),
        (r'(?:\r?\n){3,}', r'\n'),#连续3空行
        # (r'([\u4e00-\u9fa5A-Za-z0-9]+)#', r'\1\n\n#'),#连续3空行
        (r'章',r'章 '),
        (r'节',r'节 '),
        # (r'^.*微信.*$\n?',r'')#替换关键字◎行
        # 更多的模式和替换对...
        (r'\$\\rightarrow\$',r'→'),
        (r'\$\\leftarrow\$',r'←'),
        (r'^\[([\u4e00-\u9fa5A-Za-z0-9]+)\]',r'`[\1]`'),
        (r'\$=\$',r'='),
        (r'^第(一|二|三|四|五|六|七|八|九)',r'* 第\1'),
        (r'\n\n#',r'\n#'),
        (r'\]`\n{2,5}',r']`'),
        (r'\$\\mathrm\{([a-z])\}\$',r'\1'),
        # (r'\{[^{}]*id=[^{}]*\}',r''),
        # (r'\| :---: \|(\n\|.*\|$\n)\| :---: \|.*\|$\n',r'| :---: |\1'),#表格分割线多了
        
    ]
    
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    
    # 对文本进行正则替换
    for pattern, replacement in patterns_and_replacements:
        text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
    
    # 将替换后的内容写回文件（假设是原地替换）
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(text)
    # print(text)

def heading_adjustment_function():
    import re
    
    # 定义你的文件路径
    file_path = r'D:\1STUDY\3-Resource\NBU\教材\目录\1.md'  # 或者 'path_to_your_file.txt'
        
    def remove_adjacent_same_level_headers_from_file(input_file_path, output_file_path=None):
        if output_file_path is None:
            output_file_path = input_file_path
        
        with open(input_file_path, 'r', encoding='utf-8') as file:
            markdown_text = file.readlines()
        
        cleaned_markdown = strip_headers_between_adjacent_same_level(markdown_text)
        
        with open(output_file_path, 'w', encoding='utf-8') as file:
            file.writelines(cleaned_markdown)
    
    def strip_headers_between_adjacent_same_level(lines):
        cleaned_lines = []
        prev_level = 0
        prev_is_header = False
        blank_line_between = False
        consecutive_headers = []
    
        for i, line in enumerate(lines):
            if line.startswith('#'):
                current_level = len(line) - len(line.lstrip('#'))
                if current_level == 1:
                    # 处理一级标题，不进行处理
                    cleaned_lines.append(line)
                    prev_is_header = True
                    prev_level = current_level
                    consecutive_headers = []
                    continue
                
                if prev_is_header and current_level == prev_level and (not blank_line_between or consecutive_headers):
                    # 将当前标题添加到连续标题列表
                    consecutive_headers.append(len(cleaned_lines))
                else:
                    # 处理连续的同级标题
                    if len(consecutive_headers) > 1:
                        for index in consecutive_headers:
                            cleaned_lines[index] = cleaned_lines[index].lstrip('#').lstrip()
                    consecutive_headers = [len(cleaned_lines)]
                    prev_is_header = True
                    prev_level = current_level
                blank_line_between = False
            else:
                if line.strip() == '':
                    blank_line_between = True
                else:
                    blank_line_between = False
                    # 处理连续的同级标题
                    if len(consecutive_headers) > 1:
                        for index in consecutive_headers:
                            cleaned_lines[index] = cleaned_lines[index].lstrip('#').lstrip()
                    consecutive_headers = []
                prev_is_header = False
            
            cleaned_lines.append(line)
        
        # 最后检查一次是否有未处理的连续标题
        if len(consecutive_headers) > 1:
            for index in consecutive_headers:
                cleaned_lines[index] = cleaned_lines[index].lstrip('#').lstrip()
    
        return cleaned_lines
    
    # 示例文件路径
    input_md_path = r'D:\1STUDY\3-Resource\NBU\教材\目录\1.md'
    output_md_path = '1.md'
    
    
    remove_adjacent_same_level_headers_from_file(input_md_path, output_md_path)
    
    # 定义你的正则替换规则
    patterns_and_replacements = [
        (r'(#{1,6} .*?。)',r'\1\n\n'),#每个标题行之后，首次出现的中文句号（。）处添加换行符
        # (r'^(\d+)\.',r'\1. '),
        
    ]
    file_path = r'D:\1STUDY\3-Resource\NBU\教材\目录\1.md'
    
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    
    # 对文本进行正则替换
    for pattern, replacement in patterns_and_replacements:
        text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
    
    # 将替换后的内容写回文件（假设是原地替换）
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(text)


def space_removal_function():
    
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


def main():
    if ENABLE_HTML_CONVERSION:
        html_conversion_function()

    if ENABLE_DIRECTORY_REPLACEMENT:
        directory_replacement_function()

    if ENABLE_HEADING_ADJUSTMENT:
        heading_adjustment_function()

    if ENABLE_SPACE_REMOVAL:
        space_removal_function()

if __name__ == "__main__":
    ENABLE_HTML_CONVERSION = True
    ENABLE_DIRECTORY_REPLACEMENT = True
    ENABLE_HEADING_ADJUSTMENT = True
    ENABLE_SPACE_REMOVAL = True

    main()

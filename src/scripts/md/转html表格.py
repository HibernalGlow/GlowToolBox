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
                template_str += '|' + '|'.join([' --- ' for _ in range(col_num)]) + '|\n'
                separator_added = False
        
        return template_str
    else:
        return "未找到表格"

def replace_html_tables_with_markdown(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # 替换HTML标签
    content = content.replace('</body></html>', '').replace('<html><body>', '')

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

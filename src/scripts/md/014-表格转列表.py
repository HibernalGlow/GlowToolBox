import re

def markdown_to_list(markdown):
    # 使用正则表达式匹配表格的每一行
    rows = re.findall(r'\|(.*)\|', markdown)
    
    # 获取表头和表体
    header = rows[0].strip().split('|')
    data = [row.strip().split('|') for row in rows[2:]]
    
    # 将表头和表体合并为一个List
    result = [header] + data
    
    return result
markdown = """
| 姓名 | 年龄 | 性别 |
| ---- | ---- | ---- |
| 张三 | 20   | 男   |
| 李四 | 21   | 女   |
"""
print(markdown_to_list(markdown))
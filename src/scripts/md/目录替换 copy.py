import re

# 定义你的文件路径
file_path = r'D:\1STUDY\3-Resource\NBU\教材\目录\1.md'  # 或者 'path_to_your_file.txt'

# 定义你的正则替换规则
patterns_and_replacements = [
    # (r'^#{1,6} ',r''),
    (r'^ ',r''),
    (r'(\d)\s+([\u4e00-\u9fa5])',r'\1\2'),
    (r'([\u4e00-\u9fa5])\s+(\d)',r'\1\2'),
    (r'(\d)\s+(\d)',r'\1\2'),
    (r'([\u4e00-\u9fa5])\s+([\u4e00-\u9fa5])',r'\1\2'),#汉字内空格

    # (r'\[\d+\]\(#.+?\)', ''),
    # (r'\d', ''),
    # (r'\\*', r''),#\\
    # (r'^.*?目录.*$\n?', r''),#删除包含某个字符
    # (r'\*', r''),#\*
    # (r'!\[+\]+(\(.*\))', r''),#替换图片
    # (r'((?<=\S|^)!\[.*?\]\(.*?\)(?=\S|$))', r'\1\n'),#图片+\n
    # (r'> ',r''),#替换引述
    # (r'>',r''),#替换引述
    (r'（',r'('),#替换引述
    (r'）',r')'),#替换引述
    (r'</body></html> ',r''),
    (r'<html><body>',r''),
    (r'「',r'['),
    (r'」',r']'),
    (r'【',r'['),
    (r'】',r']'),
    

    (r'\|\n([^|])',r'|\n\n\1'),#表格最后一行加\n
    (r'^\|(.*?)\|\|\|{1,99}',r'\n\1'),
    # (r'\[TABLE\]',r''),#替换\[TABLE\]
    #  --- ||
    # (r'^第([\u4e00-\u9fa5A-Za-z0-9]+)讲', r'# 第\1讲 '),
    # (r'^第([\u4e00-\u9fa5A-Za-z0-9]+)部分', r'# 🌟第\1部分'),
    # (r'^.*?目录.*$\n?', r'\n'),
    # (r'^第([\u4e00-\u9fa5A-Za-z0-9]+)章', r'# 第\1章 '),
    # (r'^第([\u4e00-\u9fa5A-Za-z0-9]+)编', r'# 第\1编 '),
    (r'^第([\u4e00-\u9fa5A-Za-z0-9]+)节', r'## 第\1节 '),
    (r'^第([\u4e00-\u9fa5A-Za-z0-9]+)类', r'## 第\1类 '),
    # (r'^专题([\u4e00-\u9fa5A-Za-z0-9]+)', r'# 专题\1 '),
    # (r'^(一|二|三|四|五|六|七|八|九|十|十一|十二|十三|十四)、', r'### \1、'),
    # (r'^\((一|二|三|四|五|六|七|八|九|十|十一|十二|十三|十四)\)',r'#### (\1) '),
    # (r'^(\d)\.',r'#### \1.'),
    # (r'^序言',r'## 序言'),
    # (r'(^\(\d+\)[^()]*)',r'**\1**'),#u慎用，6级标题后(1)的小标题加粗
    # (r'#####\s*(\d+\.\s*.+)\n\n##### ',r'\1\n'),#用连续同级标题防漏
    # (r'####\s*(\((一|二|三|四|五|六|七|八|九)\)\s*.+)\n\n#### ',r'\1\n'),
    (r'(# .*)(\d\.)', r'\1\n\n\2 '),
    
    # (r'^(\d+)\.',r'\1. '),
    # 加空格.py
    # (r'^\((\d+)\)',r'\1. '),#(1)变列表
    # (r'(?<=\D)(\d+)\.',r'\n\n\1. '),#慎用，会影响表格和图片 非开头1.变列表
    # (r'(#{1,6} .*?。)',r'\1\n\n'),#慎用，每个标题行之后，首次出现的中文句号（。）处添加换行符
    # (r'(\n+)', r'\n\n'),
    
    # (r'([\u4e00-\u9fa5A-Za-z0-9]+)\n    ([\u4e00-\u9fa5A-Za-z0-9]+)', r'\1\2'),
    (r'(?:\r?\n){3,}', r'\n'),#连续3空行
    # (r'([\u4e00-\u9fa5A-Za-z0-9]+)#', r'\1\n\n#'),#连续3空行
    # (r'章',r'章 '),
    # (r'节',r'节 '),
    # (r'^.*微信.*$\n?',r'')#替换关键字◎行
    # 更多的模式和替换对...
    # (r'\$\\rightarrow\$',r'→'),
    # (r'\$\\leftarrow\$',r'←'),
    # (r'^\[([\u4e00-\u9fa5A-Za-z0-9]+)\]',r'`[\1]`'),
    # (r'\$=\$',r'='),
    # (r'^第(一|二|三|四|五|六|七|八|九)',r'* 第\1'),
    # (r'\n\n#',r'\n#'),
    # (r'\]`\n{2,5}',r']`'),
    # (r'\$\\mathrm\{([a-z])\}\$',r'\1'),
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
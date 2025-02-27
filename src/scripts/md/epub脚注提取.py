import os
from ebooklib import epub
from bs4 import BeautifulSoup
import re

# 预处理 Markdown 文件内容（替换1）
def re1(md_path):
    # 定义正则替换规则
    patterns_and_replacements = [
        (r'#w', r'￥￥'),  # 临时替换规则
    ]
    
    # 读取文件内容
    with open(md_path, 'r', encoding='utf-8') as file:
        text = file.read()
    
    # 对文本进行正则替换
    for pattern, replacement in patterns_and_replacements:
        text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
    
    # 将替换后的内容写回文件
    with open(md_path, 'w', encoding='utf-8') as file:
        file.write(text)

def extract_html_from_epub(epub_path):
    """提取 EPUB 文件中的 HTML 内容"""
    book = epub.read_epub(epub_path)
    html_content = {}
    
    for item in book.items:
        if isinstance(item, epub.EpubHtml):
            html_content[item.get_id()] = item.content.decode('utf-8')
    
    return html_content

def get_anchor_content(html_content, anchor_id):
    """查找 HTML 内容中锚点的内容"""
    for content in html_content.values():
        soup = BeautifulSoup(content, 'html.parser')
        anchor = soup.find(id=anchor_id)
        if anchor:
            return str(anchor.find_next_sibling())
    return None

def replace_links_in_md(md_path, html_content):
    """在 Markdown 文件中替换链接"""
    with open(md_path, 'r', encoding='utf-8') as md_file:
        md_text = md_file.read()
    
    # 查找所有的链接
    pattern = re.compile(r'#([\w\.]+)#([\w\.]+)')
    
    def replacement(match):
        html_file = match.group(1)
        anchor_id = match.group(2)
        anchor_content = get_anchor_content(html_content, anchor_id)
        if anchor_content:
            return anchor_content
        return match.group(0)
    
    # 替换 Markdown 中的链接
    new_md_text = pattern.sub(replacement, md_text)
    
    with open(md_path, 'w', encoding='utf-8') as md_file:
        md_file.write(new_md_text)

# 恢复 Markdown 文件内容（替换2）
def re2(md_path):
    # 定义正则替换规则
    patterns_and_replacements = [
        (r'￥￥', r'#w'),  # 恢复规则
    ]
    
    # 读取文件内容
    with open(md_path, 'r', encoding='utf-8') as file:
        text = file.read()
    
    # 对文本进行正则替换
    for pattern, replacement in patterns_and_replacements:
        text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
    
    # 将恢复后的内容写回文件
    with open(md_path, 'w', encoding='utf-8') as file:
        file.write(text)

def main(md_path, epub_path):
    """主函数"""
    # 预处理 Markdown 文件内容
    re1(md_path)
    
    # 提取 EPUB 文件中的 HTML 内容
    html_content = extract_html_from_epub(epub_path)
    
    # 替换 Markdown 文件中的链接
    replace_links_in_md(md_path, html_content)
    
    # 恢复 Markdown 文件内容
    re2(md_path)

if __name__ == '__main__':
    md_path = '2.md'
    epub_path = r"D:\1STUDY\3-Resource\Publish\法学论文写作 -- 何海波 [何海波] -- 2014 -- 北京大学出版社 -- 7301238258 -- f0de58ec371828f5a754a3a7cc966edd -- Anna’s Archive.epub"
    
    main(md_path, epub_path)

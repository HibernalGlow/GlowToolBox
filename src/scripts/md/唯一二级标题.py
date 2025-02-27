def remove_duplicate_markdown_headers(input_file, output_file):
    seen_titles = set()
    with open(input_file, 'r', encoding='utf-8') as infile:
        lines = infile.readlines()
    
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for line in lines:
            # 检查是否为以两个井号开头的标题行
            if line.startswith('#'):
                # 提取标题的纯文本部分（去除井号和前后空白）
                title_text = line.lstrip('#').strip()
                # 如果该标题尚未出现过，则写入文件并记录
                if title_text not in seen_titles:
                    seen_titles.add(title_text)
                    outfile.write(line)
            else:
                # 对于非标题行，直接写入输出文件
                outfile.write(line)

# 使用函数
input_file = r"D:\\1STUDY\\3-Resource\\NBU\\教材\\目录\\1.md"  # 输入文件名
output_file = '1.md'  # 输出文件名，包含唯一二级标题
remove_duplicate_markdown_headers(input_file, output_file)
import re

def replace_markdown_links(file_path):
    print(f"读取文件: {file_path}")
    
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    print("文件内容读取完成。")

    # 正则匹配所有 a 链接形式的 [[数字]](<a href="partXXXX.html#w数字">[数字]</a>) 链接
    a_links = re.findall(r'(\[\[\d+\]\]\(<a href="part\d+_split_\d+\.html#w\d+">.+?</a>\))', content)
    
    # 正则匹配所有的 [[数字]](#partXXXX.html#w数字) 文献引用
    w_links_with_citation = re.findall(r'(\[\[\d+\]\]\(#part\d+_split_\d+\.html#w\d+\))\s+(.+)', content)

    print(f"找到 {len(a_links)} 个 <a> 链接。")
    print(f"找到 {len(w_links_with_citation)} 个 #w 链接和引用。")

    # 存储更新后的内容
    updated_content = content

    # 替换逻辑：对于每个 <a> 链接，找到对应的 #w 链接和其后的引用文本
    for a_link in a_links:
        for w_link, citation in w_links_with_citation:
            # 如果编号相同，链接路径相同，替换为带有文献引用的格式
            if re.search(r'\[\[(\d+)\]\]', a_link).group(1) == re.search(r'\[\[(\d+)\]\]', w_link).group(1):
                # 提取链接编号以保留
                link_number = re.search(r'\[\[\d+\]\]', a_link).group(0)
                link_url = re.search(r'\(#part\d+_split_\d+\.html#w\d+\)', w_link).group(0)
                # 生成新的替换内容
                new_link = f"{link_number}({citation} \"{link_url[1:-1]}\")"
                print(f"将 {a_link} 替换为 {new_link}")
                
                # 替换原始内容中的第一个 <a> 链接
                updated_content = updated_content.replace(a_link, new_link, 1)
                break

    # 写入更新后的文件
    updated_file_path = f'updated_{file_path}'
    print(f"写入更新后的文件: {updated_file_path}")
    with open(updated_file_path, 'w', encoding='utf-8') as updated_file:
        updated_file.write(updated_content)

    print("文件写入完成。")

# 调用函数处理文件
replace_markdown_links('2.md')

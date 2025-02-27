import re
import os

def get_subtitle(content):
    # 从md文件中获取以 # 🌟 开头的标题
    # 返回标题和对应的索引
    pattern = re.compile(r'# 🌟(.*?)\n')
    matches = list(pattern.finditer(content))
    subtitle = [match.group(1).strip() for match in matches]
    indexes = [match.start() for match in matches]
    indexes.append(len(content))  # 添加文件末尾索引
    return subtitle, indexes

def save_md(path, article):
    # 保存分割后的文件
    with open(path, 'w', encoding='utf8') as f:
        f.write(article)

def safe_filename(filename):
    # 确保文件名合法
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def split_and_save_md(filepath, savepath):
    with open(filepath, 'r', encoding='utf8') as f:
        content = f.read()
    
    # 确保目标文件夹存在
    try:
        os.makedirs(savepath, exist_ok=True)
    except OSError as e:
        print(f"创建目录时出错：{e}")
        return
    
    sub_title, indexes = get_subtitle(content)
    
    for i in range(len(sub_title)):
        safe_title = safe_filename(sub_title[i])
        article_path = os.path.join(savepath, f'{safe_title}.md')
        
        if os.path.exists(article_path):
            print(f"文件已存在，跳过：{article_path}")
            continue
        
        article = content[indexes[i]:indexes[i+1]]
        save_md(article_path, article)
        print(f"文件已保存：{article_path}")

# 原始文件所在目录
filepath = r'D:\1STUDY\3-Resource\NBU\教材\目录\1.md'
# 拆分后文件所在目录，为了方便，需要新建一个文件夹
savepath = '拆分'

# 执行拆分命令
split_and_save_md(filepath, savepath)

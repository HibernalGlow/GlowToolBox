import re
import os
import warnings
warnings.filterwarnings('ignore')

def get_subtitle(content, level=1):
    # 从md文件中获取标题和位置
    pattern = re.compile(f'^#{{{level}}} (.+)$', re.MULTILINE)
    matches = list(pattern.finditer(content))
    
    if not matches:
        return [], []
        
    # 获取标题和位置
    titles = [m.group(1).strip() for m in matches]
    positions = [m.start() for m in matches]
    positions.append(len(content))
    
    return titles, positions

def save_md(path, article):
    # 保存分割后的文件
    with open(path, 'w+', encoding='utf8') as f:
        f.write(article)

def split_by_h2(content, savepath, h1_title):
    # 按二级标题拆分内容
    h2_titles, h2_positions = get_subtitle(content, 2)
    
    if not h2_titles:  # 如果没有二级标题，返回False
        return False
    
    # 创建一级标题文件夹
    h1_folder = os.path.join(savepath, h1_title)
    if not os.path.exists(h1_folder):
        os.makedirs(h1_folder)
    
    # 处理每个二级标题
    for i in range(len(h2_titles)):
        number_prefix = str(i + 1).zfill(3)
        article_path = os.path.join(h1_folder, f'{number_prefix}_{h2_titles[i]}.md')
        
        if os.path.exists(article_path):
            continue
        
        # 获取内容范围
        start_pos = h2_positions[i]
        end_pos = h2_positions[i + 1] if i + 1 < len(h2_positions) else len(content)
        article = content[start_pos:end_pos].strip()
        
        # 确保文章内容不为空
        if article:
            save_md(article_path, article)
    
    return True

def split_and_save_md(filepath, savepath):
    file_path, fullflname = os.path.split(filepath)
    fname, ext = os.path.splitext(fullflname)
    
    # 读取文件内容
    with open(filepath, 'r', encoding='utf8') as f:
        content = f.read()
    
    if not os.path.exists(savepath):
        os.makedirs(savepath)
    
    # 获取一级标题
    h1_titles, h1_positions = get_subtitle(content, 1)
    
    if not h1_titles:
        print(f"警告：在文件 {filepath} 中未找到一级标题！")
        return
    
    # 处理每个一级标题
    for i in range(len(h1_titles)):
        number_prefix = str(i + 1).zfill(3)
        h1_title = h1_titles[i]
        
        # 获取当前一级标题的内容
        start_pos = h1_positions[i]
        end_pos = h1_positions[i + 1] if i + 1 < len(h1_positions) else len(content)
        article = content[start_pos:end_pos].strip()
        
        if not article:  # 跳过空内容
            continue
        
        # 检查内容长度
        if len(article) > 100000:  # 如果超过10万字
            # 尝试按二级标题拆分
            if not split_by_h2(article, savepath, h1_title):
                # 如果没有二级标题，保存为一级标题文件
                article_path = os.path.join(savepath, f'{number_prefix}_{fname}_{h1_title}.md')
                if not os.path.exists(article_path):
                    save_md(article_path, article)
        else:
            # 保存为一级标题文件
            article_path = os.path.join(savepath, f'{number_prefix}_{fname}_{h1_title}.md')
            if not os.path.exists(article_path):
                save_md(article_path, article)

def combine_md(filepath, savepath):
    file_path, fullflname = os.path.split(filepath)
    fname, ext = os.path.splitext(fullflname)
    
    # 获取所有文件和文件夹
    items = sorted(os.listdir(savepath))
    contents = []
    
    for item in items:
        item_path = os.path.join(savepath, item)
        if os.path.isdir(item_path):  # 如果是文件夹（二级标题）
            # 获取并排序文件夹中的所有md文件
            folder_files = sorted([f for f in os.listdir(item_path) if f.endswith('.md')])
            for md_file in folder_files:
                with open(os.path.join(item_path, md_file), 'r', encoding='utf-8') as f:
                    contents.append(f.read() + "\n")
        elif item.endswith('.md') and item != f"{fname}.md":  # 如果是md文件（一级标题）
            with open(item_path, 'r', encoding='utf-8') as f:
                contents.append(f.read() + "\n")
    
    # 保存合并后的文件
    output_path = os.path.join(savepath, f"{fname}.md")
    with open(output_path, "w", encoding='utf-8') as f:
        f.writelines(contents)

# 使用示例
if __name__ == "__main__":
    filepath = r"D:\\1STUDY\\3-Resource\\NBU\\教材\\目录\\1.md"
    savepath = r"D:\\1STUDY\\3-Resource\\NBU\\教材\\目录\\拆分"
    split_and_save_md(filepath, savepath)
    # combine_md(filepath, savepath)
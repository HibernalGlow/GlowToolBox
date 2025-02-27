from os.path import basename
import re
import os
from urllib.parse import quote
import warnings
warnings.filterwarnings('ignore')

def get_subtitle(content):
    # 从md文件中获取h1标题
    # 返回日期和索引
    pattern = re.compile(r'#{1}(.*?)\n')#正则表达
    heads = pattern.findall(content)
    # print(heads)
    # 防止出现空h1标题
    subtitle = [h[1:] for h in heads if h[0] == ' ' and len(h) > 2]#以井号开头
    indexes = [content.find(title+'\n')-2 for title in subtitle]
    indexes.append(len(content))
    return subtitle, indexes

def save_md(path, article):
    # 保存分割后的文件
    with open(path, 'w+', encoding='utf8') as f:
        f.write(article)

def split_and_save_md(filepath,savepath):
    file_path,fullflname = os.path.split(filepath)
    fname,ext = os.path.splitext(fullflname)
    with open(filepath, 'r+', encoding='utf8') as f:
        content = f.read()
        if not os.path.exists(savepath):
            os.mkdir(savepath)
        sub_title, indexes = get_subtitle(content)
        for i in range(len(sub_title)):
            # 添加三位数序号前缀
            number_prefix = str(i + 1).zfill(3)
            article_path = savepath+'/'+number_prefix+'_'+fname+'_'+sub_title[i]+'.md'
            if os.path.exists(article_path):
                continue
            article = content[indexes[i]:indexes[i+1]]
            save_md(article_path, article)
# 再定义一个合并文件的

# 合并的代码
def combine_md(filepath,savepath):
    md_list = os.listdir(savepath)#列出保存路径下所有的md文件
    file_path,fullflname = os.path.split(filepath)
    fname,ext = os.path.splitext(fullflname)
    fname_split=fname+'_'
    contents = []
    for md in md_list:
        if fname_split in md:
            md_file =savepath + '\\' + md
            with open(md_file, 'r', encoding='utf-8') as file:
                contents.append(file.read() + "\n")
    #构造输出路径
    output_path=savepath+'\\'+fname+'.md'
    with open(output_path,"w", encoding='utf-8') as file:
        file.writelines(contents)


#拆分成小部分，更好查看,原始文件所在目录
filepath=r"D:\\1STUDY\\3-Resource\\NBU\\教材\\目录\\1.md"
#拆分后文件所在目录，为了方便，需要新建一个文件夹
savepath=r"D:\\1STUDY\\3-Resource\\NBU\\教材\\目录\\拆分"
#执行拆分命令
split_and_save_md(filepath,savepath)
#执行合并命令
# combine_md(filepath,savepath)
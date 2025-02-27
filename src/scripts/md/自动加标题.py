import re
import cn2an

def fix_missing_chapter_titles(content):
    # 将内容按行分割
    lines = content.split('\n')
    # 存储当前章节号
    current_chapter = 0
    # 存储上一个节的信息
    last_section = None
    # 存储修改后的内容
    result = []
    
    # 匹配一级标题的正则表达式（如：# 第四章）
    chapter_pattern = re.compile(r'^#\s*第([一二三四五六七八九十百千万亿]+)章')
    # 匹配二级标题的正则表达式（如：## 第一节）
    section_pattern = re.compile(r'^##\s*第([一二三四五六七八九十百千万亿]+)节')
    
    for line in lines:
        # 检查是否是章标题
        chapter_match = chapter_pattern.match(line)
        if chapter_match:
            try:
                current_chapter = cn2an.cn2an(chapter_match.group(1))
                last_section = None
            except Exception as e:
                print(f"转换章节号时出错：{e}")
            result.append(line)
            continue
            
        # 检查是否是节标题
        section_match = section_pattern.match(line)
        if section_match:
            try:
                current_section = cn2an.cn2an(section_match.group(1))
                
                # 如果发现相同的节号，且没有新的章标题
                if last_section == current_section:
                    current_chapter += 1
                    # 添加缺失的章标题
                    result.append(f'# 第{cn2an.an2cn(current_chapter)}章')
                    last_section = None
                else:
                    last_section = current_section
            except Exception as e:
                print(f"转换节号时出错：{e}")
                
        result.append(line)
    
    return '\n'.join(result)

def main():
    # 读取输入文件
    try:
        with open('1.md', 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 处理内容
        fixed_content = fix_missing_chapter_titles(content)
        
        # 写入输出文件
        with open('output.md', 'w', encoding='utf-8') as f:
            f.write(fixed_content)
            
        print("处理完成！结果已保存到 output.md")
    except Exception as e:
        print(f"发生错误：{str(e)}")

if __name__ == '__main__':
    main()
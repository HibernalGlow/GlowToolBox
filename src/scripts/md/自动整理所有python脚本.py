import os

def convert_to_markdown(root_dir):
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # 检查当前目录下是否有.py文件
        has_py_files = any(filename.endswith('.py') for filename in filenames)
        
        if has_py_files:
            # 生成Markdown标题
            markdown_title = dirpath.replace(root_dir, '').replace(os.sep, '/')
            if markdown_title:
                markdown_title = f"## {markdown_title}\n\n"
            else:
                markdown_title = "## Root Directory\n\n"
            
            # 遍历当前目录下的所有文件
            for filename in filenames:
                if filename.endswith('.py'):
                    with open(os.path.join(dirpath, filename), 'r', encoding='utf-8') as file:
                        content = file.read()
                    markdown_title += f"### {filename}\n\n```python\n{content}\n```\n\n"
            
            # 输出到Markdown文件
            output_filename = os.path.join(root_dir, '1output.md')
            with open(output_filename, 'a', encoding='utf-8') as output_file:
                output_file.write(markdown_title)

# 示例调用
convert_to_markdown(r'D:\1STUDY\3-Resource\NBU\教材\目录')

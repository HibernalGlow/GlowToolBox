import difflib

def compare_texts(text1, text2):
    # 将文本分割成行
    lines1 = text1.splitlines()
    lines2 = text2.splitlines()
    
    # 使用difflib的unified_diff方法来获取差异
    diff = difflib.unified_diff(lines1, lines2, lineterm='')
    
    # 输出差异行
    for line in diff:
        print(line)

# 示例文本
text1 = """

"""
text2 = """

"""

compare_texts(text1, text2)
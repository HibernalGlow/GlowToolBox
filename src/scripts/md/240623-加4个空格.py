# 读取文件并处理内容
def process_file(input_file_path, output_file_path):
    with open(input_file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    # 处理每一行
    processed_lines = []
    for line in lines:
        # 新增条件检查行首是否已有4个空格
        if not (line.startswith('    ') or line.startswith('#') or line[0].isdigit()):
            processed_lines.append('    ' + line)  # 添加4个空格
        else:
            processed_lines.append(line)
    
    # 写入新文件
    with open(output_file_path, 'w', encoding='utf-8') as file:
        file.writelines(processed_lines)

# 示例用法
input_file_path = r'D:\1STUDY\3-Resource\NBU\教材\目录\1.md'  # 指定你的输入文件路径
output_file_path = '2.md'  # 为了避免覆盖原文件，建议修改输出文件名

process_file(input_file_path, output_file_path)
print("处理完成，结果已保存至", output_file_path)
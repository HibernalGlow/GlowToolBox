def remove_duplicate_lines(content, window_size=10):
    # 按行分割内容
    lines = content.split('\n')
    
    # 使用滑动窗口去重
    result_lines = []
    for i in range(len(lines)):
        current_line = lines[i]
        
        # 获取当前行前后window_size范围内的行
        start = max(0, i - window_size)
        end = min(len(lines), i + window_size + 1)
        window = lines[start:i] + lines[i+1:end]
        
        # 如果当前行为空或在窗口范围内未重复,则保留
        if not current_line or current_line not in window:
            result_lines.append(current_line)
            
    # 重新组合成字符串
    return '\n'.join(result_lines)

if __name__ == '__main__':
    # 读取文件
    with open('1.md', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 在10行范围内去重
    deduped_content = remove_duplicate_lines(content, window_size=10)
    
    # 写回文件
    with open('1.md', 'w', encoding='utf-8') as f:
        f.write(deduped_content) 
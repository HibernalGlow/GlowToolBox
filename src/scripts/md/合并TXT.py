import os
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def merge_txt_files(directory_path, output_file):
    # 计算总文件数
    total_files = sum(1 for _ in os.listdir(directory_path) if _.endswith(('.txt', '.srt')))
    processed_files = 0
    
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for filename in os.listdir(directory_path):
            if filename.endswith(('.txt', '.srt')):
                file_path = os.path.join(directory_path, filename)
                
                # 更新进度
                processed_files += 1
                progress = (processed_files / total_files) * 100
                logging.info(f"正在处理文件 {filename} ({progress:.2f}% 完成)")
                
                with open(file_path, 'r', encoding='utf-8') as infile:
                    # 使用文件名作为一级标题
                    title = os.path.splitext(filename)[0]
                    content = infile.read()
                    outfile.write(f"# {title}\n\n")
                    outfile.write(content)
                    outfile.write("\n\n")

if __name__ == "__main__":
    directory_path = input("请输入路径: ").strip().strip('"')  # 请替换为实际路径
    output_file = '合并.md'
    
    # 开始合并文件并记录日志
    logging.info("开始合并文件...")
    merge_txt_files(directory_path, output_file)
    logging.info("文件合并完成！")
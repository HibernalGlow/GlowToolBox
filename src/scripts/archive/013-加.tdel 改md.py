import os
import logging

# 配置日志
logging.basicConfig(filename='tdel_generation.log', level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def generate_tdel_files():
    base_path = input("请输入要处理的路径: ")
    
    if not os.path.exists(base_path):
        logging.error(f"路径不存在: {base_path}")
        return

    logging.debug(f"开始处理路径: {base_path}")

    # 遍历给定路径下的所有一级文件夹
    for folder_name in os.listdir(base_path):
        folder_path = os.path.join(base_path, folder_name)
        
        # 检查是否为文件夹
        if os.path.isdir(folder_path):
            txt_file_path = os.path.join(folder_path, f"{folder_name}.txt")
            tdel_file_path = os.path.join(folder_path, f"{folder_name}.md")
            logging.debug(f"处理文件夹: {folder_path}")

            try:
                # 先创建 .txt 文件
                with open(txt_file_path, 'w', encoding='utf-8') as txt_file:
                    logging.info(f"创建 .txt 文件: {txt_file_path}")
                    
                    # 写入文件路径
                    for root, _, files in os.walk(folder_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            txt_file.write(file_path + '\n')
                
                # 重命名 .txt 文件为 .artistdel 文件
                os.rename(txt_file_path, tdel_file_path)
                logging.info(f"成功重命名为: {tdel_file_path}")
            except Exception as e:
                logging.error(f"生成失败: {tdel_file_path} - 错误: {e}")
        else:
            logging.debug(f"跳过非文件夹: {folder_path}")

# 调用函数
generate_tdel_files()
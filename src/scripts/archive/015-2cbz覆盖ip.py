import os
from send2trash import send2trash

def rename_cbz_to_zip(directory, skip_existing=True):
    # 使用 os.walk 遍历目录及其所有子目录
    for root, dirs, files in os.walk(directory):
        for filename in files:
            # 检查文件是否以.cbz结尾（不区分大小写）
            if filename.lower().endswith('.cbz'):
                # 构建原始文件的完整路径
                old_path = os.path.join(root, filename)
                # 构建新文件名（将.cbz替换为.zip）
                new_filename = filename[:-4] + '.zip'
                # 构建新文件的完整路径
                new_path = os.path.join(root, new_filename)
                
                # 检查是否存在同名zip文件
                if os.path.exists(new_path):
                    if skip_existing:
                        print(f'跳过已存在的文件: {new_path}')
                        continue
                    else:
                        print(f'移动已存在的文件到回收站: {new_path}')
                        try:
                            send2trash(new_path)  # 将文件移动到回收站
                        except Exception as e:
                            print(f'移动文件到回收站时出错 {new_path}: {str(e)}')
                            continue
                
                try:
                    # 重命名文件
                    os.rename(old_path, new_path)
                    print(f'已重命名: {old_path} -> {new_path}')
                except Exception as e:
                    print(f'重命名 {old_path} 时出错: {str(e)}')

# 使用示例
directory = input("请输入目标目录路径: ")  # 替换为实际的文件夹路径
# 设置 skip_existing=True 跳过已存在的文件，设置 False 则覆盖
rename_cbz_to_zip(directory, skip_existing=False)
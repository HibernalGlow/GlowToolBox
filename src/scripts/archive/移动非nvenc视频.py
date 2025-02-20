import os
import shutil

def move_video_files_without_keywords(source_dir, target_dir, keywords, video_extensions):
    """
    移动给定路径下不包含指定关键词的视频文件到另一目录，并完整复制文件夹结构。

    参数:
    source_dir -- 源目录路径
    target_dir -- 目标目录路径
    keywords -- 关键字列表
    video_extensions -- 视频文件扩展名列表
    """
    # 确保目标目录存在
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    for root, dirs, files in os.walk(source_dir):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, source_dir)
            target_file_path = os.path.join(target_dir, relative_path)

            # 检查文件是否是视频文件
            if any(file.lower().endswith(ext) for ext in video_extensions):
                # 检查文件名是否包含任何关键字
                if not any(keyword in file for keyword in keywords):
                    # 确保目标文件夹存在
                    target_folder = os.path.dirname(target_file_path)
                    if not os.path.exists(target_folder):
                        os.makedirs(target_folder)

                    try:
                        shutil.move(file_path, target_file_path)
                        print(f"Moved file: {file_path} to {target_file_path}")
                    except Exception as e:
                        print(f"Error moving file {file_path}: {e}")

def main():
    source_dir = input("请输入源目录路径: ")
    target_dir = input("请输入目标目录路径: ")

    # 内置的视频文件扩展名列表
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.mpeg', '.mpg']

    # 内置的关键字列表
    keywords = ['＆']

    move_video_files_without_keywords(source_dir, target_dir, keywords, video_extensions)

if __name__ == "__main__":
    main()
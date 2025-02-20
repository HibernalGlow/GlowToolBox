import shutil
import os

def move_directories():
    # 获取用户输入的源目录
    print("请输入源目录路径（用换行符分隔多个路径），输入空行结束:")
    source_dirs = []
    while True:
        try:
            source_dir = input().strip().strip('"')
            if not source_dir:
                break
            source_dirs.append(source_dir)
        except EOFError:
            break

    # 定义目标目录
    destination_dir = r"E:\9EHV"

    # 遍历每个源目录
    for source_dir in source_dirs:
        # 检查目录是否存在
        if not os.path.exists(source_dir):
            print(f"目录不存在: {source_dir}")
            continue
        
        # 获取目录名称
        dir_name = os.path.basename(source_dir)
        destination_path = os.path.join(destination_dir, dir_name)
        
        # 移动整个目录
        try:
            shutil.move(source_dir, destination_path)
            print(f"已移动: {source_dir} 到 {destination_path}")
        except Exception as e:
            print(f"移动目录时出错: {source_dir} -> {destination_path}, 错误: {e}")

if __name__ == "__main__":
    move_directories()
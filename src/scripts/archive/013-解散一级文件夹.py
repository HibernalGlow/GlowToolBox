import os
import shutil
from pathlib import Path

def dissolve_first_level_folders(root_path):
    """
    解散给定路径下的一级文件夹，将内容移动到上级目录，保留子文件夹结构
    
    Args:
        root_path: 要处理的根目录路径
    """
    root = Path(root_path)
    
    # 确保目录存在
    if not root.is_dir():
        print(f"路径 {root_path} 不存在或不是目录")
        return
    
    # 获取所有一级文件夹
    first_level_folders = [f for f in root.iterdir() if f.is_dir()]
    
    for folder in first_level_folders:
        print(f"正在处理文件夹: {folder.name}")
        
        # 遍历文件夹中的所有内容
        for item in folder.rglob("*"):
            if item.is_file():
                # 计算相对路径
                rel_path = item.relative_to(folder)
                
                # 构建目标路径，保持原有的目录结构
                target_path = root / rel_path
                
                # 创建必要的目录
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                try:
                    # 如果目标文件已存在，直接覆盖
                    shutil.move(str(item), str(target_path))
                    print(f"已移动: {item.name} -> {target_path}")
                except Exception as e:
                    print(f"移动文件 {item.name} 时出错: {e}")
        
        # 移动完成后递归删除空文件夹
        try:
            for root_to_remove, dirs, files in os.walk(str(folder), topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root_to_remove, dir_name)
                    if not os.listdir(dir_path):
                        os.rmdir(dir_path)
                        print(f"已删除空文件夹: {dir_path}")
            
            # 最后删除一级文件夹本身（如果为空）
            if not any(folder.iterdir()):
                folder.rmdir()
                print(f"已删除空文件夹: {folder}")
        except Exception as e:
            print(f"删除文件夹时出错: {e}")

if __name__ == "__main__":
    print("请输入要处理的路径（每行一个，空行结束）：")
    paths = []
    while True:
        path = input().strip()
        if not path:
            break
        # 去除可能存在的引号
        path = path.strip('"').strip("'")
        paths.append(path)
    
    for path in paths:
        print(f"\n处理路径: {path}")
        dissolve_first_level_folders(path)

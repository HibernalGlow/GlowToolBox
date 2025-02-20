import os
import subprocess

def delete_with_7z(path):
    # 记录处理的文件路径
    print(f"正在处理路径: {path}")
    
    if os.path.exists(path):
        # 创建 7z 删除命令
        # 重命名文件或文件夹
        try:
            renamed_path = path
            os.rename(path, renamed_path)
            print(f"已重命名为: {renamed_path}")
            
            # 删除文件或文件夹
            result = subprocess.run(f'7z d "{renamed_path}"', shell=True, capture_output=True)
            if result.returncode == 0:
                print(f"文件夹或文件已删除: {renamed_path}")
            else:
                print(f"删除失败: {renamed_path}")
                print(result.stderr.decode())
        except Exception as e:
            print(f"重命名或删除失败: {path}")
            print(e)
    else:
        print(f"路径不存在: {path}")

if __name__ == "__main__":
    # 处理多个目录或文件，通过运行时读取用户输入
    print("请输入要处理的文件夹或压缩包完整路径，每行一个路径，输入空行结束:")
    directories = []
    while True:
        directory = input().strip().strip('"')
        if not directory:
            break
        directories.append(directory)

    if directories:
        for directory in directories:
            delete_with_7z(directory)
    else:
        print("未输入任何路径")

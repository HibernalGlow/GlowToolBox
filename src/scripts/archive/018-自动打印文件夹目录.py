import os
import re
import datetime

# 全局变量，用于控制当前模式和是否只输出文件夹和压缩包
RENAME_MODE = False  # False 表示打印目录树模式，True 表示恢复文件重命名模式
FOLDER_AND_ZIP_ONLY = True  # True 表示只输出文件夹和压缩包，False 表示输出所有文件和文件夹

def list_files(directory, file, indent=0):
    try:
        # 打印当前目录名到文件和控制台
        line = ' ' * indent + f'[{os.path.basename(directory)}/]'
        print(line)
        file.write(line + '\n')
        
        entries = os.listdir(directory)
        if not RENAME_MODE:
            # 打印目录树模式
            sorted_entries = sorted(entries, key=sort_key_temporary)
            for entry in sorted_entries:
                entry_path = os.path.join(directory, entry)
                if os.path.isdir(entry_path):
                    # 如果是目录，则递归调用 list_files 函数
                    list_files(entry_path, file, indent + 4)
                elif not FOLDER_AND_ZIP_ONLY or (FOLDER_AND_ZIP_ONLY and (entry.endswith('.zip') or os.path.isdir(entry_path))):
                    # 如果是文件，并且未设置只输出文件夹和压缩包，或者设置了只输出文件夹和压缩包且文件是压缩包或文件夹，则打印文件名到文件和控制台
                    line = ' ' * (indent + 4) + entry_path
                    print(line)
                    file.write(line + '\n')
        else:
            # 恢复文件重命名模式
            backup_file_path = input('请输入备份文件路径: ')
            modified_file_path = input('请输入修改后的文件路径: ')
            with open(backup_file_path, 'r', encoding='utf-8') as backup_file, open(modified_file_path, 'r', encoding='utf-8') as modified_file:
                backup_lines = backup_file.readlines()
                modified_lines = modified_file.readlines()
                for backup_line, modified_line in zip(backup_lines, modified_lines):
                    backup_zip_name = backup_line.strip()
                    modified_file_name = modified_line.strip()
                    if backup_zip_name.endswith('.zip'):
                        # 使用用户提供的备份文件路径中的文件名作为压缩文件的路径
                        backup_zip_path = os.path.join(os.path.dirname(backup_file_path), backup_zip_name)
                        if os.path.exists(backup_zip_path):
                            new_name = modified_file_name + '.zip'
                            new_zip_path = os.path.join(directory, new_name)
                            os.rename(backup_zip_path, new_zip_path)
                            # 打印重命名后的文件名到文件和控制台
                            line = ' ' * (indent + 4) + new_zip_path
                            print(f'Renamed: {line}')
                            file.write(f'Renamed: {line}\n')
                        else:
                            print(f'Error: File not found - {backup_zip_path}')
                            file.write(f'Error: File not found - {backup_zip_path}\n')
                    
    except PermissionError:
        # 捕捉权限错误，并在控制台和文件中记录错误
        error_line = ' ' * indent + '[Permission Denied]'
        print(error_line)
        file.write(error_line + '\n')
    except Exception as e:
        # 捕捉其他异常，并在控制台和文件中记录错误
        error_line = ' ' * indent + f'[Error: {e}]'
        print(error_line)
        file.write(error_line + '\n')

def sort_key_temporary(entry):
    # 临时排序函数，仅用于输出目录树时的临时排序
    # 去除方框和括号内的内容后排序
    entry_without_brackets = re.sub(r'\$.*?\$|\$.*?\$', '', entry)
    return entry_without_brackets.lower()

def save_to_md(version_file, version_info):
    with open(version_file, 'a', encoding='utf-8') as f:
        f.write(f"## Version {version_info['version']} - {version_info['date']}\n")
        f.write(version_info['content'])
        f.write('\n\n')

def main():
    global RENAME_MODE
    global FOLDER_AND_ZIP_ONLY
    
    path = input('请输入路径: ')
    output_file = datetime.datetime.now().strftime('%Y%m%d%H%M%S') + '.txt'
    version_file = 'versions.md'
    
    if not os.path.exists(version_file):
        with open(version_file, 'w', encoding='utf-8') as f:
            f.write('# Directory Structure Versions\n\n')
    
    # 读取现有版本信息
    versions = []
    with open(version_file, 'r', encoding='utf-8') as f:
        content = f.read()
        version_headers = re.findall(r'## Version (\d+) - (.+)\n', content)
        for version, date in version_headers:
            versions.append((int(version), date))
    
    # 确定新版本号
    if versions:
        latest_version = max(versions, key=lambda x: x[0])[0]
        new_version = latest_version + 1
    else:
        new_version = 1
    
    # 生成目录树或恢复文件重命名
    if os.path.exists(path):
        try:
            with open(output_file, 'w', encoding='utf-8') as file:
                list_files(path, file)
            print(f'结果已保存到 {output_file}')
            
            # 记录版本信息到版本控制文件
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            version_info = {
                'version': new_version,
                'date': timestamp,
                'content': f"Generated from path '{path}' to '{output_file}'\n"
            }
            save_to_md(version_file, version_info)
            
            # 切换模式
            RENAME_MODE = not RENAME_MODE
            
            if RENAME_MODE:
                print("已切换到恢复文件重命名模式。")
            
        except Exception as e:
            print(f'发生异常: {e}')
    else:
        print('路径不存在或无效!')

if __name__ == '__main__':
    main()
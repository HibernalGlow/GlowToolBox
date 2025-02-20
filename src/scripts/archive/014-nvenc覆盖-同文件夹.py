import os
import shutil
from send2trash import send2trash

def find_matching_videos_in_folder(folder_path, keywords, move=False, permanent_delete=False):
    """
    在同一文件夹内查找NVENC文件和对应的原始文件进行覆盖
    Args:
        folder_path: 文件夹路径
        keywords: 关键词列表（如 ['NVENC', 'x264', 'x265']）
        move: 是否移动文件（True为剪切，False为复制）
        permanent_delete: 是否永久删除（True为直接删除，False为移动到回收站）
    """
    video_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.wmv')
    
    # 获取所有视频文件并分类
    nvenc_files = []  # 带关键词的文件
    normal_files = [] # 不带关键词的文件
    
    # 遍历文件夹
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(video_extensions):
                full_path = os.path.join(root, file)
                # 检查文件名是否包含关键词
                if any(keyword.lower() in file.lower() for keyword in keywords):
                    nvenc_files.append(full_path)
                else:
                    normal_files.append(full_path)
                    if os.path.getsize(full_path) == 0:
                        print(f"发现0字节文件: {full_path}")
    
    print(f"找到NVENC文件数量: {len(nvenc_files)}")
    print(f"找到普通文件数量: {len(normal_files)}")
    
    matches = []
    
    # 匹配文件
    for nvenc_file in nvenc_files:
        nvenc_filename = os.path.basename(nvenc_file).lower()
        nvenc_name_without_ext = os.path.splitext(nvenc_filename)[0]
        nvenc_ext = os.path.splitext(nvenc_file)[1].lower()
        
        # 获取不带关键词的基础文件名
        base_name = nvenc_name_without_ext
        # 先找到第一个分隔符的位置
        separator_index = -1
        for keyword in keywords:
            if keyword.lower() in base_name.lower():
                # 找到关键词前的最后一个分隔符
                keyword_index = base_name.lower().find(keyword.lower())
                possible_separators = ['-', '_', ' ', '.']
                for sep in possible_separators:
                    last_sep_index = base_name[:keyword_index].rfind(sep)
                    if last_sep_index > separator_index:
                        separator_index = last_sep_index
        
        # 如果找到分隔符，使用分隔符前的部分作为基础文件名
        if separator_index != -1:
            base_name = base_name[:separator_index].strip('.-_ ')
        else:
            # 如果没有找到分隔符，则移除所有关键词
            for keyword in keywords:
                base_name = base_name.replace(keyword.lower(), '').strip('.-_ ')
        
        # 在普通文件中查找匹配
        for normal_file in normal_files:
            normal_filename = os.path.basename(normal_file).lower()
            normal_name_without_ext = os.path.splitext(normal_filename)[0].strip('.-_ ')
            normal_ext = os.path.splitext(normal_file)[1].lower()
            
            # 检查基础文件名和扩展名是否匹配
            if base_name == normal_name_without_ext and nvenc_ext == normal_ext:
                matches.append({
                    'source': nvenc_file,
                    'target': normal_file
                })
                print(f"匹配: {nvenc_filename} -> {normal_filename}")  # 添加调试信息
                break
    
    # 处理匹配的文件
    for match in matches:
        source_file = match['source']
        target_file = match['target']
        
        try:
            # 检查目标文件是否存在
            if os.path.exists(target_file):
                target_size = os.path.getsize(target_file)
                source_size = os.path.getsize(source_file)
                
                if target_size == 0:
                    print(f"目标文件大小为0字节，将直接覆盖: {target_file}")
                elif target_size == source_size:
                    print(f"目标文件与源文件大小相同({target_size}字节)，将直接覆盖: {target_file}")
                elif source_size < target_size:
                    print(f"源文件更小(源:{source_size}字节, 目标:{target_size}字节)，将覆盖: {target_file}")
                else:
                    print(f"源文件更大(源:{source_size}字节, 目标:{target_size}字节)，跳过覆盖: {target_file}")
                    continue
                
                # 删除目标文件
                if permanent_delete:
                    os.remove(target_file)
                    print(f"已永久删除: {target_file}")
                else:
                    send2trash(target_file)
                    print(f"已移动到回收站: {target_file}")
            
            # 复制或移动源文件到目标位置
            if move:
                shutil.move(source_file, target_file)
                print(f"已移动: {source_file} -> {target_file}")
            else:
                shutil.copy2(source_file, target_file)
                print(f"已复制: {source_file} -> {target_file}")
                
        except Exception as e:
            print(f"处理文件时出错: {str(e)}")
            continue
    
    return matches

# 使用示例
if __name__ == '__main__':
    # 设置路径和关键词
    folder_path = r'E:\1MOV\me3\hand'  # 设置为你的文件夹路径
    keywords = ['NVENC', 'x264', 'x265']
    
    # 设置操作模式
    MOVE_FILES = True          # True为剪切，False为复制
    PERMANENT_DELETE = False    # True为直接删除，False为移到回收站
    
    # 查找匹配的视频
    matching_videos = find_matching_videos_in_folder(folder_path, keywords, 
                                                   move=MOVE_FILES, 
                                                   permanent_delete=PERMANENT_DELETE)
    
    # 打印结果
    if matching_videos:
        print('找到以下匹配的视频文件：')
        for match in matching_videos:
            print(f'NVENC文件: {match["source"]}')
            print(f'原始文件: {match["target"]}')
            print('-' * 50)
        
        # 请求用户确认
        confirm = input('是否确认执行文件操作？(y/n): ').lower()
        if confirm == 'y':
            print('开始执行文件操作...')
            find_matching_videos_in_folder(folder_path, keywords, 
                                         move=MOVE_FILES, 
                                         permanent_delete=PERMANENT_DELETE)
        else:
            print('操作已取消')
    else:
        print('未找到匹配的视频文件') 
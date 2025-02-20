import os
import glob
import shutil
from send2trash import send2trash

def find_matching_videos(source_path, target_path, keywords, move=False, permanent_delete=False, keep_source_name=False):
    """
    查找源路径和目标路径下匹配的视频文件
    Args:
        source_path: 源文件夹路径
        target_path: 目标文件夹路径
        keywords: 关键词列表
        move: 是否移动文件（True为剪切，False为复制）
        permanent_delete: 是否永久删除（True为直接删除，False为移动到回收站）
        keep_source_name: 是否保留源文件名（True为保留NVENC等标记，False为使用目标文件名）
    """
    video_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.wmv')
    
    # 获取所有视频文件
    source_videos = []
    target_videos = []
    
    # 改进遍历方式
    for root, dirs, files in os.walk(source_path):
        for file in files:
            if file.lower().endswith(video_extensions):
                source_videos.append(os.path.join(root, file))
                
    for root, dirs, files in os.walk(target_path):
        for file in files:
            if file.lower().endswith(video_extensions):
                file_path = os.path.join(root, file)
                target_videos.append(file_path)
                if os.path.getsize(file_path) == 0:
                    print(f"发现0字节文件: {file_path}")
    
    print(f"找到源文件夹中的视频文件数量: {len(source_videos)}")
    print(f"找到目标文件夹中的视频文件数量: {len(target_videos)}")
    
    matches = []
    
    for source_video in source_videos:
        source_filename = os.path.basename(source_video).lower()  # 转换为小写以进行不区分大小写的比较
        source_name_without_ext = os.path.splitext(source_filename)[0]
        
        # 检查文件名是否包含关键词
        if any(keyword.lower() in source_filename for keyword in keywords):
            # 获取关键词之前的文件名部分
            prefix = None
            keyword_found = None
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in source_filename:
                    # 使用 rfind 来处理文件名中可能多次出现关键词的情况
                    keyword_index = source_filename.rfind(keyword_lower)
                    prefix = source_filename[:keyword_index].strip('.-_ ')  # 移除常见的分隔符
                    keyword_found = keyword
                    break
            
            if prefix:
                # 在目标文件夹中查找匹配的文件
                for target_video in target_videos:
                    target_filename = os.path.basename(target_video).lower()
                    target_name_without_ext = os.path.splitext(target_filename)[0]
                    
                    # 跳过源文件自身
                    if source_video == target_video:
                        continue
                    
                    # 先检查完整文件名是否相同（不包括扩展名）
                    if source_name_without_ext == target_name_without_ext:
                        matches.append({
                            'source': source_video,
                            'target': target_video
                        })
                        continue
                    
                    # 如果完整文件名不同，再检查基础文件名匹配
                    # 确保目标文件不包含同样的关键词
                    if keyword_found.lower() in target_filename:
                        continue
                    
                    # 使用更宽松的匹配规则
                    target_name_clean = target_filename.strip('.-_ ')
                    if (os.path.splitext(source_video)[1].lower() == os.path.splitext(target_video)[1].lower() and 
                        (target_name_clean.startswith(prefix) or prefix in target_name_clean)):
                        matches.append({
                            'source': source_video,
                            'target': target_video
                        })
    
    # 添加文件操作逻辑
    for match in matches:
        source_file = match['source']
        target_file = match['target']
        
        try:
            # 确定目标文件路径
            if keep_source_name:
                # 使用源文件名（保留NVENC等标记）
                new_target = os.path.join(os.path.dirname(target_file), os.path.basename(source_file))
            else:
                # 使用目标文件名（不保留NVENC等标记）
                new_target = target_file
            
            # 检查目标文件是否存在
            if os.path.exists(target_file):
                target_size = os.path.getsize(target_file)
                source_size = os.path.getsize(source_file)
                
                if target_size == 0:
                    print(f"目标文件大小为0字节，将直接覆盖: {target_file}")
                elif target_size == source_size:
                    print(f"目标文件与源文件大小相同({target_size}字节)，将直接覆盖: {target_file}")
                else:
                    print(f"目标文件大小与源文件不同(目标:{target_size}字节, 源:{source_size}字节)，跳过覆盖: {target_file}")
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
                shutil.move(source_file, new_target)
                print(f"已移动: {source_file} -> {new_target}")
            else:
                shutil.copy2(source_file, new_target)
                print(f"已复制: {source_file} -> {new_target}")
                
        except Exception as e:
            print(f"处理文件时出错: {str(e)}")
            continue
    
    return matches

# 使用示例
if __name__ == '__main__':
    # 设置路径和关键词
    source_path = r'E:\1MOV\me3\nvenc'
    target_path = r'E:\1MOV\me3\hand'
    keywords = ['NVENC', 'x264', 'x265']
    
    # 设置操作模式
    MOVE_FILES = True          # True为剪切，False为复制
    PERMANENT_DELETE = False    # True为直接删除，False为移到回收站
    KEEP_SOURCE_NAME = True    # True为保留源文件名（带NVENC等标记），False为使用目标文件名
    
    # 查找匹配的视频
    matching_videos = find_matching_videos(source_path, target_path, keywords, 
                                         move=MOVE_FILES, 
                                         permanent_delete=PERMANENT_DELETE,
                                         keep_source_name=KEEP_SOURCE_NAME)
    
    # 打印结果
    if matching_videos:
        print('找到以下匹配的视频文件：')
        for match in matching_videos:
            print(f'源文件: {match["source"]}')
            print(f'目标文件: {match["target"]}')
            print('-' * 50)
        
        # 请求用户确认
        confirm = input('是否确认执行文件操作？(y/n): ').lower()
        if confirm == 'y':
            print('开始执行文件操作...')
            find_matching_videos(source_path, target_path, keywords, 
                               move=MOVE_FILES, 
                               permanent_delete=PERMANENT_DELETE,
                               keep_source_name=KEEP_SOURCE_NAME)
        else:
            print('操作已取消')
    else:
        print('未找到匹配的视频文件')
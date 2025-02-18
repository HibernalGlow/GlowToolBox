import os
import glob
from pathlib import Path

def process_videos(directory):
    # 支持的视频格式
    video_extensions = ('.mp4', '.avi', '.mkv', '.wmv', '.mov', '.flv', '.webm', '.m4v')
    
    # 一次性获取所有文件
    all_files = []
    for ext in video_extensions:
        all_files.extend(glob.glob(os.path.join(directory, f'**/*{ext}*'), recursive=True))
    
    nov_files = [f for f in all_files if f.endswith('.nov')]
    normal_files = [f for f in all_files if not f.endswith('.nov') and any(f.endswith(ext) for ext in video_extensions)]
    
    choice = input('1: 添加.nov, 2: 恢复 [默认], q: 退出: ').strip()
    if choice == 'q':
        return
        
    if choice == '1':
        # 添加.nov后缀
        for file in normal_files:
            try:
                os.rename(file, file + '.nov')
            except Exception as e:
                print(f'错误 {file}: {e}')
    else:
        # 恢复原始后缀
        for file in nov_files:
            try:
                os.rename(file, file[:-4])
            except Exception as e:
                print(f'错误 {file}: {e}')

if __name__ == '__main__':
    process_videos(r'E:\1EHV') 
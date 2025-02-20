import os
import concurrent.futures
import time
from pathlib import Path
import sys
import click
import pyperclip
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import radiolist_dialog
from prompt_toolkit.formatted_text import HTML

def normalize_path(path):
    # 处理复制粘贴的路径，移除引号，处理转义字符
    path = path.strip('" \'')  # 移除首尾的引号和空格
    return os.path.normpath(path)  # 标准化路径分隔符

def process_single_file(file_path, add_nov=True):
    try:
        # 获取原始文件的时间戳
        stat = os.stat(file_path)
        atime = stat.st_atime  # 访问时间
        mtime = stat.st_mtime  # 修改时间
        
        # 根据操作类型重命名文件
        new_path = file_path + '.nov' if add_nov else file_path[:-4]
        os.rename(file_path, new_path)
        
        # 恢复时间戳
        os.utime(new_path, (atime, mtime))
        return True, file_path
    except Exception as e:
        return False, f'错误 {file_path}: {e}'

def find_video_files(directory):
    # 支持的视频格式
    video_extensions = ('.mp4', '.avi', '.mkv', '.wmv', '.mov', '.flv', '.webm', '.m4v','.ts','.mts')
    
    print("正在扫描文件...")
    nov_files = []
    normal_files = []
    
    # 使用os.walk快速遍历目录
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            if file.endswith('.nov'):
                # 检查.nov文件的原始扩展名是否为视频格式
                base_name = file[:-4]
                if any(base_name.lower().endswith(ext) for ext in video_extensions):
                    nov_files.append(file_path)
            else:
                # 检查普通文件是否为视频格式
                if any(file.lower().endswith(ext) for ext in video_extensions):
                    normal_files.append(file_path)
    
    return nov_files, normal_files

def process_videos(directory):
    # 快速搜索文件
    nov_files, normal_files = find_video_files(directory)
    
    print(f"找到 {len(normal_files)} 个普通视频文件")
    print(f"找到 {len(nov_files)} 个.nov视频文件")
    
    # 使用prompt_toolkit的radiolist_dialog实现可点击的选择界面
    choice = radiolist_dialog(
        title="选择操作",
        text="请用鼠标或方向键选择要执行的操作：",
        values=[
            ("1", "添加.nov后缀"),
            ("2", "恢复原始文件名"),
            ("q", "退出程序")
        ],
        default="2"
    ).run()
    
    if choice == 'q' or choice is None:  # None表示用户按了Esc或关闭窗口
        return
    
    # 使用线程池处理文件
    start_time = time.time()
    total_files = len(normal_files if choice == '1' else nov_files)
    if total_files == 0:
        print("没有找到需要处理的文件！")
        return
        
    print(f"\n开始处理 {total_files} 个文件...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(32, os.cpu_count() * 4)) as executor:
        if choice == '1':
            futures = [executor.submit(process_single_file, file, True) for file in normal_files]
        else:
            futures = [executor.submit(process_single_file, file, False) for file in nov_files]
        
        # 收集处理结果并显示进度
        success_count = 0
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            success, result = future.result()
            completed += 1
            if completed % 10 == 0 or completed == total_files:  # 每10个文件更新一次进度
                print(f"\r进度: {completed}/{total_files} ({(completed/total_files*100):.1f}%)", end="")
            
            if success:
                success_count += 1
            else:
                print(f"\n{result}")
    
    end_time = time.time()
    print(f'\n\n处理完成！')
    print(f'成功处理: {success_count}/{total_files} 个文件')
    print(f'总耗时: {end_time - start_time:.2f} 秒')

@click.command()
@click.option('-c', is_flag=True, help='从剪贴板读取路径')
def main(c):
    """视频文件格式批量处理工具"""
    if c:
        # 从剪贴板读取路径
        clipboard_content = pyperclip.paste()
        # 分割多行路径
        paths = [p.strip() for p in clipboard_content.splitlines() if p.strip()]
        if not paths:
            print("剪贴板中没有有效的路径！")
            return
    else:
        # 使用prompt_toolkit的prompt实现更好的输入体验
        default_path = r'E:\1EHV'
        input_path = prompt(
            HTML('<b>请输入要处理的路径: </b>'),
            default=default_path,
            mouse_support=True
        ).strip()
        paths = [input_path] if input_path else [default_path]
    
    for path in paths:
        path = normalize_path(path)
        if not os.path.exists(path):
            print(f"路径不存在: {path}")
            continue
        print(f"\n处理路径: {path}")
        process_videos(path)

if __name__ == '__main__':
    main()
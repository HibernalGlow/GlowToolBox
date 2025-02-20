import os
import shutil
import cv2
from typing import Dict, List, Tuple
from datetime import datetime

def get_video_info(video_path: str) -> Tuple[float, float]:
    """
    获取视频时长（秒）和码率（bits/s）
    """
    try:
        # 打开视频文件
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return 0, 0
            
        # 获取视频帧数和帧率
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        # 计算时长（秒）
        duration = total_frames / fps if fps > 0 else 0
        
        # 获取文件大小（字节）并计算码率
        file_size = os.path.getsize(video_path)
        bitrate = (file_size * 8) / duration if duration > 0 else 0
        
        cap.release()
        return duration, bitrate
    except:
        return 0, 0

def estimate_video_bitrate(video_path: str) -> float:
    """
    估算视频码率（bits/s）
    使用文件大小作为参考，假设1分钟视频
    """
    try:
        # 获取文件大小（字节）
        file_size = os.path.getsize(video_path)
        # 假设平均1分钟视频，转换为比特率（bits/s）
        # 文件大小(bytes) * 8(bits/byte) / 60(s) 
        bitrate = (file_size * 8) / 60
        return bitrate
    except:
        return 0

def get_bitrate_level(bitrate: float, levels: Dict[str, float]) -> str:
    """根据码率判断所属等级"""
    for level_name, threshold in sorted(levels.items(), key=lambda x: x[1]):
        if bitrate <= threshold:
            return level_name
    return list(levels.keys())[-1]

def organize_videos_by_size(
    source_dir: str,
    output_dir: str,
    bitrate_levels: Dict[str, float],
    video_extensions: List[str] = ['.mp4', '.mkv', '.avi', '.mov']
):
    """按实际码率对视频进行分组"""
    # 创建日志目录
    log_dir = os.path.join(output_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # 创建日志文件
    log_file = os.path.join(log_dir, f"transfer_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    
    with open(log_file, "w", encoding="utf-8") as f:
        for root, _, files in os.walk(source_dir):
            for file in files:
                if any(file.lower().endswith(ext) for ext in video_extensions):
                    # 获取源文件路径
                    source_path = os.path.join(root, file)
                    
                    # 获取相对路径，用于保持目录结构
                    rel_path = os.path.relpath(root, source_dir)
                    
                    # 获取视频信息
                    duration, bitrate = get_video_info(source_path)
                    
                    # 获取码率等级
                    level = get_bitrate_level(bitrate, bitrate_levels)
                    
                    # 构建目标路径
                    dest_dir = os.path.join(output_dir, level, rel_path)
                    os.makedirs(dest_dir, exist_ok=True)
                    
                    # 移动文件（而不是复制）
                    dest_path = os.path.join(dest_dir, file)
                    shutil.move(source_path, dest_path)
                    
                    # 记录日志
                    log_message = (
                        f"文件: {file}\n"
                        f"源路径: {source_path}\n"
                        f"目标路径: {dest_path}\n"
                        f"分组: {level}\n"
                        f"时长: {duration:.2f}秒\n"
                        f"码率: {bitrate/1000000:.2f}Mbps\n"
                    )
                    f.write(log_message + "-" * 50 + "\n")
                    print(f"移动: {file} -> {level} ({bitrate/1000000:.2f}Mbps, {duration:.1f}秒)")

def create_bitrate_levels(step_mb: float = 5, max_steps: int = 5) -> Dict[str, float]:
    """
    创建码率等级字典
    step_mb: 每档位的大小（MB）
    max_steps: 最大档位数量
    """
    levels = {}
    # 计算需要的位数
    digits = len(str(max_steps * step_mb))
    
    for i in range(1, max_steps + 1):
        threshold = i * step_mb * 1000000  # 转换为 bits/s
        # 使用 str(i*step_mb).zfill() 补零
        level_name = str(int(i*step_mb)).zfill(digits) + "MB"
        levels[level_name] = threshold
    
    # 添加最后一个无限大的档位
    levels["超大文件"] = float('inf')
    return levels

def process_path(path: str, bitrate_levels: Dict[str, float], video_extensions: List[str]):
    """处理单个路径（文件或文件夹）"""
    if os.path.isdir(path):
        # 如果是目录，在该目录下创建分类文件夹
        organize_videos_by_size(path, path, bitrate_levels)
    elif os.path.isfile(path):
        # 如果是文件，使用其所在目录作为输出目录
        source_dir = os.path.dirname(path)
        organize_videos_by_size(source_dir, source_dir, bitrate_levels, [path])

if __name__ == "__main__":
    # 用户可以自定义每档大小（MB）和档位数量
    step_size = 5  # 每档5MB
    num_levels = 15  # 档位数量
    
    # 生成码率等级
    bitrate_levels = create_bitrate_levels(step_size, num_levels)
    
    # 打印当前分组设置
    print("\n当前码率分组设置：")
    for level, threshold in bitrate_levels.items():
        if threshold != float('inf'):
            print(f"{level}: {threshold/1000000:.1f}Mbps")
        else:
            print(f"{level}: 无限制")
    
    print("\n请输入文件或文件夹路径（每行一个，空行结束）：")
    print("支持直接粘贴带引号的路径")
    paths = []
    while True:
        path = input().strip()
        if not path:
            break
        # 处理带引号的路径
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]  # 去除首尾的引号
        if os.path.exists(path):
            paths.append(path)
        else:
            print(f"路径不存在: {path}")
    
    if paths:
        print("\n将处理以下路径：")
        for path in paths:
            print(path)
        confirm = 'y'
        
        if confirm == 'y':
            for path in paths:
                print(f"\n处理: {path}")
                process_path(path, bitrate_levels, ['.mp4', '.mkv', '.avi', '.mov'])
            print("\n整理完成！")
        else:
            print("\n已取消操作")
    else:
        print("\n未输入有效路径")
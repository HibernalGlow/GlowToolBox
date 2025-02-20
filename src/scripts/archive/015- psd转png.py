from PIL import Image
import os
from psd_tools import PSDImage
from tqdm import tqdm
import send2trash
from pathlib import Path

def convert_psd_to_png(input_path):
    """
    将PSD文件转换为PNG格式，转换成功后将原PSD文件移动到回收站
    
    参数:
    input_path: PSD文件或文件夹的路径
    """
    
    # 如果输入路径是文件
    if os.path.isfile(input_path):
        if input_path.lower().endswith('.psd'):
            process_single_file(input_path, os.path.dirname(input_path))
    
    # 如果输入路径是文件夹
    else:
        # 使用 pathlib 查找所有PSD文件
        input_path = Path(input_path)
        psd_files = []
        
        # 递归查找所有文件
        for file in input_path.rglob('*'):
            if file.is_file() and file.suffix.lower() == '.psd':
                psd_files.append(str(file))
        
        if not psd_files:
            print(f"在 {input_path} 中没有找到PSD文件")
            return
        
        # 使用进度条显示处理进度
        with tqdm(total=len(psd_files), desc="转换PSD文件") as pbar:
            for psd_file in psd_files:
                # 转换文件
                success = process_single_file(psd_file, os.path.dirname(psd_file))
                pbar.update(1)
                
                if success:
                    pbar.set_description(f"成功转换并移除: {os.path.basename(psd_file)}")
                else:
                    pbar.set_description(f"转换失败: {os.path.basename(psd_file)}")

def process_single_file(psd_path, out_path):
    try:
        # 打开PSD文件
        psd = PSDImage.open(psd_path)
        
        # 合并所有图层并转换为PNG
        composed = psd.composite()
        
        # 获取原始PSD的色深模式
        color_mode = psd.color_mode
        
        # 确保输出图像具有相同的色深
        if color_mode == 'RGB':
            composed = composed.convert('RGB')
        elif color_mode == 'CMYK':
            composed = composed.convert('CMYK')
        elif color_mode == 'GRAYSCALE':
            composed = composed.convert('L')
        
        # 获取文件名（不含扩展名）和目录
        filename = os.path.splitext(os.path.basename(psd_path))[0]
        dir_path = os.path.dirname(psd_path)
        
        # 新文件名添加[PSD]标记
        new_filename = f"{filename}[PSD].png"
        
        # 保存为无损PNG（在原目录）
        png_path = os.path.join(dir_path, new_filename)
        composed.save(png_path, optimize=False, compress_level=0)
        
        # 转换成功后，将原PSD文件移动到回收站
        send2trash.send2trash(psd_path)
        
        return True
    except Exception as e:
        print(f"处理文件 {psd_path} 时出错: {str(e)}")
        return False

if __name__ == "__main__":
    # 获取用户输入
    input_path = input("请输入PSD文件或文件夹路径: ")
    
    # 执行转换
    convert_psd_to_png(input_path)
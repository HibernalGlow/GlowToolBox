import os
import shutil
import subprocess
from PIL import Image
from psd_tools import PSDImage
from tqdm import tqdm
import send2trash
from pathlib import Path
import logging
from pdf2image import convert_from_path
import pyperclip
import argparse
import zipfile
from multiprocessing import Pool, cpu_count

# 配置日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_archive(archive_path, check_content=False):
    """新增check_content参数用于控制是否检查压缩包内容"""
    try:
        archive_path = Path(archive_path)
        dir_path = archive_path.parent
        file_name = archive_path.stem
        extract_path = dir_path / file_name
        
        # 新增内容检查逻辑
        if check_content:
            # 检查ZIP文件内容
            if archive_path.suffix.lower() == '.zip':
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    has_target_files = any(f.lower().endswith(('.psd', '.pdf')) for f in zip_ref.namelist())
                    if not has_target_files:
                        print(f"跳过无PSD/PDF的压缩包: {archive_path}")
                        return False
            # 其他格式在解压后检查
            else:
                temp_extract = extract_path.with_name(extract_path.name + '_temp')
                cmd = [
                    '7z', 'l',
                    str(archive_path),
                    '-slt',
                    '-scsUTF-8'
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
                has_target_files = any(line.strip().endswith(('.psd', '.pdf')) for line in result.stdout.split('\n'))
                if not has_target_files:
                    print(f"跳过无PSD/PDF的压缩包: {archive_path}")
                    return False

        # 创建解压目标文件夹
        os.makedirs(extract_path, exist_ok=True)

        if archive_path.suffix.lower() == '.zip':
            # 改进的ZIP处理方式
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                for info in zip_ref.filelist:
                    try:
                        # 尝试多种编码方式
                        encodings = ['cp932', 'utf-8', 'gbk', 'big5']
                        decoded_name = None
                        
                        for encoding in encodings:
                            try:
                                decoded_name = info.filename.encode('cp437').decode(encoding)
                                break
                            except:
                                continue
                        
                        if decoded_name:
                            # 解压单个文件
                            zip_ref.extract(info, path=extract_path)
                            old_path = extract_path / info.filename
                            new_path = extract_path / decoded_name
                            if old_path.exists() and old_path != new_path:
                                old_path.rename(new_path)
                        else:
                            # 如果所有编码都失败，使用原始文件名
                            zip_ref.extract(info, path=extract_path)
                            
                    except Exception as e:
                        print(f"处理文件 {info.filename} 时出错: {e}")
        else:
            # 保持使用7z的方式不变
            cmd = [
                '7z', 'x',
                str(archive_path),
                f'-o{str(extract_path)}',
                '-scsUTF-8',
                '-aoa',
                '-y'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"7z解压失败: {result.stderr}")

        # 解压成功后删除原压缩文件
        if has_target_files:  # 只有包含目标文件时才删除原包
            os.remove(archive_path)
            print(f"已解压并删除: {archive_path}")
        return True
            
    except Exception as e:
        print(f"处理文件时出错 {archive_path}: {e}")
        return False

def extract_all_archives(directory):
    """解压指定目录下的所有压缩文件（仅含PSD/PDF）"""
    archive_extensions = {'.zip', '.7z', '.rar', '.cbz'}
    
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in archive_extensions):
                archive_path = os.path.join(root, file)
                extract_archive(archive_path, check_content=True)  # 新增参数

def delete_files_by_extensions(directory, extensions):
    """
    删除指定目录下具有指定扩展名的所有文件。

    参数:
    directory -- 目标目录路径
    extensions -- 文件扩展名列表
    """
    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    print(f"Deleted file: {file_path}")
                except Exception as e:
                    print(f"Error deleting file {file_path}: {e}")

def delete_empty_folders(directory):
    """
    删除指定目录下的所有空文件夹。

    参数:
    directory -- 目标目录路径
    """
    for root, dirs, files in os.walk(directory, topdown=False):
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            if not os.listdir(dir_path):
                try:
                    os.rmdir(dir_path)
                    print(f"Deleted empty directory: {dir_path}")
                except Exception as e:
                    print(f"Error deleting directory {dir_path}: {e}")

def delete_folders_by_keywords(directory, keywords):
    """
    删除指定目录下包含特定关键字的文件夹。

    参数:
    directory -- 目标目录路径
    keywords -- 关键字列表
    """
    for root, dirs, files in os.walk(directory, topdown=False):
        for dir in dirs:
            if any(keyword in dir for keyword in keywords):
                dir_path = os.path.join(root, dir)
                try:
                    shutil.rmtree(dir_path)
                    print(f"Deleted directory containing keyword: {dir_path}")
                except Exception as e:
                    print(f"Error deleting directory {dir_path}: {e}")

def organize_media_files(source_path, target_base_path):
    """
    整理媒体文件，保持原有文件夹结构，使用剪切操作，清理空文件夹
    
    参数:
    source_path (str): 源路径
    target_base_path (str): 目标基础路径
    """
    # 定义文件类型
    media_types = {
        '[01视频]': ['.mp4', '.avi', '.webm', '.rmvb', '.mov', '.mkv','.flv','.wmv'],
        '[02动图]': ['.gif'],
        # '[03压缩]': ['.zip', '.7z', '.rar'],
        '[04cbz]': ['.cbz']  # 新增cbz文件类型
    }
    
    # 遍历源路径
    for root, _, files in os.walk(source_path, topdown=False):
        # 检查当前文件夹是否包含需要处理的媒体文件
        media_files = {}
        for file in files:
            for media_type, extensions in media_types.items():
                if any(file.endswith(ext.lower()) for ext in extensions):
                    if media_type not in media_files:
                        media_files[media_type] = []
                    media_files[media_type].append(file)
        
        # 如果文件夹包含媒体文件，移动文件
        if media_files:
            relative_path = os.path.relpath(root, source_path)
            for media_type, file_list in media_files.items():
                target_dir = os.path.join(target_base_path, media_type, relative_path)
                
                # 创建目标文件夹
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)
                
                # 移动文件
                for file in file_list:
                    src_file = os.path.join(root, file)
                    dst_file = os.path.join(target_dir, file)
                    try:
                        shutil.move(src_file, dst_file)
                        print(f"已移动 {src_file} 到 {dst_file}")
                    except Exception as e:
                        print(f"移动文件时出错 {src_file}: {e}")

    # 处理完文件后，删除空文件夹
    print("\n开始清理空文件夹...")
    for root, dirs, files in os.walk(source_path, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                if not os.listdir(dir_path):  # 检查文件夹是否为空
                    os.rmdir(dir_path)
                    print(f"已删除空文件夹: {dir_path}")
            except Exception as e:
                print(f"删除空文件夹时出错 {dir_path}: {e}")

def process_single_psd(psd_path, out_path, use_recycle_bin=True):
    """
    处理单个PSD文件的转换
    
    参数:
    psd_path -- PSD文件路径
    out_path -- 输出路径
    use_recycle_bin -- 是否使用回收站删除文件，True则移至回收站，False则直接删除
    """
    try:
        success = False
        error_messages = []

        # 优先尝试使用 cp932 编码（日文 Windows 系统默认编码）
        try:
            psd = PSDImage.open(psd_path, encoding='cp932')
            # 检测并输出原始色深信息
            bit_depth = psd.depth
            channels = len(psd.channels)
            print(f"原始PSD信息：")
            print(f"- 色深: {bit_depth}位/通道")
            print(f"- 通道数: {channels}")
            
            # 根据色深决定转换策略
            if bit_depth > 16:
                print("警告：原始PSD色深超过16位/通道，转换为PNG可能会损失色彩信息")
                # 这里可以添加是否继续的询问
                
            composed = psd.composite()
            success = True
        except Exception as e:
            error_messages.append(f"psd-tools (CP932) 打开失败: {e}")
            # 如果失败，依次尝试其他编码
            for encoding in ['utf-8', 'shift-jis', 'latin1']:
                try:
                    psd = PSDImage.open(psd_path, encoding=encoding)
                    composed = psd.composite()
                    success = True
                    break
                except Exception as e:
                    error_messages.append(f"psd-tools ({encoding}) 打开失败: {e}")

        # 方法2: 如果psd-tools失败，尝试使用wand
        if not success:
            try:
                from wand.image import Image
                with Image(filename=psd_path, format='psd') as img:
                    # 强制设置格式和色彩空间
                    img.format = 'png'
                    img.colorspace = 'rgb'
                    # 直接保存为PNG
                    filename = os.path.splitext(os.path.basename(psd_path))[0]
                    new_filename = f"{filename}[PSD].png"
                    png_path = os.path.join(os.path.dirname(psd_path), new_filename)
                    img.save(filename=png_path)
                    success = True
            except Exception as e:
                error_messages.append(f"wand 打开失败: {e}")

        if success:
            # 如果使用psd-tools成功，需要保存文件
            if 'composed' in locals():
                filename = os.path.splitext(os.path.basename(psd_path))[0]
                new_filename = f"{filename}[PSD].png"
                png_path = os.path.join(os.path.dirname(psd_path), new_filename)
                composed.save(png_path, 
                    format='PNG',
                    optimize=True,
                    compress_level=6,  # 降低压缩级别以提高速度
                )

            # 转换成功后，根据设置决定删除方式
            if use_recycle_bin:
                send2trash.send2trash(psd_path)
                logging.info(f"成功转换并移至回收站: {psd_path}")
            else:
                os.remove(psd_path)
                logging.info(f"成功转换并直接删除: {psd_path}")
            return True
        else:
            # 记录所有尝试过的方法的错误信息
            for error in error_messages:
                logging.error(f"{psd_path}: {error}")
            return False

    except Exception as e:
        logging.error(f"处理文件时发生错误 {psd_path}: {str(e)}")
        return False

def process_psd_wrapper(args):
    """
    包装函数用于多进程处理PSD文件
    """
    return process_single_psd(*args)

def convert_psd_files(directory, use_recycle_bin=True):
    """转换目录中的所有PSD文件"""
    directory = Path(directory)
    psd_files = list(directory.rglob('*.psd'))
    
    if not psd_files:
        print(f"在 {directory} 中没有找到PSD文件")
        return
    
    # 使用多进程处理
    num_processes = max(1, cpu_count() - 1)  # 保留一个CPU核心
    print(f"使用 {num_processes} 个进程进行转换")
    
    with Pool(num_processes) as pool:
        args = [(str(f), str(f.parent), use_recycle_bin) for f in psd_files]
        results = []
        
        # 使用process_psd_wrapper替代lambda函数
        for result in tqdm(
            pool.imap_unordered(process_psd_wrapper, args),
            total=len(psd_files),
            desc="转换PSD文件"
        ):
            results.append(result)
    
    success_count = sum(results)
    print(f"\n转换完成: 成功 {success_count}/{len(psd_files)} 个文件")

def convert_pdf_to_images(pdf_path):
    """
    使用PyMuPDF将PDF文件转换为PNG图片,每页保存为单独的文件
    
    参数:
    pdf_path -- PDF文件路径
    """
    try:
        # 检查fitz库是否可用
        try:
            import fitz
        except ImportError as e:
            logging.error(f"PyMuPDF (fitz)库导入失败: {e}")
            logging.error("请安装PyMuPDF: pip install PyMuPDF")
            return False

        # 检查文件是否存在和可访问
        if not os.path.exists(pdf_path):
            logging.error(f"PDF文件不存在: {pdf_path}")
            return False

        # 创建输出目录
        output_dir = os.path.splitext(pdf_path)[0]
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            logging.error(f"创建输出目录失败: {e}")
            return False
        
        # 打开PDF文件
        try:
            doc = fitz.open(pdf_path)
            logging.info(f"PDF信息: 页数={doc.page_count}")
        except Exception as e:
            logging.error(f"打开PDF文件失败: {e}")
            return False

        # 转换每一页
        for page_num in range(doc.page_count):
            try:
                page = doc[page_num]
                # 设置更高的缩放因子以获得更好的图像质量
                zoom = 2.0
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                
                # 保存图像
                image_path = os.path.join(output_dir, f'page_{page_num + 1}.png')
                pix.save(image_path)
                logging.info(f"成功保存第 {page_num + 1} 页到 {image_path}")
            except Exception as e:
                logging.error(f"处理第 {page_num + 1} 页时出错: {e}")
                continue

        # 关闭PDF文档
        doc.close()
            
        # 转换完成后将PDF移到回收站
        try:
            send2trash.send2trash(pdf_path)
            logging.info(f"成功转换PDF并移除: {pdf_path}")
            return True
        except Exception as e:
            logging.error(f"移动PDF到回收站失败: {e}")
            return False
        
    except Exception as e:
        logging.error(f"处理PDF文件时出错 {pdf_path}: {e}")
        return False

def convert_pdf_files(directory):
    """转换目录中的所有PDF文件"""
    directory = Path(directory)
    pdf_files = list(directory.rglob('*.pdf'))
    
    if not pdf_files:
        print(f"在 {directory} 中没有找到PDF文件")
        return
    
    with tqdm(total=len(pdf_files), desc="转换PDF文件") as pbar:
        for pdf_file in pdf_files:
            success = convert_pdf_to_images(str(pdf_file))
            pbar.update(1)
            if success:
                pbar.set_description(f"成功转换并移除: {pdf_file.name}")
            else:
                pbar.set_description(f"转换失败: {pdf_file.name}")

def main():
    """主函数修改"""
    # 添加命令行参数解析
    parser = argparse.ArgumentParser(description='文件处理工具')
    parser.add_argument('--clipboard', action='store_true', help='从剪贴板读取路径')
    args = parser.parse_args()
    
    # 获取目录路径
    if args.clipboard:
        input_text = pyperclip.paste()
    else:
        print("请一次性粘贴所有目录路径（每行一个路径，最后输入空行结束）:")
        input_text = ""
        while True:
            line = input()
            if not line:
                break
            input_text += line + "\n"

    # 处理输入的路径
    directories = []
    for path in input_text.strip().split('\n'):
        # 去除可能存在的引号和空白字符
        clean_path = path.strip().strip('"').strip("'").strip()
        if os.path.exists(clean_path):
            directories.append(clean_path)
        else:
            print(f"警告：路径不存在 - {clean_path}")
    
    if not directories:
        print("未输入有效路径，程序退出")
        return
    
    # 修改控制开关部分
    EXECUTE_DELETE = True      # 是否执行删除操作
    EXECUTE_ORGANIZE = True    # 是否执行整理操作
    EXECUTE_EXTRACT = True     # 是否执行解压操作
    PSD_HANDLING = 'convert'   # 'delete': 直接删除PSD, 'convert': 转换为PNG, 'keep': 保留PSD
    PDF_HANDLING = 'convert'   # 'delete': 直接删除PDF, 'convert': 转换为PNG, 'keep': 保留PDF
    USE_RECYCLE_BIN = False    # 转换PSD后是否使用回收站删除原文件
    
    # 删除操作配置
    extensions = ['txt', 'js', 'url', 'htm', 'html', 'docx', 'sai2']
    keywords = ['進捗', '宣伝', '同人誌', '予告', '新刊']
    if PSD_HANDLING == 'delete':
        extensions.append('psd')
    if PDF_HANDLING == 'delete':
        extensions.append('pdf')
    
    # 对每个目录执行操作
    for directory in directories:
        print(f"\n正在处理目录: {directory}")
        # 执行解压操作
        # if EXECUTE_EXTRACT:
        #     print("\n=== 开始解压压缩文件 ===")
        #     extract_all_archives(directory)
            
        # 处理PSD文件
        if PSD_HANDLING == 'convert':
            print("\n=== 开始转换PSD文件 ===")
            convert_psd_files(directory, USE_RECYCLE_BIN)
        # 处理PDF文件
        if PDF_HANDLING == 'convert':
            print("\n=== 开始转换PDF文件 ===")
            convert_pdf_files(directory)
        # 执行删除操作
        if EXECUTE_DELETE:
            print("\n=== 开始删除不需要的文件和文件夹 ===")
            delete_files_by_extensions(directory, extensions)
            delete_empty_folders(directory)
            delete_folders_by_keywords(directory, keywords)
        
        # 执行整理操作
        # if EXECUTE_ORGANIZE:
        #     print("\n=== 开始整理媒体文件 ===")
        #     organize_media_files(directory, directory)
        
        print(f"\n目录 {directory} 处理完成")
    
    print("\n所有操作已完成")

if __name__ == "__main__":
    main()


import os
from pathlib import Path
import logging
import argparse
import pyperclip

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(message)s')

def is_special_char(char):
    """检查字符是否是特殊字符（GBK编码在特定范围内）"""
    try:
        gbk_bytes = char.encode('gbk')
        if len(gbk_bytes) == 2:
            first_byte = gbk_bytes[0]
            second_byte = gbk_bytes[1]
            
            # 扩展日文片假名检测范围
            return (
                (0x83 == first_byte and 0x40 <= second_byte <= 0x96) or  # 片假名
                (0x84 == first_byte and 0x40 <= second_byte <= 0x60) or  # 平假名扩展
                (0x87 == first_byte and 0x40 <= second_byte <= 0xFC) or  # 扩展字符
                (0xA1 <= first_byte <= 0xFE and 0xA1 <= second_byte <= 0xFE)  # 全角字符
            )
        return False
    except:
        return False

def fix_filename_encoding(filename):
    """
    修复文件名编码错误
    主要处理以下情况：
    1. 日文片假名被错误解码为GBK时产生的特殊汉字（编码范围0x8340-0x8396）
    2. 其他可能的编码错误情况（0x82xx, 0x93xx-0x97xx, 0x8Dxx-0x95xx）
    """
    needs_fix = False
    fixed_name = ""
    
    for char in filename:
        try:
            # 获取GBK编码值
            gbk_bytes = char.encode('gbk')
            if len(gbk_bytes) != 2:  # 不是双字节字符
                fixed_name += char
                continue
                
            first_byte, second_byte = gbk_bytes[0], gbk_bytes[1]
            
            # 检查是否在特殊编码范围内
            is_special = False
            if ((0x83 == first_byte and 0x40 <= second_byte <= 0x96) or  # 日文片假名范围
                (0x84 == first_byte and 0x40 <= second_byte <= 0x60) or  # 平假名扩展
                (0x87 == first_byte and 0x40 <= second_byte <= 0xFC) or  # 扩展字符
                (0xA1 <= first_byte <= 0xFE and 0xA1 <= second_byte <= 0xFE)):  # 全角字符
                is_special = True
                
            if is_special:
                needs_fix = True
                # 扩展解码方式支持
                try:
                    # 尝试多种日文编码解码
                    fixed_char = gbk_bytes.decode('shift_jis')
                except:
                    fixed_char = gbk_bytes.decode('cp932', errors='ignore')
            else:
                fixed_char = char
                
            fixed_name += fixed_char
            
        except Exception as e:
            # 如果出现编码错误，保持原字符不变
            fixed_name += char
            
    return needs_fix, fixed_name

def rename_single_file(file_path):
    """重命名单个文件"""
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"文件不存在: {file_path}")
            return False
        
        old_name = file_path.name
        new_name, needs_rename = fix_filename_encoding(old_name)
        
        if needs_rename and old_name != new_name:
            try:
                new_path = file_path.parent / new_name
                file_path.rename(new_path)
                logger.info(f"已重命名: {old_name} -> {new_name}")
                return True
            except Exception as e:
                logger.error(f"重命名失败 '{old_name}': {str(e)}")
                return False
        return False
    except Exception as e:
        logger.error(f"处理文件时出错: {str(e)}")
        return False

def batch_rename_files(directory):
    """批量重命名目录下的所有文件"""
    try:
        directory = Path(directory).resolve()
        logger.info(f"开始处理目录: {directory}")
        
        if not directory.exists():
            logger.error(f"目录不存在: {directory}")
            return
        
        # 收集需要重命名的文件
        rename_list = []
        for file_path in directory.glob('*'):
            if file_path.is_file():
                old_name = file_path.name
                new_name, should_rename = fix_filename_encoding(old_name)
                
                if should_rename and old_name != new_name:
                    print(f"检测到需要重命名: {old_name} -> {new_name}")  # 调试信息
                    rename_list.append((file_path, new_name))
        
        if not rename_list:
            logger.info("没有需要重命名的文件")
            return
            
        # 显示预览信息
        print("\n重命名预览:")
        print("="*50)
        for i, (file_path, new_name) in enumerate(rename_list, 1):
            print(f"{i}. {file_path.name} -> {new_name}")
            if (file_path.parent / new_name).exists():
                print(f"   警告: 目标文件已存在!")
        
        # 请求用户确认
        confirm = input("\n是否确认重命名？(y/N): ").strip().lower()
        if confirm != 'y':
            logger.info("用户取消操作")
            return
            
        # 执行重命名
        success = 0
        for file_path, new_name in rename_list:
            try:
                new_path = file_path.parent / new_name
                if new_path.exists():
                    logger.warning(f"跳过重命名，目标已存在: {new_name}")
                    continue
                file_path.rename(new_path)
                success += 1
                logger.info(f"已重命名: {file_path.name} -> {new_name}")
            except Exception as e:
                logger.error(f"重命名失败 '{file_path.name}': {str(e)}")
        
        logger.info(f"\n重命名完成：成功 {success}/{len(rename_list)} 个文件")
        
    except Exception as e:
        logger.error(f"处理目录时出错: {str(e)}")

def main():
    """主函数"""
    # 添加命令行参数解析
    parser = argparse.ArgumentParser(description='批量修复文件名编码错误')
    parser.add_argument('--clipboard', action='store_true', help='从剪贴板读取路径')
    args = parser.parse_args()
    
    # 获取路径
    if args.clipboard:
        input_text = pyperclip.paste()
    else:
        print("请一次性粘贴所有路径（每行一个路径，最后输入空行结束）:")
        input_text = ""
        while True:
            line = input()
            if not line:
                break
            input_text += line + "\n"

    # 处理输入的路径
    files = []
    directories = []
    
    for path in input_text.strip().split('\n'):
        # 去除可能存在的引号和空白字符
        clean_path = path.strip().strip('"').strip("'").strip()
        if os.path.exists(clean_path):
            if os.path.isfile(clean_path):
                files.append(clean_path)
            else:
                directories.append(clean_path)
        else:
            print(f"警告：路径不存在 - {clean_path}")
    
    if not files and not directories:
        print("未输入有效路径，程序退出")
        return

    # 显示将要处理的内容
    if files:
        print("\n将要处理以下文件:")
        for i, file_path in enumerate(files, 1):
            print(f"{i}. {file_path}")
    
    if directories:
        print("\n将要处理以下目录:")
        for i, directory in enumerate(directories, 1):
            print(f"{i}. {directory}")

    # 请求用户确认
    confirm = input("\n是否确认处理这些路径？(y/N): ").strip().lower()
    if confirm != 'y':
        print("用户取消操作")
        return

    # 处理文件
    if files:
        success = 0
        for file_path in files:
            if rename_single_file(file_path):
                success += 1
        logger.info(f"\n单个文件处理完成：成功 {success}/{len(files)} 个文件")

    # 处理目录
    for directory in directories:
        batch_rename_files(directory)

if __name__ == "__main__":
    main()
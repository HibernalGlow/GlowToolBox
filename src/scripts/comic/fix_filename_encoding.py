import os
import sys
import argparse
import subprocess
import logging
import tempfile
import shutil
import json

def setup_logger(verbose=False):
    logger = logging.getLogger('EncodingFixer')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def load_encoding_map():
    """加载编码映射文件"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    map_file = os.path.join(script_dir, 'encoding_map.json')
    try:
        with open(map_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"无法加载编码映射文件: {e}")
        return None

def fix_filename_with_map(filename: str, encoding_map: dict) -> str:
    """使用字符映射修复文件名"""
    result = filename
    char_mappings = encoding_map.get('character_mappings', {})
    
    # 应用字符映射
    for old_char, new_char in char_mappings.items():
        result = result.replace(old_char, new_char)
    
    return result

def run_encfix(files: list[str], verbose: bool = False) -> bool:
    """运行文件名修复"""
    logger = setup_logger(verbose)
    
    if not files:
        logger.error("未指定文件")
        return False

    # 加载编码映射
    encoding_map = load_encoding_map()
    if not encoding_map:
        logger.error("无法加载编码映射，将使用默认的 encfix 命令")
        return run_encfix_command(files, verbose)

    # 检查文件是否存在
    for file in files:
        if not os.path.exists(file):
            logger.error(f"文件不存在: {file}")
            return False

    # 使用映射修复文件名
    success = True
    for file in files:
        try:
            dirname = os.path.dirname(file)
            filename = os.path.basename(file)
            new_filename = fix_filename_with_map(filename, encoding_map)
            
            if new_filename != filename:
                new_path = os.path.join(dirname, new_filename)
                logger.info(f"重命名: {filename} -> {new_filename}")
                os.rename(file, new_path)
        except Exception as e:
            logger.error(f"处理文件 {file} 时出错: {e}")
            success = False

    return success

def run_encfix_command(files: list[str], verbose: bool = False) -> bool:
    """使用原始的 encfix 命令修复文件名编码"""
    try:
        cmd = ['encfix'] + files
        logger.info(f"执行命令: {' '.join(cmd)}")
        
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            encoding='utf-8',
            errors='replace'
        )
        
        stdout, stderr = process.communicate()
        
        if stdout:
            print(stdout)
        if stderr:
            print(stderr, file=sys.stderr)
            
        return process.returncode == 0
    except Exception as e:
        logger.error(f"执行失败: {str(e)}")
        return False

def demo_fix():
    """演示功能"""
    logger = setup_logger(verbose=True)
    
    # 测试用例
    test_cases = [
        "2021-05-14 úñ3000ííüä╚╦Ñ╩⌐ûÑ╖ñ┴ñπñ≤╛╨╩°ñ╖ñ╞│»ñ▐ñ╟Ñ¼Ñ├Ñ─ÑΩ╖N╓▓ñ¿╗ß(▓ε╖╓╢α╩²) 14[hash-99511b59f3e3e422].txt",
        "搶曽峠杺嫿.cfg",  # 应该是 "東方紅魔郷.cfg"
        "CRH¶¯³µ×é·¢Õ¹Æ×ÏµÍ¼2016.12.jpg",  # 应该是 "CRH动车组发展谱系图2016.12.jpg"
        "%5BFeather%40TSDM%5D%5BSumiSora%26CASO%5D%5BChaos_Child%5D%5B04%5D%5BGB%5D%5B720p%5D.mp4"  # URL编码的文件名
    ]
    
    print("\n=== 编码修复演示 ===")
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 创建测试文件
        test_files = []
        for case in test_cases:
            test_file = os.path.join(temp_dir, case)
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write("测试内容")
            test_files.append(test_file)
            
        # 运行 encfix
        print("\n原始文件名:")
        for file in test_files:
            print(f"- {os.path.basename(file)}")
            
        print("\n修复结果:")
        run_encfix(test_files, verbose=True)
    
    finally:
        # 清理临时目录
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def main():
    parser = argparse.ArgumentParser(description='修复文件名编码问题')
    parser.add_argument('files', nargs='+', help='要修复的文件路径列表')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示详细信息')
    parser.add_argument('--demo', '-d', action='store_true', help='运行演示')
    args = parser.parse_args()
    
    if args.demo:
        demo_fix()
        return
    
    run_encfix(args.files, args.verbose)

if __name__ == "__main__":
    
    main() 
    
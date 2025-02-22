import os
import sys
import argparse
import subprocess
import logging
import tempfile
import zipfile
import shutil

def setup_logger(verbose=False):
    logger = logging.getLogger('ZipFixer')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def run_zipu(zip_path: str, destination: str = None, extract: bool = False, 
             fix: bool = False, encoding: str = None, password: str = None, 
             verbose: bool = False) -> bool:
    """运行 zipu 命令处理 zip 文件"""
    logger = setup_logger(verbose)
    
    if not os.path.exists(zip_path):
        logger.error(f"文件不存在: {zip_path}")
        return False

    # 构建 zipu 命令
    cmd = ['zipu']
    
    if extract:
        cmd.append('--extract')
    if fix:
        cmd.append('--fix')
    if encoding:
        cmd.extend(['--encoding', encoding])
    if password:
        cmd.extend(['--password', password])
    
    cmd.append(zip_path)
    if destination:
        cmd.append(destination)

    try:
        logger.info(f"执行命令: {' '.join(cmd)}")
        # 设置环境变量以处理输出编码
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        # 使用 utf-8 编码运行命令
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            encoding='utf-8',
            errors='replace'
        )
        
        # 读取输出
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
    """改进后的演示功能"""
    logger = setup_logger(verbose=True)
    
    # 更新测试用例（包含多级编码错误）
    test_cases = [
        ("úñ3000ííüä╚╦Ñ╩⌐ûÑ╖ñ┴ñπñ≤╛╨╩°ñ╖ñ╞│»ñ▐ñ╟Ñ¼Ñ├Ñ─ÑΩ╖N╓▓ñ¿╗ß(▓ε╖╓╢α╩²) 14[hash-99511b59f3e3e422].txt", 
         "第3000回日本語同人誌(差分多数) 14[hash-99511b59f3e3e422].txt"),
        ("µªÀµ¡ú.txt", "日本語.txt"),  # UTF-8 -> Latin-1 -> GBK
        ("ãƒ¡ã‚«ãƒ–.txt", "メカブ.txt")  # Shift_JIS -> Latin-1
    ]
    
    print("\n=== 多级编码修复演示 ===")
    temp_dir = tempfile.mkdtemp()
    
    try:
        for i, (corrupted, expected) in enumerate(test_cases, 1):
            print(f"\n测试用例 {i}:")
            print(f"损坏文件名: {corrupted}")
            print(f"期望文件名: {expected}")
            
            # 创建多层错误编码的zip文件
            zip_path = os.path.join(temp_dir, f"test_{i}.zip")
            with zipfile.ZipFile(zip_path, 'w') as zf:
                # 修改后的编码转换链（添加错误处理）
                original_bytes = expected.encode('utf-8')
                try:
                    # 第一步：UTF-8 -> Latin-1 解码
                    latin1_str = original_bytes.decode('latin-1')
                    
                    # 第二步：Latin-1 -> GBK 编码（添加错误处理）
                    gbk_bytes = latin1_str.encode('gbk', errors='replace')  # 替换无效字符
                    
                    # 第三步：GBK -> UTF-8 解码（使用surrogateescape处理错误）
                    corrupted_name = gbk_bytes.decode('utf-8', errors='surrogateescape')
                except UnicodeError as e:
                    logger.error(f"生成测试文件时编码错误: {str(e)}")
                    corrupted_name = expected  # 回退使用原始名称
                
                zf.writestr(corrupted_name, "测试内容")
            
            # 新增多级解码方法
            def multi_step_decoding(name: str) -> str:
                """实现多级编码转换"""
                # 第一级尝试：Latin-1 -> GBK -> UTF-8
                try:
                    step1 = name.encode('latin-1').decode('gbk')
                    return step1
                except UnicodeDecodeError:
                    pass
                
                # 第二级尝试：CP437 -> UTF-8
                try:
                    step2 = name.encode('cp437').decode('utf-8')
                    return step2
                except UnicodeDecodeError:
                    pass
                
                # 第三级尝试：GBK -> Shift_JIS
                try:
                    step3 = name.encode('gbk').decode('shift_jis')
                    return step3
                except UnicodeDecodeError:
                    pass
                
                return name  # 保留原始名称如果所有转换失败
            
            # 运行修复流程
            output_dir = os.path.join(temp_dir, f"output_{i}")
            os.makedirs(output_dir, exist_ok=True)
            
            # 修改后的解压流程
            with zipfile.ZipFile(zip_path, 'r') as zf:
                for fileinfo in zf.infolist():
                    original_name = fileinfo.filename
                    # 应用多级解码
                    fixed_name = multi_step_decoding(original_name)
                    # 提取并重命名文件
                    source = zf.extract(fileinfo, output_dir)
                    target = os.path.join(output_dir, fixed_name)
                    os.rename(source, target)
                    print(f"修复结果: {original_name} → {fixed_name}")
            
            print("-" * 50)
    
    finally:
        shutil.rmtree(temp_dir)

def main():
    parser = argparse.ArgumentParser(description='修复 ZIP 文件中的文件名编码问题')
    parser.add_argument('zip_file', nargs='?', help='要修复的 ZIP 文件路径')
    parser.add_argument('destination', nargs='?', help='解压目标路径')
    parser.add_argument('--extract', '-x', action='store_true', help='解压 zip 文件到指定目录')
    parser.add_argument('--fix', '-f', action='store_true', help='创建新的 UTF-8 文件名的 zip 文件')
    parser.add_argument('--encoding', '-enc', help='zip 文件使用的编码: shift-jis, cp932...')
    parser.add_argument('--password', '-pwd', help='zip 文件的密码')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示详细信息')
    parser.add_argument('--demo', '-d', action='store_true', help='运行演示')
    args = parser.parse_args()
    
    if args.demo:
        demo_fix()
        return
        
    if not args.zip_file:
        parser.print_help()
        return
    
    run_zipu(
        args.zip_file,
        args.destination,
        extract=args.extract,
        fix=args.fix,
        encoding=args.encoding,
        password=args.password,
        verbose=args.verbose
    )

if __name__ == "__main__":
    demo_fix()
    main() 
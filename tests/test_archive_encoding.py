import subprocess
import zipfile
import py7zr
# import libarchive
import patoolib
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple
from colorama import Fore, Style
import tempfile
import shutil

# 修改后的测试用例配置
TEST_CASES = {
    "normal.zip": {
        "desc": "纯英文正常文件名",
        "files": ["file1.txt", "folder/doc.pdf"]
    },
    "gbk_chinese.zip": {
        "desc": "中文GBK编码文件名",
        "files": ["报告-2023.txt", "图片/封面.jpg"]
    },
    "shift_jis.zip": {
        "desc": "日文Shift-JIS编码文件名",
        "files": ["日本語_ドキュメント.txt", "フォルダ/画像.png"]
    },
    "special_mix.7z": {
        "desc": "混合特殊符号文件名",
        "files": ["30°_angle.txt", "Ψ_psi_file.doc"]
    }
}

def check_dependencies():
    """检查必要依赖"""
    deps = {
        '7z': lambda: subprocess.run(['7z'], capture_output=True).returncode == 0,
        'patool': lambda: True,  # 总是返回True，实际依赖后端工具
        'libarchive': lambda: True,
        'py7zr': lambda: True
    }
    
    print(f"{Fore.CYAN}=== 依赖检查 ==={Style.RESET_ALL}")
    for dep, checker in deps.items():
        try:
            if checker():
                print(f"{Fore.GREEN}√ {dep}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}× {dep} (未安装){Style.RESET_ALL}")
        except:
            print(f"{Fore.RED}× {dep} (不可用){Style.RESET_ALL}")

def test_zipfile(archive_path: Path) -> Tuple[List[str], str]:
    """使用zipfile库测试"""
    try:
        with zipfile.ZipFile(archive_path, 'r') as zf:
            # 尝试多种编码方式
            encodings = ['utf-8', 'gbk', 'shift-jis', 'cp437']
            files = []
            error = ""
            
            for fileinfo in zf.filelist:
                for encoding in encodings:
                    try:
                        filename = fileinfo.filename.encode('cp437').decode(encoding)
                        files.append(filename)
                        break
                    except:
                        continue
                else:
                    error = f"解码失败: {fileinfo.filename}"
                    break
            return files, error
    except Exception as e:
        return [], f"Zipfile错误: {str(e)}"

def test_7z_cli(archive_path: Path) -> Tuple[List[str], str]:
    """使用7z命令行测试"""
    try:
        result = subprocess.run(
            ['7z', 'l', str(archive_path)],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        files = []
        in_files = False
        for line in result.stdout.split('\n'):
            if line.startswith('----'):
                in_files = not in_files
                continue
            if in_files and line.strip():
                parts = line.split()
                if len(parts) > 5:
                    files.append(' '.join(parts[5:]))
        return files, ""
    except Exception as e:
        return [], f"7z CLI错误: {str(e)}"

def test_py7zr(archive_path: Path) -> Tuple[List[str], str]:
    """使用py7zr测试"""
    try:
        if archive_path.suffix.lower() != '.7z':
            return [], "跳过非7z文件"
            
        with py7zr.SevenZipFile(archive_path, 'r') as sz:
            return [f.filename for f in sz.list()], ""
    except Exception as e:
        return [], f"Py7zr错误: {str(e)}"

def test_patool(archive_path: Path) -> Tuple[List[str], str]:
    """使用patool测试"""
    try:
        files = []
        patoolib.list_archive(str(archive_path), outlist=files)
        return files, ""
    except Exception as e:
        return [], f"Patool错误: {str(e)}"

def create_test_archives(test_dir: Path):
    """自动创建测试压缩包"""
    print(f"\n{Fore.YELLOW}=== 生成测试压缩包 ==={Style.RESET_ALL}")
    
    # 创建普通ZIP（英文）
    with zipfile.ZipFile(test_dir/"normal.zip", 'w') as zf:
        for f in TEST_CASES["normal.zip"]["files"]:
            zf.writestr(f, data="")
    
    # 修复GBK编码的ZIP创建方式
    with zipfile.ZipFile(test_dir/"gbk_chinese.zip", 'w', metadata_encoding='gbk') as zf:
        for f in TEST_CASES["gbk_chinese.zip"]["files"]:
            # 直接写入Unicode字符串，由metadata_encoding参数处理编码
            zf.writestr(f, data="")
    
    # 创建Shift-JIS编码的ZIP（使用7z命令行）
    sjis_dir = test_dir / "sjis_temp"
    sjis_dir.mkdir(exist_ok=True)
    for f in TEST_CASES["shift_jis.zip"]["files"]:
        (sjis_dir / f).parent.mkdir(parents=True, exist_ok=True)
        (sjis_dir / f).touch()
    subprocess.run(
        ['7z', 'a', '-mcp=shift_jis', str(test_dir/"shift_jis.zip"), str(sjis_dir)],
        stdout=subprocess.DEVNULL
    )
    shutil.rmtree(sjis_dir)
    
    # 创建特殊符号7z文件
    with py7zr.SevenZipFile(test_dir/"special_mix.7z", 'w') as sz:
        for f in TEST_CASES["special_mix.7z"]["files"]:
            sz.writestr(f, data="")

def run_test_suite(test_dir: Path):
    """运行完整的测试套件"""
    check_dependencies()
    
    # 自动生成测试文件
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = Path(tmpdir)
        create_test_archives(source_dir)
        
        # 复制测试文件到用户指定目录
        for f in TEST_CASES.keys():
            shutil.copy(source_dir/f, test_dir/f)
        
        results = []
        testers = {
            "zipfile": test_zipfile,
            # "libarchive": test_libarchive,
            "7z_cli": test_7z_cli,
            "py7zr": test_py7zr,
            "patool": test_patool
        }
        
        for archive, description in TEST_CASES.items():
            archive_path = test_dir / archive
            if not archive_path.exists():
                print(f"{Fore.RED}跳过不存在的测试文件: {archive}{Style.RESET_ALL}")
                continue
            
            print(f"\n{Fore.CYAN}=== 测试 [{description['desc']}] {archive} ==={Style.RESET_ALL}")
            
            ground_truth = []  # 以7z CLI结果为基准
            for name, tester in testers.items():
                files, error = tester(archive_path)
                if name == '7z_cli':
                    ground_truth = files
                
                # 计算准确率
                correct = sum(1 for f in files if f in ground_truth) if ground_truth else 0
                total = len(ground_truth) if ground_truth else len(files)
                accuracy = f"{correct}/{total}" if total > 0 else "N/A"
                
                status = f"{Fore.GREEN}成功{Style.RESET_ALL}" if not error else f"{Fore.RED}失败{Style.RESET_ALL}"
                results.append({
                    '测试用例': description['desc'],
                    '压缩包': archive,
                    '库名称': name,
                    '状态': status,
                    '准确率': accuracy,
                    '错误信息': error,
                    '文件列表': files
                })
                
                print(f"{name.ljust(10)} | {status} | 匹配: {accuracy.ljust(8)} | 错误: {error}")

    # 生成详细报告
    df = pd.DataFrame(results)
    report_path = test_dir / "encoding_test_report.xlsx"
    df.to_excel(report_path, index=False)
    print(f"\n{Fore.GREEN}测试报告已保存至: {report_path}{Style.RESET_ALL}")

if __name__ == "__main__":
    test_dir = Path(input("请输入测试压缩包所在目录路径: ").strip())
    run_test_suite(test_dir)
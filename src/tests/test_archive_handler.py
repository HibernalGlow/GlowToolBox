import unittest
import zipfile
from pathlib import Path
from nodes.pics.filter.statistics_manager import ArchiveHandler
import tempfile
import os

class TestArchiveHandler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 创建测试用压缩包
        cls.test_files = {
            '你好.txt': 'gbk',          # 简体中文
            '測試.txt': 'big5',         # 繁体中文
            'あい.txt': 'shift-jis',    # 日文
            '안녕.txt': 'euc-kr',       # 韩文
            'test[测试].txt': 'cp437',  # 特殊符号
            'τστ.txt': 'utf-8'         # UTF-8
        }
        
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.zip_path = Path(cls.temp_dir.name) / "test.zip"
        
        # 使用不同编码创建文件
        with zipfile.ZipFile(cls.zip_path, 'w') as zf:
            for name, enc in cls.test_files.items():
                # 创建ZipInfo对象设置编码标志
                zinfo = zipfile.ZipInfo.from_file(Path('dummy.txt'))
                zinfo.filename = name.encode(enc).decode('cp437', 'replace')
                
                # 设置UTF-8标志位（当编码是UTF-8时）
                if enc.lower() == 'utf-8':
                    zinfo.flag_bits |= 0x800
                
                zf.writestr(zinfo, b'')

    def test_filename_decoding(self):
        handler = ArchiveHandler()
        results = {}
        
        for filename, content in handler.list_contents(self.zip_path):
            results[filename] = filename in self.test_files
            
        # 验证所有文件名都能正确解码
        for original_name in self.test_files:
            self.assertTrue(
                original_name in results,
                f"文件名解码失败: {original_name}"
            )
            
        print("\n测试结果：")
        for filename, success in results.items():
            status = "✅" if success else "❌"
            print(f"{status} {filename}")

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

if __name__ == "__main__":
    unittest.main() 
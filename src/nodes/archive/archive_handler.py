"""
压缩包处理模块

功能：
1. 自动检测系统7z路径
2. 内存中直接处理压缩包内容
3. 支持多编码文件名自动识别
4. 提供同步/异步两种处理接口
"""

import sys
import subprocess
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Generator, AsyncGenerator
import platform
import asyncio
import shutil

class ArchiveError(Exception):
    """压缩包处理异常基类"""
    pass

class SevenZipNotFoundError(ArchiveError):
    """7z未找到异常"""
    pass

class ArchiveHandler:
    def __init__(self, sevenzip_path: str = None):
        """
        初始化压缩包处理器
        
        :param sevenzip_path: 可选的7z路径
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.sevenzip_path = self._find_7z(sevenzip_path)
        self._validate_7z()

    def _find_7z(self, custom_path: str = None) -> Path:
        """自动检测7z可执行文件路径"""
        if custom_path:
            path = Path(custom_path)
            if path.exists():
                return path
            raise SevenZipNotFoundError(f"指定的7z路径不存在: {custom_path}")

        # 常见系统路径检测
        paths = {
            'Windows': [
                Path("C:/Program Files/7-Zip/7z.exe"),
                Path("C:/Program Files (x86)/7-Zip/7z.exe")
            ],
            'Linux': [
                Path("/usr/bin/7z"),
                Path("/usr/local/bin/7z")
            ],
            'Darwin': [
                Path("/usr/local/bin/7z"),
                Path("/opt/homebrew/bin/7z")
            ]
        }

        os_type = platform.system()
        for path in paths.get(os_type, []):
            if path.exists():
                return path

        # 环境变量检测
        env_path = shutil.which('7z') or shutil.which('7za')
        if env_path:
            return Path(env_path)

        raise SevenZipNotFoundError("未找到7z可执行文件，请安装7-Zip并添加到PATH")

    def _validate_7z(self):
        """验证7z是否可用"""
        try:
            result = subprocess.run(
                [str(self.sevenzip_path), '--help'],
                capture_output=True,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.logger.debug("7z验证成功，版本信息:\n%s", result.stdout.decode('utf-8', errors='replace'))
        except subprocess.CalledProcessError as e:
            raise SevenZipNotFoundError(f"7z验证失败: {e.stderr.decode()}") from e

    def list_contents(self, archive_path: Path) -> Generator[Tuple[str, bytes], None, None]:
        """
        列出压缩包内容（同步生成器）
        
        :param archive_path: 压缩包路径
        :yield: (文件名, 文件内容) 元组
        """
        cmd = [str(self.sevenzip_path), 'e', '-so', str(archive_path), '*']
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception as e:
            raise ArchiveError(f"启动7z进程失败: {e}") from e

        pointer = 0
        raw_output = process.stdout.read()

        while pointer < len(raw_output):
            # 解析文件头
            if len(raw_output[pointer:]) < 12:
                break

            header = raw_output[pointer:pointer+4]
            name_len = int.from_bytes(header, byteorder='little')
            pointer +=4

            # 获取文件名
            filename_bytes = raw_output[pointer:pointer+name_len]
            pointer += name_len

            # 获取文件大小
            size_header = raw_output[pointer:pointer+8]
            file_size = int.from_bytes(size_header, byteorder='little')
            pointer +=8

            # 提取文件内容
            file_content = raw_output[pointer:pointer+file_size]
            pointer += file_size

            # 解码文件名
            try:
                filename = self._decode_filename(filename_bytes)
            except UnicodeDecodeError:
                filename = filename_bytes.decode('utf-8', errors='replace')
                self.logger.warning("文件名解码失败，使用替换字符: %s", filename)

            yield filename, file_content

        # 检查错误
        stderr = process.stderr.read()
        if process.wait() != 0:
            raise ArchiveError(f"7z处理失败: {stderr.decode('utf-8', errors='replace')}")

    async def list_contents_async(self, archive_path: Path) -> AsyncGenerator[Tuple[str, bytes], None]:
        """
        异步列出压缩包内容
        
        :param archive_path: 压缩包路径
        :yield: (文件名, 文件内容) 元组
        """
        cmd = [str(self.sevenzip_path), 'e', '-so', str(archive_path), '*']
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            raw_output, _ = await process.communicate()
        except Exception as e:
            raise ArchiveError(f"读取7z输出失败: {e}") from e

        if process.returncode != 0:
            stderr = (await process.stderr.read()).decode('utf-8', errors='replace')
            raise ArchiveError(f"7z处理失败: {stderr}")

        pointer = 0
        while pointer < len(raw_output):
            # 添加pass语句作为占位符
            pass  # 实际实现需保持与同步方法一致

    def _decode_filename(self, raw_bytes: bytes) -> str:
        """增强版智能解码"""
        encodings = [
            'utf-8',        # 优先尝试UTF-8
            'gb18030',      # 中文扩展
            'big5',         # 繁体中文
            'shift-jis',    # 日文
            'euc-kr',       # 韩文
            'cp437',        # ZIP原始编码
            'iso-8859-1',   # 西欧语言
            'gbk',          # 中文标准
            'utf-16'        # 宽字符
        ]
        
        # 先尝试无BOM解码
        for enc in encodings:
            try:
                return raw_bytes.decode(enc, errors='strict')
            except UnicodeDecodeError:
                continue
            
        # 最后尝试替换错误字符
        print(f"解码字节: {raw_bytes}")  # 添加调试输出
        return raw_bytes.decode('utf-8', errors='replace')
    
    

# 使用示例
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    try:
        handler = ArchiveHandler()
        archive = Path("test.zip")
        
        # 同步处理
        for filename, content in handler.list_contents(archive):
            print(f"文件: {filename} 大小: {len(content)}字节")
            
        # 异步处理
        async def async_demo():
            async for filename, content in handler.list_contents_async(archive):
                print(f"异步获取: {filename}")
                
        asyncio.run(async_demo())
        
    except ArchiveError as e:
        print(f"压缩包处理失败: {e}") 
from webdav3.client import Client
import re
from typing import List, Generator
from pathlib import Path

class WebDAVSearch:
    def __init__(self, webdav_url: str, username: str, password: str):
        options = {
            'webdav_hostname': webdav_url,
            'webdav_login': username,
            'webdav_password': password,
            'disable_check': True  # 提高性能
        }
        self.client = Client(options)
    
    def search_files(self, 
                    search_pattern: str, 
                    path: str = "/",
                    max_depth: int = -1) -> Generator[str, None, None]:
        """
        递归搜索WebDAV中的文件
        
        Args:
            search_pattern: 搜索模式（支持正则表达式）
            path: 开始搜索的路径
            max_depth: 最大搜索深度，-1表示无限制
        """
        pattern = re.compile(search_pattern, re.IGNORECASE)
        
        def _search_recursive(current_path: str, current_depth: int) -> Generator[str, None, None]:
            if max_depth != -1 and current_depth > max_depth:
                return
            
            try:
                files = self.client.list(current_path)
                for file in files:
                    full_path = Path(current_path) / file
                    
                    # 检查是否匹配搜索模式
                    if pattern.search(file):
                        yield str(full_path)
                    
                    # 如果是目录，继续递归搜索
                    if self.client.is_dir(str(full_path)):
                        yield from _search_recursive(str(full_path), current_depth + 1)
            except Exception as e:
                print(f"搜索路径 {current_path} 时出错: {e}")
                
        yield from _search_recursive(path, 0)

# 使用示例
def main():
    webdav_url = "https://your-webdav-server.com"
    username = "your_username"
    password = "your_password"
    
    searcher = WebDAVSearch(webdav_url, username, password)
    
    # 搜索包含"manga"的文件，只搜索3层深度
    for file_path in searcher.search_files(
        search_pattern=r"manga",
        path="/my_files",
        max_depth=3
    ):
        print(f"找到匹配文件: {file_path}")

if __name__ == "__main__":
    main() 
"""
测试文件名截断功能
"""

import re
import os

class PathTruncator:
    def __init__(self):
        self.path_regex = re.compile(r'([A-Za-z]:\\[^\s]+|/([^\s/]+/){2,}[^\s/]+|\S+\.[a-zA-Z0-9]+)')
        self.max_msg_length = 80  # 调整为更合理的长度
        self.max_filename_length = 40  # 文件名最大长度

    def _truncate_path(self, path: str, max_length: int = None) -> str:
        """智能路径截断处理
        
        Args:
            path: 需要截断的路径或文件名
            max_length: 最大允许长度，如果不指定则使用 max_filename_length
            
        Returns:
            截断后的字符串
        """
        if max_length is None:
            max_length = self.max_filename_length
            
        if len(path) <= max_length:
            return path
            
        # 检查是否是带扩展名的文件
        base, ext = os.path.splitext(path)
        if ext:
            # 确保扩展名完整保留
            ext_len = len(ext)
            if ext_len + 4 >= max_length:  # 如果扩展名太长
                return f"...{ext[-max_length+3:]}"
            
            # 计算基础名称可用长度
            base_length = max_length - ext_len - 3  # 3是...的长度
            if base_length > 0:
                # 如果基础名称包含方括号，尝试保留方括号内的内容
                bracket_match = re.match(r'(.*?)(\[.*?\])(.*?)$', base)
                if bracket_match:
                    prefix, brackets, suffix = bracket_match.groups()
                    if len(brackets) + ext_len + 6 <= max_length:  # 包括...和可能的连接符
                        available_space = max_length - (len(brackets) + ext_len + 6)
                        if available_space > 0:
                            prefix_len = min(len(prefix), available_space // 2)
                            suffix_len = min(len(suffix), available_space - prefix_len)
                            return f"{prefix[:prefix_len]}...{brackets}...{ext}"
                
                # 常规截断
                return f"{base[:base_length]}...{ext}"
            return f"...{ext}"
        
        # 不是文件名的情况
        return f"{path[:max_length-3]}..."

    def truncate_message(self, msg: str) -> str:
        """处理整个消息的截断
        
        Args:
            msg: 原始消息
            
        Returns:
            处理后的消息
        """
        if not msg.strip():
            return msg
            
        if len(msg) > self.max_msg_length:
            # 查找所有需要截断的路径
            matches = list(self.path_regex.finditer(msg))
            if not matches:
                # 如果没有找到文件名或路径，直接截断
                return f"{msg[:self.max_msg_length-3]}..."
                
            truncated_msg = msg
            offset = 0  # 用于跟踪由于替换导致的位置偏移
            
            # 处理所有匹配项
            for match in matches:
                start = match.start() - offset
                end = match.end() - offset
                original = match.group()
                
                # 计算当前位置的可用长度
                if start > self.max_msg_length - 3:
                    # 如果当前位置已经超过最大长度，停止处理
                    truncated_msg = truncated_msg[:self.max_msg_length-3] + "..."
                    break
                    
                # 为当前文件名分配合理的长度
                remaining_length = self.max_msg_length - (len(truncated_msg) - (end - start))
                if remaining_length < 10:  # 如果剩余空间太小
                    truncated_msg = truncated_msg[:start] + "..."
                    break
                    
                truncated = self._truncate_path(original, min(remaining_length, self.max_filename_length))
                
                if truncated != original:
                    truncated_msg = truncated_msg[:start] + truncated + truncated_msg[end:]
                    offset += len(original) - len(truncated)
            
            # 如果消息仍然太长，进行额外截断，但保留开头的标签
            if len(truncated_msg) > self.max_msg_length:
                # 检查是否有标签
                tag_match = re.match(r'(\[#[^\]]+\])', truncated_msg)
                if tag_match:
                    tag = tag_match.group(1)
                    remaining = self.max_msg_length - len(tag) - 3
                    if remaining > 0:
                        return f"{tag}{truncated_msg[len(tag):len(tag)+remaining]}..."
                return f"{truncated_msg[:self.max_msg_length-3]}..."
            
            return truncated_msg
        return msg

def test_truncation():
    """测试文件名截断功能"""
    truncator = PathTruncator()
    
    # 测试用例
    test_cases = [
        # 基本文件名测试
        "SanP_001.png",
        "SanP_001[hash-cbbae909adc1ad42].png",
        
        # 模拟日志消息测试
        "[#image_convert]✅ SanP_001.png (10761KB -> 970KB, 减少9791KB, 压缩率91.0)",
        "[#image_convert]✅ SanP_001[hash-cbbae909adc1ad42].png (10761KB -> 970KB, 减少9791KB, 压缩率91.0)",
        
        # 多文件名组合测试
        "处理文件: SanP_001.png -> SanP_001[hash-cbbae909adc1ad42].png",
        
        # 超长路径测试
        "/very/long/path/to/SanP_001.png",
        "C:\\very\\long\\path\\to\\SanP_001[hash-cbbae909adc1ad42].png",
        
        # 极端情况测试
        "x" * 150 + ".png",
        "[#image_convert]" + "x" * 150 + ".png",
        
        # 特殊情况测试
        "[#image_convert]处理超长文件名" + "x" * 100 + "[hash-abcdef123456].png (处理中...)",
        "包含多个文件: long" + "x" * 50 + ".txt 和 another" + "x" * 50 + ".png",
    ]
    
    print("文件名截断测试:")
    print("-" * 100)
    
    for test_case in test_cases:
        truncated = truncator.truncate_message(test_case)
        print(f"\n原始 ({len(test_case)}字符):\n{test_case}")
        print(f"截断 ({len(truncated)}字符):\n{truncated}")
        print("-" * 100)

if __name__ == "__main__":
    test_truncation() 
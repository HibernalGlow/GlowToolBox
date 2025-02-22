import os
import logging
import pyperclip
from typing import List, Optional
from ..tui.textual_logger import TextualLoggerManager

logger = logging.getLogger(__name__)

class InputHandler:
    """通用输入处理类"""
    
    @staticmethod
    def get_clipboard_content() -> str:
        """
        获取剪贴板内容
        
        Returns:
            str: 剪贴板内容
        """
        try:
            return pyperclip.paste()
        except Exception as e:
            logger.error(f"从剪贴板读取失败: {e}")
            return ""
            
    @staticmethod
    def get_manual_input(prompt: str = "请输入内容（输入空行结束）：") -> List[str]:
        """
        获取用户手动输入的多行内容
        
        Args:
            prompt: 提示信息
            
        Returns:
            List[str]: 输入的内容列表
        """
        print(prompt)
        lines = []
        while True:
            line = input().strip()
            if not line:
                break
            lines.append(line)
        return lines
        
    @staticmethod
    def get_input_paths(
        cli_paths: Optional[List[str]] = None,
        use_clipboard: bool = True,
        allow_manual: bool = True,
        path_validator: Optional[callable] = os.path.exists,
        path_normalizer: Optional[callable] = None
    ) -> List[str]:
        """
        获取输入路径，支持多种输入方式
        
        Args:
            cli_paths: 命令行参数中的路径列表
            use_clipboard: 是否使用剪贴板内容
            allow_manual: 是否允许手动输入
            path_validator: 路径验证函数
            path_normalizer: 路径规范化函数
            
        Returns:
            List[str]: 有效的路径列表
        """
        paths = []
        
        # 处理命令行参数
        if cli_paths:
            paths.extend(cli_paths)
            
        # 处理剪贴板内容
        if use_clipboard and (not paths or use_clipboard):
            clipboard_content = InputHandler.get_clipboard_content()
            if clipboard_content:
                clipboard_paths = [
                    line.strip()
                    for line in clipboard_content.splitlines()
                    if line.strip()
                ]
                paths.extend(clipboard_paths)
                logger.info(f"从剪贴板读取了 {len(clipboard_paths)} 个路径")
                
        # 手动输入
        if allow_manual and not paths:
            manual_paths = InputHandler.get_manual_input("请输入路径（每行一个，输入空行结束）：")
            paths.extend(manual_paths)
            
        # 规范化路径
        if path_normalizer:
            paths = [path_normalizer(p) for p in paths]
            
        # 验证路径
        if path_validator:
            valid_paths = []
            for p in paths:
                if path_validator(p):
                    valid_paths.append(p)
                else:
                    logger.warning(f"路径无效: {p}")
            return valid_paths
            
        return paths
        

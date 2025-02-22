from typing import Dict, Any, Optional, List, Callable
import json
import sys
import os
import argparse
from nodes.tui.textual_preset import create_config_app

class ModeManager:
    """通用模式管理器，支持TUI、调试和命令行三种模式"""
    
    def __init__(self, 
                 config_path: Optional[str] = None,
                 config: Optional[Dict] = None,
                 cli_parser_setup: Optional[Callable] = None,
                 application_runner: Optional[Callable] = None):
        """
        初始化模式管理器
        
        Args:
            config_path: 配置文件路径，如果提供则从文件加载配置
            config: 配置字典，直接提供配置
            cli_parser_setup: 命令行参数解析器设置函数
            application_runner: 应用程序运行函数
        """
        self.config = self._load_config(config_path) if config_path else config or {}
        self.cli_parser_setup = cli_parser_setup
        self.application_runner = application_runner
        
    def _load_config(self, config_path: str) -> Dict:
        """从文件加载配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return {}
            
    def run_tui(self, on_run: Optional[Callable] = None) -> bool:
        """
        运行TUI模式
        
        Args:
            on_run: TUI回调函数，处理TUI界面的参数
            
        Returns:
            bool: 是否成功执行
        """
        if not self.config.get('tui_config'):
            print("未找到TUI配置")
            return False
            
        def default_on_run(params: dict):
            """默认TUI回调函数"""
            args = []
            
            # 添加选中的选项
            for arg, enabled in params['options'].items():
                if enabled:
                    args.append(arg)
            
            # 添加输入值
            for arg, value in params['inputs'].items():
                if value:
                    args.extend([arg, value])
            
            # 如果选择了预设，添加预设特定的参数
            if params.get('preset'):
                preset_name = params['preset']
                preset_config = self.config['tui_config']['preset_configs'].get(preset_name, {})
                if 'extra_args' in preset_config:
                    args.extend(preset_config['extra_args'])
            
            # 运行命令行模式
            return self.run_cli(args)
        
        # 创建TUI应用
        app = create_config_app(
            program=sys.argv[0],
            checkbox_options=self.config['tui_config']['checkbox_options'],
            input_options=self.config['tui_config']['input_options'],
            title=self.config['tui_config'].get('title', "配置界面"),
            preset_configs=self.config['tui_config'].get('preset_configs'),
            on_run=on_run or default_on_run
        )
        
        # 运行TUI应用
        app.run()
        return True
        
    def run_debug(self, debugger_handler: Optional[Callable] = None) -> bool:
        """
        运行调试模式
        
        Args:
            debugger_handler: 自定义调试处理器
            
        Returns:
            bool: 是否成功执行
        """
        if not self.config.get('debug_config'):
            print("未找到调试模式配置")
            return False
            
        def default_debugger():
            """默认调试处理器"""
            base_modes = self.config['debug_config']['base_modes']
            last_config_file = self.config['debug_config'].get('last_config_file', 'last_debug_config.json')
            
            # 加载上次配置
            last_config = None
            try:
                if os.path.exists(last_config_file):
                    with open(last_config_file, 'r', encoding='utf-8') as f:
                        last_config = json.load(f)
            except Exception:
                pass
            
            while True:
                print("\n=== 调试模式选项 ===")
                print("\n基础模式:")
                for key, mode in base_modes.items():
                    print(f"{key}. {mode['name']}")
                
                if last_config:
                    print("\n上次配置:")
                    print(f"模式: {base_modes[last_config['mode']]['name']}")
                    print("参数:", " ".join(last_config['args']))
                    print("\n选项:")
                    print("L. 使用上次配置")
                    print("N. 使用新配置")
                    choice = input("\n请选择 (L/N 或直接选择模式 1-4): ").strip().upper()
                    
                    if choice == 'L':
                        return last_config['args']
                    elif choice == 'N':
                        pass
                    elif not choice:
                        return []
                    elif choice in base_modes:
                        mode_choice = choice
                    else:
                        print("❌ 无效的选择，请重试")
                        continue
                else:
                    mode_choice = input("\n请选择基础模式(1-4): ").strip()
                    if not mode_choice:
                        return []
                    if mode_choice not in base_modes:
                        print("❌ 无效的模式选择，请重试")
                        continue
                
                selected_mode = base_modes[mode_choice]
                final_args = []
                
                # 添加基础参数和默认值
                for arg in selected_mode["base_args"]:
                    if arg.startswith('-'):
                        param_key = arg.lstrip('-').replace('-', '_')
                        if param_key in selected_mode.get("default_params", {}):
                            final_args.extend([arg, selected_mode["default_params"][param_key]])
                        else:
                            final_args.append(arg)
                    else:
                        final_args.append(arg)
                
                # 保存配置
                try:
                    with open(last_config_file, 'w', encoding='utf-8') as f:
                        json.dump({
                            "mode": mode_choice,
                            "args": final_args
                        }, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
                
                return final_args
        
        # 使用自定义或默认调试处理器
        handler = debugger_handler or default_debugger
        selected_options = handler()
        
        if selected_options:
            return self.run_cli(selected_options)
        return False
        
    def run_cli(self, cli_args: Optional[List[str]] = None) -> bool:
        """
        运行命令行模式
        
        Args:
            cli_args: 命令行参数列表
            
        Returns:
            bool: 是否成功执行
        """
        if not self.cli_parser_setup:
            print("未设置命令行参数解析器")
            return False
            
        parser = self.cli_parser_setup()
        args = parser.parse_args(cli_args)
        
        if not self.application_runner:
            print("未设置应用程序运行函数")
            return False
            
        return self.application_runner(args)
        
    def create_default_cli_parser(self) -> argparse.ArgumentParser:
        """创建默认的命令行参数解析器"""
        parser = argparse.ArgumentParser(
            description=self.config.get('cli_config', {}).get('description', "命令行工具")
        )
        
        # 添加配置中定义的参数
        for arg in self.config.get('cli_config', {}).get('arguments', []):
            kwargs = {
                'help': arg.get('help'),
                'type': eval(arg['type']) if isinstance(arg.get('type'), str) else arg.get('type'),
                'default': arg.get('default'),
                'choices': arg.get('choices'),
                'action': arg.get('action')
            }
            # 移除None值的键
            kwargs = {k: v for k, v in kwargs.items() if v is not None}
            
            if 'short' in arg:
                parser.add_argument(arg['short'], arg['name'], **kwargs)
            else:
                parser.add_argument(arg['name'], **kwargs)
        
        return parser

def create_mode_manager(
    config_path: Optional[str] = None,
    config: Optional[Dict] = None,
    cli_parser_setup: Optional[Callable] = None,
    application_runner: Optional[Callable] = None
) -> ModeManager:
    """
    创建模式管理器的便捷函数
    
    Args:
        config_path: 配置文件路径
        config: 配置字典
        cli_parser_setup: 命令行参数解析器设置函数
        application_runner: 应用程序运行函数
        
    Returns:
        ModeManager: 模式管理器实例
    """
    return ModeManager(
        config_path=config_path,
        config=config,
        cli_parser_setup=cli_parser_setup,
        application_runner=application_runner
    ) 
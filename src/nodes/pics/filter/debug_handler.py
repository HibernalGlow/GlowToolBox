import json
import os
import logging

class DebuggerHandler:
    LAST_CONFIG_FILE = "last_debug_config.json"

    @staticmethod
    def save_last_config(mode_choice, final_args):
        """保存最后一次使用的配置"""
        try:
            config = {
                "mode": mode_choice,
                "args": final_args
            }
            with open(DebuggerHandler.LAST_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.info(f"[#update_log]保存配置失败: {e}")

    @staticmethod
    def load_last_config():
        """加载上次使用的配置"""
        try:
            if os.path.exists(DebuggerHandler.LAST_CONFIG_FILE):
                with open(DebuggerHandler.LAST_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logging.info(f"[#update_log]加载配置失败: {e}")
        return None

    @staticmethod
    def get_debugger_options():
        """交互式调试模式菜单"""
        # 基础模式选项
        base_modes = {
            "1": {"name": "去小图模式", "base_args": ["-rs"], "default_params": {"ms": "631"}},
            "2": {"name": "去重复模式", "base_args": ["-rd"], "default_params": {"hd": "12", "rhd": "12"}},
            "3": {"name": "去黑白模式", "base_args": ["-rg"]},
            "4": {"name": "合并处理模式", "base_args": ["-ma", "-rs", "-rd", "-rg"], 
                  "default_params": {"ms": "631", "hd": "12", "rhd": "12"}}
        }
        
        # 可配置参数选项
        param_options = {
            "ms": {"name": "最小尺寸", "arg": "-ms", "default": "631", "type": int},
            "hd": {"name": "汉明距离", "arg": "-hd", "default": "12", "type": int},
            "rhd": {"name": "参考汉明距离", "arg": "-rhd", "default": "12", "type": int},
            "bm": {"name": "备份模式", "arg": "-bm", "default": "keep", "choices": ["keep", "recycle", "delete"]},
            "c": {"name": "从剪贴板读取", "arg": "-c", "is_flag": True},
            "mw": {"name": "最大线程数", "arg": "-mw", "default": "4", "type": int}
        }

        # 加载上次配置
        last_config = DebuggerHandler.load_last_config()
        
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
                    pass  # 继续使用新配置
                elif not choice:
                    return []
                elif choice in base_modes:
                    mode_choice = choice
                else:
                    print("❌ 无效的选择，请重试")
                    continue
            else:
                # 获取基础模式选择
                mode_choice = input("\n请选择基础模式(1-4): ").strip()
                if not mode_choice:
                    return []
                
                if mode_choice not in base_modes:
                    print("❌ 无效的模式选择，请重试")
                    continue
            
            selected_mode = base_modes[mode_choice]
            final_args = selected_mode["base_args"].copy()
            
            # 添加默认参数
            if "default_params" in selected_mode:
                for param_key, default_value in selected_mode["default_params"].items():
                    if param_key in param_options:
                        param = param_options[param_key]
                        final_args.append(f"{param['arg']}={default_value}")
            
            # 显示当前配置
            print("\n当前配置:")
            for arg in final_args:
                print(f"  {arg}")
            
            # 询问是否需要修改参数
            while True:
                print("\n可选操作:")
                print("1. 修改参数")
                print("2. 添加参数")
                print("3. 开始执行")
                print("4. 重新选择模式")
                print("0. 退出程序")
                
                op_choice = input("\n请选择操作(0-4): ").strip()
                
                if op_choice == "0":
                    return []
                elif op_choice == "1":
                    # 显示当前所有参数
                    print("\n当前参数:")
                    for i, arg in enumerate(final_args, 1):
                        print(f"{i}. {arg}")
                    param_idx = input("请选择要修改的参数序号: ").strip()
                    try:
                        idx = int(param_idx) - 1
                        if 0 <= idx < len(final_args):
                            new_value = input(f"请输入新的值: ").strip()
                            if '=' in final_args[idx]:
                                arg_name = final_args[idx].split('=')[0]
                                final_args[idx] = f"{arg_name}={new_value}"
                            else:
                                final_args[idx] = new_value
                    except ValueError:
                        print("❌ 无效的输入")
                elif op_choice == "2":
                    # 显示可添加的参数
                    print("\n可添加的参数:")
                    for key, param in param_options.items():
                        if param.get("is_flag"):
                            print(f"  {key}. {param['name']} (开关参数)")
                        elif "choices" in param:
                            print(f"  {key}. {param['name']} (可选值: {'/'.join(param['choices'])})")
                        else:
                            print(f"  {key}. {param['name']}")
                    
                    param_key = input("请输入要添加的参数代号: ").strip()
                    if param_key in param_options:
                        param = param_options[param_key]
                        if param.get("is_flag"):
                            final_args.append(param["arg"])
                        else:
                            value = input(f"请输入{param['name']}的值: ").strip()
                            if "choices" in param and value not in param["choices"]:
                                print(f"❌ 无效的值，可选值: {'/'.join(param['choices'])}")
                                continue
                            if "type" in param:
                                try:
                                    value = param["type"](value)
                                except ValueError:
                                    print("❌ 无效的数值")
                                    continue
                            final_args.append(f"{param['arg']}={value}")
                elif op_choice == "3":
                    print("\n最终参数:", " ".join(final_args))
                    # 保存当前配置
                    DebuggerHandler.save_last_config(mode_choice, final_args)
                    return final_args
                elif op_choice == "4":
                    break
                else:
                    print("❌ 无效的选择")
            
        return []
    

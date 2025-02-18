from textual.app import App
from config import create_config_app, CheckboxOption, InputOption

# 修改后的正确预设配置
PRESET_CONFIGS = {
    "快速模式": {
        "description": "默认优化配置",
        "checkbox_options": ["hash_md5", "dedup"],
        "input_values": {
            "threads": "8",  # 改为输入框ID
            "loglevel": "WARNING"  # 改为输入框ID
        }
    },
    "安全模式": {
        "description": "完整校验配置",
        "checkbox_options": ["hash_md5", "hash_sha1", "dedup"],
        "input_values": {
            "threads": "2",  # 改为输入框ID
            "loglevel": "DEBUG"  # 改为输入框ID
        }
    }
}

def custom_runner(params: dict):
    """自定义执行函数"""
    # 在打印前添加换行确保输出可见
    print("\n" + "="*40)
    print("[回调函数被触发]")
    print("✅ 选项参数:")
    for arg, enabled in params['options'].items():
        print(f"  {arg}: {'启用' if enabled else '禁用'}")
    
    print("\n✅ 输入参数:")
    for arg, value in params['inputs'].items():
        print(f"  {arg}: {value or '未设置'}")
    
    print(f"\n🔖 使用预设: {params['preset'] or '无'}")
    # 这里可以添加实际业务逻辑
    print("="*40 + "\n")

# 配置选项
checkbox_options = [
    ("MD5校验", "hash_md5", "--md5", True),
    ("SHA1校验", "hash_sha1", "--sha1"),
    ("去重处理", "dedup", "--dedup", True),
]

input_options = [
    ("工作线程数", "threads", "--threads", "4", "1-8"),
    ("输出目录", "output", "--output", "", "输入路径"),
    ("日志级别", "loglevel", "--loglevel", "INFO", "DEBUG/INFO/WARNING"),
]

# 创建应用实例
app = create_config_app(
    program="demo.py",
    checkbox_options=checkbox_options,
    input_options=input_options,
    title="去重复工具配置",
    preset_configs=PRESET_CONFIGS,  # 新增预设配置
    on_run=custom_runner  # 传入回调函数
)

if __name__ == "__main__":
    print("启动配置界面...")
    print("👉 在界面完成配置后点击'运行'按钮")
    
    import sys
    # 强制刷新输出缓冲区
    sys.stdout.flush()
    
    try:
        app.run()
    finally:
        # 确保最后执行保持窗口的代码
        input("\n按回车键退出...")
        sys.stdout.flush()
from pathlib import Path
import os
import sys
from dotenv import load_dotenv

def setup_project_path():
    """设置项目路径并初始化环境"""
    # 获取当前脚本的绝对路径
    current_file = Path(__file__).resolve()
    
    # 查找项目根目录 (包含 .env 或 .git 的目录)
    project_root = current_file.parent
    while project_root != project_root.parent:
        if (project_root / '.env').exists() or (project_root / '.git').exists():
            break
        project_root = project_root.parent
    
    # 如果没找到.env或.git，使用默认的src的父目录作为项目根目录
    if project_root == project_root.parent:
        project_root = current_file.parent.parent.parent
    
    # 添加项目根目录到Python路径
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # 加载环境变量
    env_file = project_root / '.env'
    if env_file.exists():
        load_dotenv(env_file)
    
    # 设置项目相关路径
    paths = {
        'PROJECT_ROOT': project_root,
        'LOG_DIR': project_root / 'logs',
        'SRC_DIR': project_root / 'src',
    }
    
    # 确保必要的目录存在
    paths['LOG_DIR'].mkdir(parents=True, exist_ok=True)
    
    return paths

def get_project_paths():
    """获取项目路径配置"""
    global PROJECT_PATHS
    if 'PROJECT_PATHS' not in globals():
        PROJECT_PATHS = setup_project_path()
    return PROJECT_PATHS

# 加载项目根目录的.env
root_dir = Path(__file__).parent.parent.parent
load_dotenv(root_dir / '.env') 
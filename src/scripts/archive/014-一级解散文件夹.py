import os
import shutil
import pyperclip
import argparse
import yaml
import json
import time
from pathlib import Path
from datetime import datetime

OPERATIONS_FILE = "folder_operations.yaml"

class FileOperation:
    def __init__(self, source, target, operation_type):
        self.source = str(source)
        self.target = str(target)
        self.operation_type = operation_type  # 'move' or 'delete'
        self.timestamp = datetime.now().isoformat()
        
    def to_dict(self):
        return {
            'source': self.source,
            'target': self.target,
            'operation_type': self.operation_type,
            'timestamp': self.timestamp
        }
        
    @classmethod
    def from_dict(cls, data):
        op = cls(data['source'], data['target'], data['operation_type'])
        op.timestamp = data['timestamp']
        return op

def get_paths_from_clipboard():
    """从剪贴板读取多行路径"""
    try:
        clipboard_content = pyperclip.paste()
        if not clipboard_content:
            return []
        
        paths = []
        for line in clipboard_content.splitlines():
            if line := line.strip().strip('"').strip("'"):
                path = Path(line)
                if path.exists():
                    paths.append(path)
                else:
                    print(f"⚠️ 警告：路径不存在 - {line}")
        
        print(f"📋 从剪贴板读取到 {len(paths)} 个有效路径")
        return paths
        
    except Exception as e:
        print(f"❌ 读取剪贴板失败: {e}")
        return []

def backup_folder(path):
    """创建文件夹的备份"""
    path = Path(path)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = path.parent / f"{path.name}_backup_{timestamp}"
    shutil.copytree(path, backup_path)
    print(f"📦 已创建备份: {backup_path}")
    return backup_path

def load_operations_history():
    """加载操作历史"""
    if os.path.exists(OPERATIONS_FILE):
        try:
            with open(OPERATIONS_FILE, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"❌ 读取操作历史失败: {e}")
            return {}
    return {}

def save_operations_history(history):
    """保存操作历史"""
    try:
        with open(OPERATIONS_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(history, f, allow_unicode=True, sort_keys=False)
    except Exception as e:
        print(f"❌ 保存操作历史失败: {e}")

def save_operations(operations, path):
    """保存操作记录到YAML文件"""
    if not operations:
        return None
        
    # 生成操作ID
    operation_id = f"{path.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # 加载现有历史记录
    history = load_operations_history()
    
    # 添加新的操作记录
    history[operation_id] = {
        'path': str(path),
        'timestamp': datetime.now().isoformat(),
        'operations': [op.to_dict() for op in operations]
    }
    
    # 保存更新后的历史记录
    save_operations_history(history)
    print(f"📝 操作记录已保存，操作ID: {operation_id}")
    return operation_id

def list_operations():
    """列出所有操作记录"""
    history = load_operations_history()
    if not history:
        print("📭 没有找到任何操作记录")
        return
        
    print("\n📋 操作历史记录:")
    for op_id, data in history.items():
        timestamp = datetime.fromisoformat(data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n🔖 操作ID: {op_id}")
        print(f"📂 处理路径: {data['path']}")
        print(f"🕒 操作时间: {timestamp}")
        print(f"📝 操作详情:")
        for op in data['operations']:
            if op['operation_type'] == 'move':
                print(f"  ↗️ 移动: {os.path.basename(op['source'])} -> {os.path.basename(op['target'])}")
            else:
                print(f"  🗑️ 删除: {os.path.basename(op['source'])}")

def undo_operations(operation_id):
    """撤销指定ID的操作"""
    history = load_operations_history()
    if operation_id not in history:
        print(f"❌ 未找到操作记录: {operation_id}")
        return False
        
    data = history[operation_id]
    operations = [FileOperation.from_dict(op) for op in data['operations']]
    
    print(f"\n↩️ 开始撤销操作: {operation_id}")
    print(f"📂 原始路径: {data['path']}")
    
    # 反向执行操作
    success = True
    for op in reversed(operations):
        try:
            if op.operation_type == 'move':
                if Path(op.target).exists():
                    shutil.move(op.target, op.source)
                    print(f"✅ 已撤销移动: {os.path.basename(op.target)} -> {os.path.basename(op.source)}")
                else:
                    print(f"⚠️ 文件不存在，无法撤销: {op.target}")
                    success = False
            elif op.operation_type == 'delete':
                if not Path(op.source).exists() and Path(op.target).exists():
                    os.makedirs(op.source)
                    print(f"✅ 已恢复文件夹: {op.source}")
                else:
                    print(f"⚠️ 无法恢复文件夹: {op.source}")
                    success = False
        except Exception as e:
            print(f"❌ 撤销操作失败: {e}")
            success = False
    
    if success:
        # 从历史记录中删除已撤销的操作
        del history[operation_id]
        save_operations_history(history)
        print(f"✅ 操作已成功撤销并从历史记录中删除")
    else:
        print(f"⚠️ 部分操作撤销失败，历史记录已保留")
    
    return success

def preview_dissolve(path):
    """预览将要执行的操作"""
    path = Path(path).resolve()
    if not path.exists() or not path.is_dir():
        print(f"❌ 错误：{path} 不是一个有效的文件夹")
        return
        
    print(f"\n🔍 预览解散文件夹: {path}")
    items = list(path.iterdir())
    
    # 检查冲突
    has_conflict = False
    for item in items:
        target_path = path.parent / item.name
        if target_path.exists():
            if target_path.is_dir():
                print(f"⚠️ 将保留原文件夹（发现冲突）: {item.name}")
                has_conflict = True
                break
            else:
                print(f"⚠️ 将跳过已存在的文件: {item.name}")
        else:
            print(f"📦 将移动: {item.name} -> {target_path}")
    
    if has_conflict:
        print(f"🔒 由于存在冲突的文件夹，将保留原文件夹: {path}")
    else:
        print(f"🗑️ 将删除空文件夹: {path}")

def dissolve_folder_one_level(path, dry_run=False, create_backup=True):
    """
    将指定文件夹中的内容移动到其父文件夹中
    如果目标位置已存在同名文件夹，则保留原文件夹不解散
    
    参数:
    path (Path/str): 要解散的文件夹路径
    dry_run (bool): 是否仅预览不执行
    create_backup (bool): 是否创建备份
    """
    try:
        path = Path(path).resolve()
        if not path.exists() or not path.is_dir():
            print(f"❌ 错误：{path} 不是一个有效的文件夹")
            return

        if dry_run:
            preview_dissolve(path)
            return
            
        parent_dir = path.parent
        print(f"\n🔍 开始解散文件夹: {path}")
        
        # 创建备份
        backup_path = None
        if create_backup:
            backup_path = backup_folder(path)
        
        # 记录操作
        operations = []
        
        # 获取所有项目
        items = list(path.iterdir())
        
        # 检查是否有冲突的文件夹
        has_conflict = False
        for item in items:
            target_path = parent_dir / item.name
            if target_path.exists() and target_path.is_dir():
                print(f"⚠️ 发现冲突的文件夹: {item.name}")
                has_conflict = True
                break
        
        if has_conflict:
            print(f"🔒 由于存在冲突的文件夹，保留原文件夹: {path}")
            if backup_path and backup_path.exists():
                shutil.rmtree(backup_path)
                print(f"🗑️ 已删除不需要的备份: {backup_path}")
            return
        
        # 如果没有冲突，开始移动文件
        for item in items:
            target_path = parent_dir / item.name
            try:
                if target_path.exists():
                    if target_path.is_file():
                        print(f"⏩ 跳过已存在的文件: {item.name}")
                        continue
                print(f"📦 移动: {item.name} -> {target_path}")
                shutil.move(str(item.absolute()), str(target_path.absolute()))
                operations.append(FileOperation(item, target_path, 'move'))
            except Exception as e:
                print(f"❌ 移动 {item.name} 失败: {e}")
                continue
        
        try:
            # 检查文件夹是否为空
            remaining_items = list(path.iterdir())
            if remaining_items:
                print(f"⚠️ 警告：文件夹 {path} 仍包含以下项目，无法删除:")
                for item in remaining_items:
                    print(f"  📄 {item.name}")
            else:
                # 记录删除操作
                operations.append(FileOperation(path, path.parent, 'delete'))
                path.rmdir()
                print(f"✅ 已成功解散并删除文件夹: {path}")
                
                # 保存操作记录
                if operations:
                    log_path = save_operations(operations, path)
                    print(f"💡 提示：如需撤销操作，请使用 --undo {log_path}")
        except Exception as e:
            print(f"❌ 删除文件夹失败: {e}")
            
    except Exception as e:
        print(f"❌ 解散文件夹时出错: {e}")

def main():
    parser = argparse.ArgumentParser(description='一级解散文件夹工具')
    parser.add_argument('paths', nargs='*', help='要处理的路径列表')
    parser.add_argument('--clipboard', '-c', action='store_true', help='从剪贴板读取路径')
    parser.add_argument('--dry-run', '-d', action='store_true', help='预览模式，不实际执行')
    parser.add_argument('--no-backup', '-n', action='store_true', help='不创建备份')
    parser.add_argument('--undo', type=str, help='撤销操作（需要提供操作ID）')
    parser.add_argument('--list', '-l', action='store_true', help='列出所有操作记录')
    args = parser.parse_args()
    
    if args.list:
        list_operations()
        return
    
    if args.undo:
        undo_operations(args.undo)
        return
    
    # 获取要处理的路径
    paths = []
    if args.clipboard:
        paths = get_paths_from_clipboard()
    elif args.paths:  # 处理直接传入的路径
        for path_str in args.paths:
            path = Path(path_str.strip('"').strip("'"))
            if path.exists():
                paths.append(path)
            else:
                print(f"⚠️ 警告：路径不存在 - {path_str}")
    
    if not paths:
        print("📝 请输入要处理的文件夹路径，每行一个，输入空行结束:")
        while True:
            if line := input().strip():
                path = Path(line.strip('"').strip("'"))
                if path.exists():
                    paths.append(path)
                else:
                    print(f"⚠️ 警告：路径不存在 - {line}")
            else:
                break
    
    if not paths:
        print("❌ 未提供任何有效的路径")
        return

    # 处理每个路径
    for path in paths:
        if args.dry_run:
            print("\n🔍 预览模式...")
        dissolve_folder_one_level(path, dry_run=args.dry_run, create_backup=not args.no_backup)

if __name__ == "__main__":
    main() 
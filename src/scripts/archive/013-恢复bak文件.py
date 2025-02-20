import os
import shutil
import logging
import argparse
from pathlib import Path
from tqdm import tqdm
from send2trash import send2trash

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('restore_bak.log', encoding='utf-8')
    ]
)

def find_bak_files(directory):
    """查找目录下的所有.bak文件"""
    bak_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.zip.bak'):  # 修改为查找.zip.bak文件
                bak_path = os.path.join(root, file)
                original_path = bak_path[:-4]  # 只移除.bak后缀
                if os.path.exists(original_path):
                    bak_size = os.path.getsize(bak_path)
                    original_size = os.path.getsize(original_path)
                    if bak_size > original_size:
                        bak_files.append((bak_path, original_path, bak_size, original_size))
    return bak_files

def handle_bak_file(bak_path, action):
    """根据指定的动作处理bak文件"""
    try:
        if action == 'delete':
            os.remove(bak_path)
            logging.info(f'已删除bak文件: {bak_path}')
        elif action == 'recycle':
            send2trash(bak_path)
            logging.info(f'已将bak文件移至回收站: {bak_path}')
        elif action == 'keep':
            logging.info(f'保留bak文件: {bak_path}')
    except Exception as e:
        logging.error(f'处理bak文件失败 {bak_path}: {e}')

def restore_bak_file(bak_path, original_path, bak_action):
    """恢复单个bak文件"""
    try:
        # 如果原始文件存在，先将其备份为.old
        if os.path.exists(original_path):
            old_path = original_path + '.old'
            shutil.move(original_path, old_path)
            logging.info(f'原文件已备份为: {old_path}')
        
        # 恢复bak文件
        shutil.copy2(bak_path, original_path)
        logging.info(f'已恢复: {bak_path} -> {original_path}')
        
        # 处理bak文件
        handle_bak_file(bak_path, bak_action)
        
        return True
    except Exception as e:
        logging.error(f'恢复文件失败 {bak_path}: {e}')
        return False

def process_files(bak_files, bak_action, auto_confirm=False):
    """处理找到的bak文件"""
    for bak_path, original_path, bak_size, original_size in tqdm(bak_files, desc='恢复文件'):
        logging.info(f'\n处理文件: {bak_path}')
        logging.info(f'BAK文件大小: {bak_size/1024/1024:.2f}MB')
        logging.info(f'原文件大小: {original_size/1024/1024:.2f}MB')
        
        if not auto_confirm:
            while True:
                choice = input(f'是否恢复此文件? (y/n/all/quit): ').lower()
                if choice in ['y', 'n', 'all', 'quit']:
                    break
                print('无效的输入，请重试')
            
            if choice == 'quit':
                logging.info('用户取消操作')
                break
            elif choice == 'all':
                auto_confirm = True
            elif choice == 'n':
                logging.info('跳过此文件')
                continue
        
        restore_bak_file(bak_path, original_path, bak_action)

def get_user_input():
    """获取用户输入"""
    print("\n请输入要处理的目录路径：")
    while True:
        directory = input().strip()
        if os.path.exists(directory):
            break
        print("目录不存在，请重新输入：")
    
    print("\n请选择处理bak文件的方式：")
    print("1. 移至回收站 (默认)")
    print("2. 直接删除")
    print("3. 保留")
    while True:
        choice = input("请输入选项编号 [1-3]: ").strip()
        if choice in ['1', '2', '3', '']:
            break
        print("无效的选择，请重新输入")
    
    action_map = {
        '1': 'recycle',
        '2': 'delete',
        '3': 'keep',
        '': 'recycle'
    }
    action = action_map[choice]
    
    print("\n是否自动确认所有操作？(y/n)")
    while True:
        auto_confirm = input().lower().strip()
        if auto_confirm in ['y', 'n', '']:
            break
        print("无效的输入，请重新输入")
    
    return directory, action, auto_confirm in ['y', '']

def main():
    directory, action, auto_confirm = get_user_input()
    
    logging.info(f'开始扫描目录: {directory}')
    bak_files = find_bak_files(directory)
    
    if not bak_files:
        logging.info('没有找到需要恢复的bak文件')
        return
    
    logging.info(f'找到 {len(bak_files)} 个需要恢复的bak文件')
    process_files(bak_files, action, auto_confirm)

if __name__ == '__main__':
    main() 
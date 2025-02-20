import os
import orjson
from tqdm import tqdm
from datetime import datetime

class TimestampManager:
    def __init__(self, backup_dir='1ehv/timestamp_backups'):
        self.backup_dir = backup_dir
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

    def save_timestamps(self, directory, version_name=None):
        if version_name is None:
            version_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        backup_file = os.path.join(self.backup_dir, f"timestamps_{version_name}.json")
        timestamps = {}
        total_items = 0
        for root, dirs, files in os.walk(directory):
            total_items += len(dirs) + len(files)
        
        with tqdm(total=total_items, desc="保存时间戳") as pbar:
            for root, dirs, files in os.walk(directory):
                for dir in dirs:
                    dir_path = os.path.join(root, dir)
                    stats = os.stat(dir_path)
                    timestamps[dir_path] = {'access_time': stats.st_atime, 'mod_time': stats.st_mtime}
                    pbar.update(1)
                
                for file in files:
                    file_path = os.path.join(root, file)
                    stats = os.stat(file_path)
                    timestamps[file_path] = {'access_time': stats.st_atime, 'mod_time': stats.st_mtime}
                    pbar.update(1)
        
        with open(backup_file, 'wb') as f:
            f.write(orjson.dumps(timestamps))
        print(f"时间戳已保存到 {backup_file}")

    def list_backups(self):
        backups = []
        for file in os.listdir(self.backup_dir):
            if file.startswith("timestamps_") and file.endswith(".json"):
                version = file[11:-5]
                backups.append(version)
        return backups

    def restore_timestamps(self, version_name=None):
        if version_name is None:
            backups = self.list_backups()
            if not backups:
                print("没有找到任何备份")
                return
            print("\n可用的备份版本：")
            for i, backup in enumerate(backups, 1):
                print(f"{i}. {backup}")
            try:
                choice = int(input("\n请选择要恢复的版本编号: "))
                if 1 <= choice <= len(backups):
                    version_name = backups[choice-1]
                else:
                    print("无效的选择")
                    return
            except ValueError:
                print("无效的输入")
                return

        backup_file = os.path.join(self.backup_dir, f"timestamps_{version_name}.json")
        if not os.path.exists(backup_file):
            print(f"备份文件 {backup_file} 不存在")
            return

        with open(backup_file, 'rb') as f:
            timestamps = orjson.loads(f.read())
        
        with tqdm(total=len(timestamps), desc="恢复时间戳") as pbar:
            for path, times in timestamps.items():
                if os.path.exists(path):
                    os.utime(path, (times['access_time'], times['mod_time']))
                pbar.update(1)
        print("时间戳已恢复")

def main():
    manager = TimestampManager()
    while True:
        print("\n1. 保存时间戳")
        print("2. 恢复时间戳")
        print("3. 查看所有备份")
        print("4. 退出")
        
        choice = input("请选择操作: ")
        
        if choice == "1":
            directory = input("请输入要保存时间戳的目录路径: ")
            if not os.path.exists(directory):
                print("目录不存在")
                continue
            version_name = input("请输入版本名称（直接回车使用时间戳作为版本名）: ").strip()
            version_name = version_name if version_name else None
            manager.save_timestamps(directory, version_name)
        elif choice == "2":
            manager.restore_timestamps()
        elif choice == "3":
            backups = manager.list_backups()
            if not backups:
                print("没有找到任何备份")
            else:
                print("\n可用的备份版本：")
                for i, backup in enumerate(backups, 1):
                    print(f"{i}. {backup}")
        elif choice == "4":
            break
        else:
            print("无效的选择")

if __name__ == "__main__":
    main()
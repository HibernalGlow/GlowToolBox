# ... existing imports ...
import sqlite3
import csv
import json
from random import choices
from string import hexdigits
import time
from pathlib import Path
import yaml  # 添加yaml支持
import psutil  # 添加psutil模块

# 新增测试格式配置
TEST_FORMATS = {
    'yaml': {'ext': 'yaml', 'module': 'yaml'},
    'json': {'ext': 'json', 'module': 'json'},
    'txt': {'ext': 'txt', 'module': None},
    'csv': {'ext': 'csv', 'module': 'csv'},
    'sqlite': {'ext': 'db', 'module': 'sqlite3'}
}

# 在类定义上方添加哈希参数配置
HASH_PARAMS = {
    'hash_size': 16,    # 哈希值长度
    'hash_version': '1.0',
    'sample_size': 100000  # 测试数据量
}

class FormatPerformanceTest:
    @classmethod
    def generate_test_data(cls):
        """生成性能测试数据"""
        test_data = {"hashes": {}}
        for i in range(HASH_PARAMS['sample_size']):
            uri = f"file:///dataset/images/image_{i:08d}.jpg"
            # 生成随机哈希值（16进制字符串）
            hash_val = ''.join(choices(hexdigits, k=HASH_PARAMS['hash_size']))
            test_data["hashes"][uri] = hash_val
        return test_data

    @staticmethod
    def save_sqlite(data, filename):
        """SQLite保存方法（优化版）"""
        conn = sqlite3.connect(filename)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS hashes
                     (uri TEXT PRIMARY KEY, hash TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS meta
                     (key TEXT PRIMARY KEY, value TEXT)''')
        
        # 优化：使用事务批量插入
        conn.execute('BEGIN TRANSACTION')
        c.executemany('INSERT OR REPLACE INTO hashes VALUES (?, ?)', 
                     data["hashes"].items())
        # 保存元数据
        c.executemany('INSERT INTO meta VALUES (?, ?)', [
            ('hash_size', HASH_PARAMS['hash_size']),
            ('hash_version', HASH_PARAMS['hash_version'])
        ])
        conn.commit()
        conn.close()

    @staticmethod
    def load_sqlite(filename):
        """SQLite加载方法"""
        conn = sqlite3.connect(filename)
        c = conn.cursor()
        c.execute('SELECT uri, hash FROM hashes')
        hashes = dict(c.fetchall())
        conn.close()
        return {"hashes": hashes}

    @staticmethod
    def save_txt(data, filename):
        """纯文本保存方法"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# hash_size={HASH_PARAMS['hash_size']}\n")
            f.write(f"# hash_version={HASH_PARAMS['hash_version']}\n")
            for uri, hash_val in data["hashes"].items():
                f.write(f"{uri}|{hash_val}\n")

    @staticmethod
    def load_txt(filename):
        """纯文本加载方法"""
        hashes = {}
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    uri, hash_val = line.split('|', 1)
                    hashes[uri] = hash_val
        return {"hashes": hashes}

    @staticmethod
    def save_csv(data, filename):
        """CSV保存方法"""
        with open(filename, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['URI', 'Hash'])
            writer.writerows(data["hashes"].items())

    @staticmethod
    def load_csv(filename):
        """CSV加载方法"""
        hashes = {}
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # 跳过标题
            for row in reader:
                hashes[row[0]] = row[1]
        return {"hashes": hashes}

    @staticmethod
    def save_json(data, filename):
        """JSON保存方法"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f)

    @staticmethod
    def load_json(filename):
        """JSON加载方法"""
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)

    @classmethod
    def run_test(cls):
        """运行完整测试"""
        # 生成测试数据
        test_data = cls.generate_test_data()
        results = []

        for fmt, config in TEST_FORMATS.items():
            filename = f"test_hashes.{config['ext']}"
            print(f"\n=== {fmt.upper()} 格式测试 ===")

            # 保存测试
            save_func = getattr(cls, f'save_{fmt}', None)
            start = time.time()
            if save_func:
                save_func(test_data, filename)
            else:
                with open(filename, 'w') as f:
                    yaml.dump(test_data, f) if fmt == 'yaml' else None
            save_time = time.time() - start

            # 加载测试
            load_func = getattr(cls, f'load_{fmt}', None)
            start = time.time()
            if load_func:
                loaded_data = load_func(filename)
            else:
                with open(filename, 'r') as f:
                    loaded_data = yaml.safe_load(f) if fmt == 'yaml' else None
            load_time = time.time() - start

            # 验证数据
            is_consistent = test_data["hashes"] == loaded_data.get("hashes", {})
            file_size = Path(filename).stat().st_size/1024/1024

            # 获取内存使用情况
            process = psutil.Process()
            mem_usage = process.memory_info().rss // 1024 // 1024  # MB

            results.append({
                'format': fmt,
                'save_time': save_time,
                'load_time': load_time,
                'file_size': file_size,
                'mem_usage': mem_usage,
                'consistent': is_consistent
            })

            # 清理测试文件
            Path(filename).unlink()

        # 打印结果对比
        print("\n=== 性能对比 ===")
        print(f"{'格式':<8} | {'保存(s)':<7} | {'加载(s)':<7} | {'大小(MB)':<9} | {'内存(MB)':<9} | 一致")
        print("-"*65)
        for res in results:
            print(f"{res['format']:<8} | {res['save_time']:<7.2f} | {res['load_time']:<7.2f} | "
                  f"{res['file_size']:<9.2f} | {res['mem_usage']:<9.2f} | {'✅' if res['consistent'] else '❌'}")

if __name__ == "__main__":
    FormatPerformanceTest.run_test()


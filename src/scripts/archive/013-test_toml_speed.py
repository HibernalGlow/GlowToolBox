import time
import yaml
import toml
import msgpack
import sqlite3
import json

# 测试数据
data = {
    "uuid": "abc123",
    "timestamp": "2023-10-01T12:00:00Z",
    "artist_name": "Artist Name",
    "archive_name": "archive.zip",
    "relative_path": "relative/path"
}

# 测试 YAML
start = time.time()
for _ in range(1000):
    yaml.dump(data, open("test.yaml", "w"))
    yaml.safe_load(open("test.yaml", "r"))
print(f"YAML: {time.time() - start:.2f} 秒")

# 测试 TOML
start = time.time()
for _ in range(1000):
    toml.dump(data, open("test.toml", "w"))
    toml.load(open("test.toml", "r"))
print(f"TOML: {time.time() - start:.2f} 秒")

# 测试 json
start = time.time()
for _ in range(1000):
    json.dump(data, open("test.json", "w"))
    json.load(open("test.json", "r"))
print(f"JSON: {time.time() - start:.2f} 秒")

# 测试 MessagePack
start = time.time()
for _ in range(1000):
    with open("test.msgpack", "wb") as f:
        msgpack.pack(data, f)
    with open("test.msgpack", "rb") as f:
        msgpack.unpack(f)
print(f"MessagePack: {time.time() - start:.2f} 秒")
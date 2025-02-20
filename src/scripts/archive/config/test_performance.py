import pytest
from performance_config import get_thread_count, get_batch_size, save_config
import os
import json
import threading
import importlib

def test_default_values():
    """测试默认值是否为1"""
    # 重置线程本地存储
    import performance_config
    performance_config._local = threading.local()
    
    # 删除配置文件
    if os.path.exists("performance_instances.json"):
        os.remove("performance_instances.json")
    
    # 重新导入配置模块
    importlib.reload(performance_config)
    from performance_config import get_thread_count, get_batch_size
    
    assert get_thread_count() == 1
    assert get_batch_size() == 1
    print("✅ 默认值测试通过")

def test_multi_instance(tmp_path):
    """测试多实例隔离"""
    # 模拟第一个实例
    os.environ["TEST_INSTANCE_ID"] = "test_id_1"
    save_config({"thread_count": 3, "batch_size": 5})
    
    # 模拟第二个实例
    os.environ["TEST_INSTANCE_ID"] = "test_id_2"
    assert get_thread_count() == 1, "新实例应使用默认值"
    assert get_batch_size() == 1, "新实例应使用默认值"
    print("✅ 多实例隔离测试通过")

def test_config_persistence():
    """测试配置持久化"""
    test_id = "persistence_test"
    os.environ["TEST_INSTANCE_ID"] = test_id
    
    # 修改配置
    save_config({"thread_count": 4, "batch_size": 8})
    
    # 重新读取
    with open("performance_instances.json", 'r') as f:
        configs = json.load(f)
        assert configs[test_id]["thread_count"] == 4
        assert configs[test_id]["batch_size"] == 8
    print("✅ 持久化测试通过")

if __name__ == "__main__":
    test_default_values()
    test_multi_instance()
    test_config_persistence()
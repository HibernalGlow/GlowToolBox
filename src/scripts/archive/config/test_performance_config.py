from performance_config import get_thread_count, get_batch_size, save_config
import os

def test_default_values():
    """测试默认值是否为1"""
    assert get_thread_count() == 1, f"默认线程数错误，当前值: {get_thread_count()}"
    assert get_batch_size() == 1, f"默认批处理大小错误，当前值: {get_batch_size()}"
    print("✅ 默认值测试通过")

def test_config_update():
    """测试配置更新功能"""
    save_config({"thread_count": 8, "batch_size": 16})
    assert get_thread_count() == 8, f"线程数更新失败，当前值: {get_thread_count()}"
    assert get_batch_size() == 16, f"批处理更新失败，当前值: {get_batch_size()}"
    print("✅ 配置更新测试通过")

def test_multi_process():
    """测试多进程隔离"""
    # 保存当前配置
    current_id = os.getpid()
    save_config({"thread_count": 4, "batch_size": 4})
    
    # 启动新进程
    new_pid = os.fork()
    if new_pid == 0:
        # 子进程应使用默认值
        assert get_thread_count() == 1, f"子进程隔离失败: {get_thread_count()}"
        print("✅ 多进程隔离测试通过")
        os._exit(0)
    else:
        os.wait()
    
    # 父进程配置应保持不变
    assert get_thread_count() == 4, f"父进程配置污染: {get_thread_count()}"
    assert os.getpid() == current_id

if __name__ == "__main__":
    test_default_values()
    test_config_update()
    test_multi_process()
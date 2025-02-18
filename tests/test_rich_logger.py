
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.rich_logger import (
    update_panel,
    add_log,
    add_success_log, 
    add_error_log,
    add_warning_log,
    add_status_log,
    create_progress_task,
    close_demo_handler
)
import time

def test_rich_logger():
    """测试rich_logger的新接口"""
    try:
        # 1. 创建进度任务
        total = 5
        task_id = create_progress_task(total, "测试进度条...")
        
        # 2. 测试各种日志类型
        add_log("开始测试日志系统")
        time.sleep(1)
        
        for i in range(total):
            # 更新进度面板
            update_panel("stats", f"正在处理第 {i+1}/{total} 个任务")
            
            # 更新当前任务面板
            update_panel("process", f"当前任务: Task-{i+1}")
            
            # 测试不同类型的日志
            if i == 0:
                add_success_log(f"成功完成任务 {i+1}")
            elif i == 1:
                add_error_log(f"任务 {i+1} 执行失败")
            elif i == 2:
                add_warning_log(f"任务 {i+1} 需要注意")
            elif i == 3:
                add_status_log(f"正在处理任务 {i+1}")
            else:
                add_log(f"普通日志: 任务 {i+1}")
                
            # 模拟任务处理时间
            time.sleep(1)
            
        # 3. 测试面板更新
        update_panel("update_log", "✨ 测试完成!")
        time.sleep(1)
        
    finally:
        # 4. 确保关闭处理器
        close_demo_handler()

if __name__ == "__main__":
    print("开始测试rich_logger新接口...")
    test_rich_logger() 
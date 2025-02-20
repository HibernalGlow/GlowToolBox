import sys
import time

def main():
    print("\n" + "="*50)
    print("这是一个测试脚本")
    print("运行参数:", sys.argv[1:])
    print("PowerShell中运行成功!")
    print("="*50 + "\n")
    
    # 等待一会儿以便查看输出
    time.sleep(1)
    
    # 测试参数处理
    if "--test1" in sys.argv:
        print("测试选项1已启用")
    if "--test2" in sys.argv:
        print("测试选项2已启用")
    
    input_value = None
    try:
        input_idx = sys.argv.index("--input")
        if input_idx + 1 < len(sys.argv):
            input_value = sys.argv[input_idx + 1]
    except ValueError:
        pass
    
    if input_value:
        print(f"输入参数值: {input_value}")
    
    print("\n执行完成!")
    time.sleep(1)

if __name__ == "__main__":
    main()
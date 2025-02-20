# 测试代码框架
import timeit
import json  # 标准库
import ujson
import orjson


test_data = {"hashes": {f"uri_{i}": "a1b2c3d4e5f6" for i in range(100000)}}

def benchmark(lib_name):
    # 序列化
    dump_time = timeit.timeit(
        lambda: globals()[lib_name].dumps(test_data),
        number=100
    )
    
    # 反序列化
    json_str = globals()[lib_name].dumps(test_data)
    load_time = timeit.timeit(
        lambda: globals()[lib_name].loads(json_str),
        number=100
    )
    
    return dump_time/100, load_time/100

# 执行测试
libs = ['json', 'ujson', 'orjson']
results = {lib: benchmark(lib) for lib in libs}
print(results)
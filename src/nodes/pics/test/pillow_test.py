import time
from PIL import Image
from io import BytesIO
import os
import pillow_avif  # 需要安装
import pillow_jxl   # 需要安装
import pyvips
import subprocess
import tempfile
import time
import sys
import os
from pathlib import Path
vipshome = Path('D:\\1VSCODE\\1ehv\\other\\vips\\bin')
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(str(vipshome))
def test_format_performance(image_path, save_format, iterations=5):
    """测试指定格式的编解码性能"""
    results = {
        'decode_times': [],
        'encode_times': [],
        'file_size': os.path.getsize(image_path)
    }
    
    # 原始格式检测
    orig_format = os.path.splitext(image_path)[1][1:].upper()
    
    try:
        for _ in range(iterations):
            # 解码测试
            start = time.perf_counter()
            with Image.open(image_path) as img:
                img.load()  # 确保完整加载
            results['decode_times'].append(time.perf_counter() - start)
            
            # 编码测试
            buffer = BytesIO()
            start = time.perf_counter()
            # 添加JXL特殊参数处理
            if save_format.lower() == 'jxl':
                img.save(buffer, 
                        format=save_format, 
                        quality=85,
                        lossless_jpeg=True)  # 启用JPEG元数据复用
            else:
                img.save(buffer, 
                        format=save_format, 
                        quality=85)  # 其他格式保持原参数
            results['encode_times'].append(time.perf_counter() - start)
            
        # 计算平均时间
        avg_decode = sum(results['decode_times']) / iterations
        avg_encode = sum(results['encode_times']) / iterations
        encoded_size = buffer.tell()
        
        print(f"{orig_format} -> {save_format.upper():5} | "
              f"解码: {avg_decode:.3f}s | "
              f"编码: {avg_encode:.3f}s | "
              f"原大小: {results['file_size']/1024:.1f}KB | "
              f"新大小: {encoded_size/1024:.1f}KB")
        
    except Exception as e:
        print(f"Error processing {image_path} to {save_format}: {str(e)}")
    return results
# ... existing code ...
def decode_with_engine(image_data, engine='pillow'):
    """使用指定引擎进行解码"""
    try:
        start = time.perf_counter()
        if engine == 'pillow':
            with Image.open(BytesIO(image_data)) as img:
                img.load()
        elif engine == 'pyvips':
            pyvips.Image.new_from_buffer(image_data, '')
        elif engine == 'imagemagick':
            with tempfile.NamedTemporaryFile() as tmp:
                tmp.write(image_data)
                tmp.flush()
                subprocess.run(['magick', tmp.name, 'info:'], check=True, capture_output=True)
        return time.perf_counter() - start
    except Exception as e:
        print(f"{engine} 解码失败: {str(e)}")
        return float('inf')  # 返回极大值表示失败

def standardized_conversion_test(original_path, intermediate_format='PNG', target_formats=['AVIF', 'JXL']):
    """标准化转换测试流程"""
    results = {}
    
    try:
        # 统一压缩参数
        COMMON_PARAMS = {
            'quality': 85,
            'lossless': False,
            'strip_metadata': True
        }
        
        # 第一阶段：原始格式 -> PNG
        with Image.open(original_path) as img:
            png_buffer = BytesIO()
            img.save(png_buffer, format=intermediate_format, **COMMON_PARAMS)
            png_data = png_buffer.getvalue()
            results['to_png'] = len(png_data)/1024
            
        # 第二阶段：PNG -> 目标格式（多引擎测试）
        for fmt in target_formats:
            fmt = fmt.upper()
            results[fmt] = {}
            
            # 测试不同引擎
            for engine in ['pillow', 'pyvips', 'imagemagick']:
                engine_key = f"{fmt}_{engine}"
                results[fmt][engine_key] = {}
                
                try:
                    # 编码测试
                    encode_time, target_data = convert_with_engine(
                        png_data, fmt, 
                        engine=engine,
                        **COMMON_PARAMS
                    )
                    
                    # 解码测试
                    decode_time = decode_with_engine(
                        target_data,
                        engine=engine
                    )
                    
                    # 记录结果
                    results[fmt][engine_key] = {
                        'encode_time': encode_time,
                        'decode_time': decode_time,
                        'target_size': len(target_data)/1024,
                        'roundtrip_size': len(png_data)/1024
                    }
                    
                except Exception as e:
                    print(f"{engine} 引擎处理 {fmt} 失败: {str(e)}")
                    continue
                    
        # 打印结果
        orig_size = os.path.getsize(original_path)/1024
        print(f"\n测试文件: {os.path.basename(original_path)}")
        print(f"原始大小: {orig_size:.1f}KB → PNG中间大小: {results['to_png']:.1f}KB")
        
        for fmt in target_formats:
            fmt = fmt.upper()
            for engine in ['pillow', 'pyvips', 'imagemagick']:
                engine_key = f"{fmt}_{engine}"
                data = results[fmt].get(engine_key, {})
                if data:
                    print(f"引擎: {engine:8} | PNG → {fmt:4} | "
                          f"编码: {data.get('encode_time', 0):.3f}s | "
                          f"解码: {data.get('decode_time', 0):.3f}s | "
                          f"目标大小: {data.get('target_size', 0):.1f}KB")
            
    except Exception as e:
        print(f"转换流程出错: {str(e)}")
    return results

def convert_with_engine(image_data, target_format, engine='pillow', **params):
    """使用指定引擎进行格式转换"""
    if engine == 'pillow':
        return pillow_convert(image_data, target_format, **params)
    elif engine == 'pyvips':
        return pyvips_convert(image_data, target_format, **params)
    elif engine == 'imagemagick':
        return imagemagick_convert(image_data, target_format, **params)
    else:
        raise ValueError(f"不支持的引擎: {engine}")

def pillow_convert(image_data, target_format, **params):
    """使用Pillow转换"""
    start = time.perf_counter()
    with Image.open(BytesIO(image_data)) as img:
        buffer = BytesIO()
        img.save(buffer, format=target_format, **params)
    return time.perf_counter() - start, buffer.getvalue()

def pyvips_convert(image_data, target_format, **params):
    """使用pyvips转换"""
    start = time.perf_counter()
    image = pyvips.Image.new_from_buffer(image_data, '')
    buffer = image.write_to_buffer(f'.{target_format.lower()}', **params)
    return time.perf_counter() - start, buffer

def imagemagick_convert(image_data, target_format, **params):
    """使用ImageMagick转换（需要安装）"""
    start = time.perf_counter()
    tmp_in = None
    tmp_out = None
    
    try:
        # 使用临时文件并显式关闭句柄
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_in:
            tmp_in.write(image_data)
            tmp_in_name = tmp_in.name
        tmp_out = f"{os.path.splitext(tmp_in_name)[0]}.{target_format.lower()}"

        # 构建命令
        cmd = [
            'magick',
            tmp_in_name,
            '-quality', str(params.get('quality', 85)),
            '-strip',
            tmp_out
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        with open(tmp_out, 'rb') as f:
            output_data = f.read()
        
        return time.perf_counter() - start, output_data
        
    finally:
        # 确保清理临时文件
        if tmp_in and os.path.exists(tmp_in_name):
            os.unlink(tmp_in_name)
        if tmp_out and os.path.exists(tmp_out):
            os.unlink(tmp_out)

# ... existing code ...
if __name__ == "__main__":
    # 配置测试目录
    test_dir = r'D:\1VSCODE\1ehv\pics\test'
    target_formats = ['JPEG', 'PNG', 'WEBP', 'AVIF', 'JXL']  # 要测试的目标格式
    
    # 获取目录下所有图片文件
    image_files = []
    supported_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.avif', '.jxl']  # 支持的源格式
    for entry in os.scandir(test_dir):
        if entry.is_file() and os.path.splitext(entry.name)[1].lower() in supported_extensions:
            image_files.append(entry.path)
    
    if not image_files:
        print(f"目录 {test_dir} 中没有找到支持的图片文件（支持格式：{', '.join(supported_extensions)}）")
        exit()
    
    # 执行测试
    for img_path in image_files:
        standardized_conversion_test(img_path)
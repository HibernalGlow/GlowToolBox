import subprocess
import os
from pathlib import Path
from PIL import Image
import pillow_jxl
def jxl_to_gif(input_path, output_path, djxl_path="djxl.exe"):
    """
    将JXL图片转换为GIF格式
    
    参数:
    input_path: JXL文件路径
    output_path: 输出GIF文件路径
    djxl_path: djxl.exe的路径
    """
    try:
        # 创建临时PNG文件路径
        temp_png = str(Path(output_path).with_suffix('.png'))
        
        # 先转换为PNG
        cmd = [djxl_path, input_path, temp_png]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"JXL转PNG失败: {result.stderr}")
        
        # 再将PNG转换为GIF
        try:
            with Image.open(temp_png) as img:
                img.save(output_path, 'GIF')
            print(f"转换成功: {output_path}")
        finally:
            # 删除临时PNG文件
            if os.path.exists(temp_png):
                os.remove(temp_png)
                
    except Exception as e:
        print(f"转换过程中出错: {str(e)}")

# 使用示例
if __name__ == "__main__":
    # 设置输入输出路径
    input_jxl = r"E:\999EHV\[えびふりゃ]\2. 画集\[02动图]\2. 画集\FANTIA 作品集 (ex-hentai 1118P 截止2024.09.16)\0620_0568_min2.jxl"
    output_gif = "output.gif"
    
    # 执行转换
    jxl_to_gif(input_jxl, output_gif)
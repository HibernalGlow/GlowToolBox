from PIL import Image, ImageGrab
import io
import pyperclip
from PIL.PngImagePlugin import PngImageFile
import pillow_avif
from io import BytesIO

try:
    import win32clipboard
except ImportError:
    print("请先安装 pywin32：pip install pywin32")
    exit(1)

def set_clipboard_data(data):
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    finally:
        win32clipboard.CloseClipboard()

def convert_clipboard_image_to_avif():
    try:
        # 从剪贴板获取图片
        clipboard_content = ImageGrab.grabclipboard()
        
        if clipboard_content is None:
            print("剪贴板中没有图片")
            return
            
        # 检查并打印图片格式
        print(f"剪贴板图片格式: {clipboard_content.format if hasattr(clipboard_content, 'format') else '未知'}")
            
        # 处理不同的剪贴板内容类型
        if isinstance(clipboard_content, list):
            if not clipboard_content:
                print("剪贴板中的图片路径列表为空")
                return
            clipboard_image = Image.open(clipboard_content[0])
        else:
            clipboard_image = clipboard_content
        
        # 创建一个字节流对象来存储AVIF图片
        avif_buffer = io.BytesIO()
        
        # 使用与原脚本相同的AVIF配置
        avif_config = {
            'quality': 90,
            'speed': 6,
            'chroma_quality': 100,
            'lossless': False
        }
        
        # 转换为AVIF格式并保存到字节流
        clipboard_image.save(avif_buffer, format="AVIF", **avif_config)
        
        # 将AVIF图片写回剪贴板
        avif_image = Image.open(BytesIO(avif_buffer.getvalue()))
        
        # 将图片转换为BMP格式以便写入剪贴板
        output = BytesIO()
        avif_image.convert('RGB').save(output, 'BMP')
        data = output.getvalue()[14:]  # 去除BMP文件头
        
        # 写入剪贴板
        set_clipboard_data(data)
        
        print("图片已转换为AVIF格式并写回剪贴板")
        
    except Exception as e:
        print(f"转换过程中出错: {str(e)}")

if __name__ == "__main__":
    convert_clipboard_image_to_avif()
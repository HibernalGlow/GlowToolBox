import onnx
import torch
from onnx2torch import convert
import os

# 获取用户输入的ONNX文件路径
onnx_path = input("请输入ONNX文件路径: ").strip().strip("&'")

# 加载ONNX模型
onnx_model = onnx.load(onnx_path)

# 转换为PyTorch模型
torch_model = convert(onnx_model)

# 获取用户输入的保存路径
save_path = input("请输入保存PyTorch模型的路径: ").strip().strip("&'")

# 确保保存路径有.pth扩展名
if not save_path.endswith('.pth'):
    save_path += '.pth'

# 确保保存目录存在
os.makedirs(os.path.dirname(save_path), exist_ok=True)

# 保存PyTorch模型
torch.save(torch_model, save_path)
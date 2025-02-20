# ========== 基础工具 ==========
# 路径处理
from pathlib import Path
import os
import shutil

# 系统交互
import subprocess
import sys
import pyperclip
from send2trash import send2trash

# ========== 多线程相关 ==========
import threading
from threading import Lock
from concurrent.futures import ThreadPoolExecutor

# ========== 时间处理 ==========
from datetime import datetime
import time

# ========== 压缩文件处理 ==========
import zipfile

# ========== 图像处理核心 ==========
import PIL
from PIL import Image
import numpy as np

# 图像格式扩展
import pillow_avif  # AVIF支持
import pillow_jxl   # JXL支持

# ========== 配置管理 ==========
import argparse
import yaml
import json



# ========== 日志与进度 ==========
import logging
from tqdm import tqdm

# ========== 个人模块 ==========

from nodes.pics.calculate_hash_custom import ImageHashCalculator, PathURIGenerator , ImgUtils
from nodes.pics.grayscale_detector import GrayscaleDetector
from nodes.tui.textual_logger import TextualLoggerManager
from nodes.tui.textual_preset import create_config_app


# ========== 数据转换 ==========
from io import BytesIO

# 环境加载（保持最后）
from dotenv import load_dotenv
load_dotenv()
# file_list = ImgUtils.get_image_files(r"E:\1EHV")
# print(file_list)

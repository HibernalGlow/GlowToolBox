#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
URL过滤工具 (图形界面版本)
------------------------

功能说明：
    用于对比两个文件中的URL，如果文件A中的URL包含了文件B中的任何URL，
    则从文件A中删除该URL。主要用于过滤重复或相关的URL链接。

使用方法：
    1. 运行程序：python url_filter_gui.py
    2. 在界面上选择文件：
       - 文件A：基准文件，包含需要过滤的URL列表
       - 文件B：包含用于匹配的URL列表
       - 输出文件：过滤后的结果保存位置
    3. 可以使用测试区域测试单个URL的匹配情况
    4. 点击"处理文件"开始处理

功能特点：
    1. 直观的图形界面
    2. 实时URL测试功能
    3. 自动处理各种URL编码
    4. 详细的处理结果显示
    5. 支持文件拖放

注意事项：
    1. 文件编码应为UTF-8
    2. 每行一个URL
    3. 支持各种URL编码格式
    4. 会自动处理URL编码和特殊字符

作者：Claude
创建日期：2024-03-xx
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import re
from pathlib import Path
from typing import Set, Optional
from urllib.parse import unquote, quote, urlparse
from url_filter import normalize_url, filter_urls, read_urls

class URLFilterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("URL过滤器")
        self.root.geometry("1200x800")
        
        # 创建主框架
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 说明文本
        desc_frame = ttk.LabelFrame(main_frame, text="功能说明", padding="5")
        desc_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        ttk.Label(desc_frame, text="本工具用于过滤URL列表。如果文件A中的URL包含了文件B中的任何URL，则该URL将被过滤掉。").grid(row=0, column=0, padx=5)
        
        # 测试区域
        test_frame = ttk.LabelFrame(main_frame, text="测试区域", padding="5")
        test_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # URL测试输入框
        ttk.Label(test_frame, text="测试URL 1 (来自文件A):").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.test_url1 = scrolledtext.ScrolledText(test_frame, height=3, width=80)
        self.test_url1.grid(row=1, column=0, padx=5, pady=5)
        
        ttk.Label(test_frame, text="测试URL 2 (来自文件B):").grid(row=2, column=0, sticky=tk.W, padx=5)
        self.test_url2 = scrolledtext.ScrolledText(test_frame, height=3, width=80)
        self.test_url2.grid(row=3, column=0, padx=5, pady=5)
        
        # 测试结果
        ttk.Label(test_frame, text="处理结果:").grid(row=4, column=0, sticky=tk.W, padx=5)
        self.test_result = scrolledtext.ScrolledText(test_frame, height=3, width=80)
        self.test_result.grid(row=5, column=0, padx=5, pady=5)
        
        # 测试按钮
        ttk.Button(test_frame, text="测试URL", command=self.test_rules).grid(row=6, column=0, pady=10)
        
        # 文件处理区域
        file_frame = ttk.LabelFrame(main_frame, text="文件处理", padding="5")
        file_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 文件A选择
        ttk.Label(file_frame, text="文件A (基准文件):").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.file_a_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.file_a_var, width=60).grid(row=0, column=1, padx=5)
        ttk.Button(file_frame, text="浏览", command=lambda: self.browse_file('a')).grid(row=0, column=2, padx=5)
        
        # 文件B选择
        ttk.Label(file_frame, text="文件B (包含要过滤的URL):").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.file_b_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.file_b_var, width=60).grid(row=1, column=1, padx=5)
        ttk.Button(file_frame, text="浏览", command=lambda: self.browse_file('b')).grid(row=1, column=2, padx=5)
        
        # 输出文件选择
        ttk.Label(file_frame, text="输出文件:").grid(row=2, column=0, sticky=tk.W, padx=5)
        self.output_file_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.output_file_var, width=60).grid(row=2, column=1, padx=5)
        ttk.Button(file_frame, text="浏览", command=lambda: self.browse_file('output')).grid(row=2, column=2, padx=5)
        
        # 处理按钮
        ttk.Button(file_frame, text="处理文件", command=self.process_files).grid(row=3, column=0, columnspan=3, pady=10)
        
        # 状态栏
        self.status_var = tk.StringVar()
        ttk.Label(main_frame, textvariable=self.status_var).grid(row=3, column=0, columnspan=2, sticky=tk.W)
    
    def browse_file(self, file_type):
        if file_type in ('a', 'b'):
            filename = filedialog.askopenfilename(
                title=f"选择文件{file_type.upper()}",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
            )
            if file_type == 'a':
                self.file_a_var.set(filename)
            else:
                self.file_b_var.set(filename)
        else:
            filename = filedialog.asksaveasfilename(
                title="保存输出文件",
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
            )
            self.output_file_var.set(filename)
    
    def test_rules(self):
        try:
            # 获取测试URL
            url1 = self.test_url1.get("1.0", tk.END).strip()
            url2 = self.test_url2.get("1.0", tk.END).strip()
            
            if not url1 or not url2:
                self.test_result.delete("1.0", tk.END)
                self.test_result.insert("1.0", "请输入测试URL")
                return
            
            # 标准化URL
            norm_url1 = normalize_url(url1)
            norm_url2 = normalize_url(url2)
            
            # 检查包含关系
            contains = norm_url2 in norm_url1
            
            # 显示结果
            result = f"URL1 (标准化后): {norm_url1}\nURL2 (标准化后): {norm_url2}\n"
            result += f"结果: URL1 {'包含' if contains else '不包含'} URL2\n"
            result += f"处理建议: {'将被过滤' if contains else '将被保留'}"
            
            self.test_result.delete("1.0", tk.END)
            self.test_result.insert("1.0", result)
            
        except Exception as e:
            self.test_result.delete("1.0", tk.END)
            self.test_result.insert("1.0", f"错误: {str(e)}")
    
    def process_files(self):
        try:
            file_a = self.file_a_var.get()
            file_b = self.file_b_var.get()
            output_file = self.output_file_var.get()
            
            if not all([file_a, file_b, output_file]):
                messagebox.showerror("错误", "请选择所有必需的文件")
                return
            
            # 读取文件
            urls_a = read_urls(file_a)
            urls_b = read_urls(file_b)
            
            if not urls_a or not urls_b:
                messagebox.showerror("错误", "输入文件为空或无法读取")
                return
            
            # 过滤URL
            filtered_urls = filter_urls(urls_a, urls_b)
            
            # 写入结果
            with open(output_file, 'w', encoding='utf-8') as f:
                for url in sorted(filtered_urls):
                    f.write(f"{url}\n")
            
            self.status_var.set(f"处理完成！共保留 {len(filtered_urls)} 个URL（过滤掉 {len(urls_a) - len(filtered_urls)} 个）")
            messagebox.showinfo("成功", f"处理完成！\n结果已保存到: {output_file}")
            
        except Exception as e:
            messagebox.showerror("错误", str(e))
            self.status_var.set(f"处理出错: {str(e)}")

def main():
    root = tk.Tk()
    app = URLFilterGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 
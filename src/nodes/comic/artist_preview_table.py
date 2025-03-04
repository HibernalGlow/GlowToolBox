import yaml
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple
import logging
import asyncio
import aiohttp
from dataclasses import dataclass
from datetime import datetime
import os
import sys

logger = logging.getLogger(__name__)

@dataclass
class ArtistPreview:
    name: str
    folder: str
    preview_url: str
    files: List[str]
    is_existing: bool

class ArtistPreviewGenerator:
    def __init__(self, base_url: str = "https://www.wn01.uk"):
        self.base_url = base_url
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def _get_preview_url(self, artist_name: str) -> Optional[str]:
        """获取画师作品的预览图URL"""
        try:
            # 移除方括号获取纯画师名
            clean_name = artist_name.strip('[]')
            search_url = f"{self.base_url}/search/?q={clean_name}"
            
            async with self.session.get(search_url) as response:
                if response.status != 200:
                    logger.warning(f"搜索画师 {clean_name} 失败: {response.status}")
                    return None
                    
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # 查找所有预览图
                gallery_items = soup.select('.gallary_item')
                for item in gallery_items:
                    img = item.select_one('img')
                    if img and img.get('src'):
                        img_url = f"https:{img['src']}"
                        # 验证图片是否可访问
                        try:
                            async with self.session.head(img_url) as img_response:
                                if img_response.status == 200:
                                    return img_url
                        except Exception:
                            continue
            
            return None
        except Exception as e:
            logger.error(f"获取画师 {clean_name} 预览图失败: {e}")
            return None

    async def process_artist(self, folder_name: str, files: List[str], is_existing: bool) -> ArtistPreview:
        """处理单个画师信息"""
        # 已存在画师不获取预览图
        preview_url = "" if is_existing else await self._get_preview_url(folder_name)
        return ArtistPreview(
            name=folder_name.strip('[]'),
            folder=folder_name,
            preview_url=preview_url,
            files=files,
            is_existing=is_existing
        )

    async def process_yaml(self, yaml_path: str) -> Tuple[List[ArtistPreview], List[ArtistPreview]]:
        """处理yaml文件，返回新旧画师预览信息"""
        # 读取yaml文件
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # 获取画师信息
        existing_artists = data['artists']['existing_artists']
        new_artists = data['artists']['new_artists']
        
        # 异步处理所有画师
        existing_tasks = [
            self.process_artist(folder, files, True)
            for folder, files in existing_artists.items()
        ]
        
        new_tasks = [
            self.process_artist(folder, files, False)
            for folder, files in new_artists.items()
        ]
        
        # 等待所有任务完成
        existing_previews = await asyncio.gather(*existing_tasks)
        new_previews = await asyncio.gather(*new_tasks)
        
        return existing_previews, new_previews

    def generate_html(self, existing_previews: List[ArtistPreview], 
                     new_previews: List[ArtistPreview], 
                     output_path: str):
        """生成HTML预览页面"""
        html_template = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>画师预览表格</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .table-container {{ margin-bottom: 20px; }}
        .preview-table {{ border-collapse: collapse; width: 100%; }}
        .preview-table th, .preview-table td {{ 
            border: 1px solid #ddd; 
            padding: 8px; 
            text-align: left; 
        }}
        .preview-table th {{ background-color: #f4f4f4; }}
        .preview-img {{ max-width: 100px; max-height: 150px; }}
        .files-list {{ max-height: 150px; overflow-y: auto; margin: 0; }}
        .collapsible {{ 
            background-color: #f4f4f4;
            cursor: pointer;
            padding: 18px;
            width: 100%;
            border: none;
            text-align: left;
            outline: none;
            font-size: 15px;
            margin-bottom: 10px;
        }}
        .active, .collapsible:hover {{ background-color: #ddd; }}
        .content {{ 
            display: none;
            overflow: hidden;
            background-color: #f9f9f9;
            padding: 0 18px;
        }}
        .checkbox-container {{ margin-bottom: 10px; }}
        .preview-cell {{ width: 100px; }}
        .name-cell {{ width: 200px; }}
    </style>
</head>
<body>
    <h2>已存在画师</h2>
    <div class="table-container">
        <button type="button" class="collapsible">显示/隐藏已存在画师 (已全选)</button>
        <div class="content">
            <div class="checkbox-container">
                <input type="checkbox" id="existing-select-all" checked>
                <label for="existing-select-all">全选/取消全选</label>
            </div>
            <table class="preview-table">
                <tr>
                    <th>选择</th>
                    <th>画师名</th>
                    <th>文件列表</th>
                </tr>
                {existing_rows}
            </table>
        </div>
    </div>

    <h2>新画师</h2>
    <div class="table-container">
        <div class="checkbox-container">
            <input type="checkbox" id="new-select-all">
            <label for="new-select-all">全选/取消全选</label>
        </div>
        <table class="preview-table">
            <tr>
                <th>选择</th>
                <th>预览图</th>
                <th>画师名</th>
                <th>文件列表</th>
            </tr>
            {new_rows}
        </table>
    </div>

    <script>
        // 折叠面板功能
        var coll = document.getElementsByClassName("collapsible");
        for (var i = 0; i < coll.length; i++) {{
            coll[i].addEventListener("click", function() {{
                this.classList.toggle("active");
                var content = this.nextElementSibling;
                if (content.style.display === "block") {{
                    content.style.display = "none";
                }} else {{
                    content.style.display = "block";
                }}
            }});
        }}

        // 全选功能
        function setupSelectAll(tableId, selectAllId) {{
            const selectAll = document.getElementById(selectAllId);
            const table = document.querySelector(tableId);
            if (!selectAll || !table) return;

            selectAll.addEventListener('change', function() {{
                const checkboxes = table.querySelectorAll('input[type="checkbox"]');
                checkboxes.forEach(checkbox => checkbox.checked = this.checked);
            }});

            table.addEventListener('change', function(e) {{
                if (e.target.type === 'checkbox' && e.target !== selectAll) {{
                    const checkboxes = table.querySelectorAll('input[type="checkbox"]:not(#' + selectAllId + ')');
                    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                    selectAll.checked = allChecked;
                }}
            }});
        }}

        setupSelectAll('.content table', 'existing-select-all');
        setupSelectAll('.table-container:nth-of-type(2) table', 'new-select-all');
    </script>
</body>
</html>
'''
        
        def generate_table_row(preview: ArtistPreview) -> str:
            files_list = '<br>'.join(preview.files)
            if preview.is_existing:
                # 已存在画师不显示预览图
                return f"""
                    <tr>
                        <td><input type="checkbox" checked></td>
                        <td class="name-cell">{preview.name}</td>
                        <td><div class="files-list">{files_list}</div></td>
                    </tr>
                """
            else:
                # 新画师显示预览图
                preview_img = f'<img src="{preview.preview_url}" class="preview-img">' if preview.preview_url else '无预览图'
                return f"""
                    <tr>
                        <td><input type="checkbox"></td>
                        <td class="preview-cell">{preview_img}</td>
                        <td class="name-cell">{preview.name}</td>
                        <td><div class="files-list">{files_list}</div></td>
                    </tr>
                """
        
        # 生成表格行
        existing_rows = '\n'.join(generate_table_row(p) for p in existing_previews)
        new_rows = '\n'.join(generate_table_row(p) for p in new_previews)
        
        # 生成完整HTML
        html_content = html_template.format(
            existing_rows=existing_rows,
            new_rows=new_rows
        )
        
        # 保存HTML文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"预览页面已生成: {output_path}")

async def generate_preview_tables(yaml_path: str, output_path: str = None):
    """生成画师预览表格的主函数"""
    if output_path is None:
        output_path = Path(yaml_path).parent / 'artist_preview.html'
    
    async with ArtistPreviewGenerator() as generator:
        # 处理yaml文件
        existing_previews, new_previews = await generator.process_yaml(yaml_path)
        
        # 生成HTML页面
        generator.generate_html(existing_previews, new_previews, output_path)

if __name__ == "__main__":
    import argparse
    
    # 设置日志
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 默认yaml路径
    default_yaml = r"d:\1VSCODE\GlowToolBox\src\scripts\comic\classify\classified_result.yaml"
    
    # 如果默认文件不存在，提示输入
    if not os.path.exists(default_yaml):
        print(f"默认文件不存在: {default_yaml}")
        yaml_path = input("请输入yaml文件路径（直接回车使用默认路径）: ").strip()
        if not yaml_path:
            yaml_path = default_yaml
    else:
        yaml_path = default_yaml
    
    # 检查文件是否存在
    if not os.path.exists(yaml_path):
        print(f"文件不存在: {yaml_path}")
        sys.exit(1)
    
    # 设置输出路径
    output_path = Path(yaml_path).parent / 'artist_preview.html'
    
    print(f"处理文件: {yaml_path}")
    print(f"输出文件: {output_path}")
    
    try:
        # 安装依赖
        try:
            import aiohttp
        except ImportError:
            print("正在安装必要的依赖...")
            os.system("pip install aiohttp beautifulsoup4")
            import aiohttp
        
        # 运行生成器
        asyncio.run(generate_preview_tables(yaml_path, str(output_path)))
        print(f"预览页面已生成: {output_path}")
    except Exception as e:
        print(f"生成预览页面时出错: {e}")
        if input("是否显示详细错误信息？(y/n): ").lower() == 'y':
            import traceback
            traceback.print_exc() 
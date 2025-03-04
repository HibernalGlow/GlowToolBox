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
        body { font-family: Arial, sans-serif; margin: 20px; }
        .table-container { margin-bottom: 20px; }
        .preview-table { border-collapse: collapse; width: 100%; }
        .preview-table th, .preview-table td { 
            border: 1px solid #ddd; 
            padding: 8px; 
            text-align: left; 
        }
        .preview-table th { background-color: #f4f4f4; }
        .preview-img { max-width: 100px; max-height: 150px; }
        .files-list { max-height: 150px; overflow-y: auto; margin: 0; }
        .collapsible { 
            background-color: #f4f4f4;
            cursor: pointer;
            padding: 18px;
            width: 100%;
            border: none;
            text-align: left;
            outline: none;
            font-size: 15px;
            margin-bottom: 10px;
        }
        .active, .collapsible:hover { background-color: #ddd; }
        .content { 
            display: none;
            overflow: hidden;
            background-color: #f9f9f9;
            padding: 0 18px;
        }
        .checkbox-container { margin-bottom: 10px; }
        .preview-cell { width: 100px; }
        .name-cell { width: 200px; }
        .export-container {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: #f4f4f4;
            padding: 10px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            z-index: 1000;
        }
        .control-btn {
            background-color: #4CAF50;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin: 0 10px;
        }
        .control-btn:hover {
            background-color: #45a049;
        }
        .main-content {
            margin-top: 60px;
        }
        .preview-link {
            color: #0066cc;
            text-decoration: none;
            margin-left: 10px;
        }
        .preview-link:hover {
            text-decoration: underline;
        }
        .import-area {
            width: 100%;
            height: 100px;
            margin: 10px 0;
            display: none;
        }
    </style>
</head>
<body>
    <div class="export-container">
        <button class="control-btn" onclick="exportSelected('artists')">导出选中画师</button>
        <button class="control-btn" onclick="exportSelected('files')">导出选中压缩包</button>
        <button class="control-btn" onclick="toggleImportArea()">导入画师列表</button>
        <button class="control-btn" onclick="invertSelection()">反选</button>
    </div>
    
    <div class="main-content">
        <textarea id="importArea" class="import-area" placeholder="请输入画师列表，每行一个画师名"></textarea>
        <button id="importButton" class="control-btn" style="display: none;" onclick="importArtists()">确认导入</button>

        <h2>已存在画师</h2>
        <div class="table-container">
            <div class="checkbox-container">
                <input type="checkbox" id="existing-select-all" checked>
                <label for="existing-select-all">全选/取消全选</label>
            </div>
            <button type="button" class="collapsible">显示/隐藏已存在画师</button>
            <div class="content">
                <table class="preview-table" id="existing-table">
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
            <table class="preview-table" id="new-table">
                <tr>
                    <th>选择</th>
                    <th>预览图</th>
                    <th>画师名</th>
                    <th>文件列表</th>
                </tr>
                {new_rows}
            </table>
        </div>
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
                const checkboxes = table.querySelectorAll('input[type="checkbox"]:not(#' + selectAllId + ')');
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

        setupSelectAll('#existing-table', 'existing-select-all');
        setupSelectAll('#new-table', 'new-select-all');

        // 反选功能
        function invertSelection() {{
            const tables = ['existing-table', 'new-table'];
            tables.forEach(tableId => {{
                const table = document.getElementById(tableId);
                if (table) {{
                    const checkboxes = table.querySelectorAll('input[type="checkbox"]:not([id$="-select-all"])');
                    checkboxes.forEach(checkbox => {{
                        checkbox.checked = !checkbox.checked;
                    }});
                    // 更新全选框状态
                    const selectAll = document.getElementById(tableId.split('-')[0] + '-select-all');
                    if (selectAll) {{
                        const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                        selectAll.checked = allChecked;
                    }}
                }}
            }});
        }}

        // 导入/导出功能
        function toggleImportArea() {{
            const importArea = document.getElementById('importArea');
            const importButton = document.getElementById('importButton');
            importArea.style.display = importArea.style.display === 'none' ? 'block' : 'none';
            importButton.style.display = importArea.style.display;
        }}

        function importArtists() {{
            const importArea = document.getElementById('importArea');
            const artistsList = importArea.value.split('\\n').filter(name => name.trim());
            
            const tables = ['existing-table', 'new-table'];
            tables.forEach(tableId => {{
                const table = document.getElementById(tableId);
                if (table) {{
                    const rows = table.querySelectorAll('tr');
                    rows.forEach(row => {{
                        const nameCell = row.querySelector('.name-cell');
                        if (nameCell) {{
                            const artistName = nameCell.textContent.trim();
                            const checkbox = row.querySelector('input[type="checkbox"]');
                            if (checkbox) {{
                                checkbox.checked = artistsList.includes(artistName);
                            }}
                        }}
                    }});
                }}
            }});

            // 清空并隐藏导入区域
            importArea.value = '';
            toggleImportArea();
        }}

        function exportSelected(type) {{
            let content = [];
            let exportData = {{'artists': [], 'files': [], 'links': []}};
            
            function processTable(tableId) {{
                const table = document.getElementById(tableId);
                if (table) {{
                    const rows = table.querySelectorAll('tr');
                    rows.forEach(row => {{
                        const checkbox = row.querySelector('input[type="checkbox"]');
                        if (checkbox && checkbox.checked) {{
                            const nameCell = row.querySelector('.name-cell');
                            if (nameCell) {{
                                const artistName = nameCell.textContent.trim();
                                exportData.artists.push(artistName);
                                exportData.links.push(`https://www.wn01.uk/search/?q=${encodeURIComponent(artistName)}`);
                                
                                const filesList = row.querySelector('.files-list');
                                if (filesList) {{
                                    exportData.files.push(...filesList.innerHTML.split('<br>'));
                                }}
                            }}
                        }}
                    }});
                }}
            }}

            processTable('existing-table');
            processTable('new-table');

            // 根据类型导出不同内容
            if (type === 'artists') {{
                content = exportData.artists.map((artist, i) => `${artist}\\t${exportData.links[i]}`);
            }} else if (type === 'files') {{
                content = exportData.files;
            }}

            if (content.length > 0) {{
                const blob = new Blob([content.join('\\n')], {{ type: 'text/plain' }});
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = type === 'artists' ? 'selected_artists.txt' : 'selected_files.txt';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);

                // 保存选中状态到localStorage
                localStorage.setItem('selectedArtists', JSON.stringify(exportData.artists));
            }} else {{
                alert('请先选择要导出的内容！');
            }}
        }}

        // 页面加载时恢复选中状态
        window.addEventListener('load', function() {{
            const savedArtists = JSON.parse(localStorage.getItem('selectedArtists') || '[]');
            if (savedArtists.length > 0) {{
                const tables = ['existing-table', 'new-table'];
                tables.forEach(tableId => {{
                    const table = document.getElementById(tableId);
                    if (table) {{
                        const rows = table.querySelectorAll('tr');
                        rows.forEach(row => {{
                            const nameCell = row.querySelector('.name-cell');
                            if (nameCell) {{
                                const artistName = nameCell.textContent.trim();
                                const checkbox = row.querySelector('input[type="checkbox"]');
                                if (checkbox) {{
                                    checkbox.checked = savedArtists.includes(artistName);
                                }}
                            }}
                        }});
                    }}
                }});
            }}
        }});
    </script>
</body>
</html>
'''
        
        def generate_table_row(preview: ArtistPreview) -> str:
            files_list = '<br>'.join(preview.files)
            preview_link = f'<a href="https://www.wn01.uk/search/?q={preview.name}" class="preview-link" target="_blank">预览</a>'
            
            if preview.is_existing:
                return f"""
                    <tr>
                        <td><input type="checkbox" checked></td>
                        <td class="name-cell">{preview.name}{preview_link}</td>
                        <td><div class="files-list">{files_list}</div></td>
                    </tr>
                """
            else:
                preview_img = f'<img src="{preview.preview_url}" class="preview-img">' if preview.preview_url else '无预览图'
                return f"""
                    <tr>
                        <td><input type="checkbox"></td>
                        <td class="preview-cell">{preview_img}</td>
                        <td class="name-cell">{preview.name}{preview_link}</td>
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
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
    <link rel="stylesheet" href="https://cdn.datatables.net/1.11.5/css/jquery.dataTables.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/select/1.3.4/css/select.dataTables.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/buttons/2.2.2/css/buttons.dataTables.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/viewerjs/1.10.2/viewer.min.css">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .table-container {{ margin: 20px 0; }}
        .preview-table {{ width: 100%; }}
        .preview-img {{ max-width: 100px; max-height: 150px; cursor: pointer; }}
        .files-list {{ max-height: 150px; overflow-y: auto; margin: 0; }}
        .control-panel {{ 
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: #f4f4f4;
            padding: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            z-index: 1000;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .main-content {{ margin-top: 60px; }}
        .btn {{
            background-color: #4CAF50;
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin: 0 5px;
        }}
        .btn:hover {{ background-color: #45a049; }}
        .btn-group {{ display: flex; gap: 5px; }}
        .mode-switch {{
            padding: 5px 10px;
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 4px;
            cursor: pointer;
        }}
        .mode-switch.active {{ background: #4CAF50; color: white; }}
        .grid-view {{ 
            display: none;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 20px;
            padding: 20px;
        }}
        .grid-item {{
            border: 1px solid #ddd;
            padding: 10px;
            text-align: center;
        }}
        .grid-item img {{ max-width: 100%; height: auto; }}
        .custom-select-all {{
            margin: 10px 0;
            font-weight: bold;
        }}
        .dt-buttons {{ margin-bottom: 10px; }}
    </style>
</head>
<body>
    <div class="control-panel">
        <div class="btn-group">
            <button class="btn" onclick="exportSelected('artists')">导出选中画师</button>
            <button class="btn" onclick="exportSelected('files')">导出选中压缩包</button>
            <button class="btn" onclick="exportSelectionState()">导出选中状态</button>
            <input type="file" id="importState" style="display: none" onchange="importSelectionState(event)">
            <button class="btn" onclick="document.getElementById('importState').click()">导入选中状态</button>
        </div>
        <div class="view-controls">
            <button class="mode-switch active" data-mode="table">表格模式</button>
            <button class="mode-switch" data-mode="grid">图墙模式</button>
        </div>
    </div>
    
    <div class="main-content">
        <h2>已存在画师</h2>
        <div class="table-container">
            <div class="custom-select-all">
                <input type="checkbox" id="existing-select-all" checked>
                <label for="existing-select-all">全选/取消全选已存在画师</label>
                <button class="btn" onclick="invertSelection('existing-table')">反选</button>
            </div>
            <table class="preview-table" id="existing-table">
                <thead>
                    <tr>
                        <th>选择</th>
                        <th>画师名</th>
                        <th>文件列表</th>
                    </tr>
                </thead>
                <tbody>
                    {existing_rows}
                </tbody>
            </table>
        </div>

        <h2>新画师</h2>
        <div class="table-container">
            <div class="custom-select-all">
                <input type="checkbox" id="new-select-all">
                <label for="new-select-all">全选/取消全选新画师</label>
                <button class="btn" onclick="invertSelection('new-table')">反选</button>
            </div>
            <table class="preview-table" id="new-table">
                <thead>
                    <tr>
                        <th>选择</th>
                        <th>预览图</th>
                        <th>画师名</th>
                        <th>文件列表</th>
                    </tr>
                </thead>
                <tbody>
                    {new_rows}
                </tbody>
            </table>
        </div>
    </div>

    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.11.5/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/select/1.3.4/js/dataTables.select.min.js"></script>
    <script src="https://cdn.datatables.net/buttons/2.2.2/js/dataTables.buttons.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/viewerjs/1.10.2/viewer.min.js"></script>
    <script>
        // 初始化 DataTables
        $(document).ready(function() {{
            const commonConfig = {{
                pageLength: 25,
                dom: 'Bfrtip',
                select: {{
                    style: 'multi',
                    selector: 'td:first-child input[type="checkbox"]'
                }},
                buttons: [
                    'selectAll',
                    'selectNone'
                ]
            }};

            $('#existing-table').DataTable(commonConfig);
            $('#new-table').DataTable(commonConfig);

            // 初始化图片查看器
            new Viewer(document.getElementById('new-table'), {{
                inline: false,
                viewed() {{
                    viewer.zoomTo(1);
                }}
            }});
        }});

        // 视图切换
        document.querySelectorAll('.mode-switch').forEach(btn => {{
            btn.addEventListener('click', function() {{
                const mode = this.dataset.mode;
                document.querySelectorAll('.mode-switch').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                
                const tables = document.querySelectorAll('.table-container');
                const gridView = document.querySelector('.grid-view');
                
                if (mode === 'grid') {{
                    tables.forEach(t => t.style.display = 'none');
                    gridView.style.display = 'grid';
                }} else {{
                    tables.forEach(t => t.style.display = 'block');
                    gridView.style.display = 'none';
                }}
            }});
        }});

        // 全选功能
        function setupSelectAll(tableId, selectAllId) {{
            const selectAll = document.getElementById(selectAllId);
            const table = document.querySelector(tableId);
            if (!selectAll || !table) return;

            selectAll.addEventListener('change', function() {{
                const checkboxes = table.querySelectorAll('tbody input[type="checkbox"]');
                checkboxes.forEach(checkbox => checkbox.checked = this.checked);
            }});

            table.addEventListener('change', function(e) {{
                if (e.target.type === 'checkbox' && e.target !== selectAll) {{
                    const checkboxes = table.querySelectorAll('tbody input[type="checkbox"]');
                    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                    selectAll.checked = allChecked;
                }}
            }});
        }}

        // 反选功能
        function invertSelection(tableId) {{
            const table = document.getElementById(tableId);
            const checkboxes = table.querySelectorAll('tbody input[type="checkbox"]');
            checkboxes.forEach(checkbox => checkbox.checked = !checkbox.checked);
            
            // 更新全选框状态
            const selectAllId = tableId === 'existing-table' ? 'existing-select-all' : 'new-select-all';
            const selectAll = document.getElementById(selectAllId);
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            selectAll.checked = allChecked;
        }}

        // 导出选中状态
        function exportSelectionState() {{
            const state = {{
                existing: getTableState('existing-table'),
                new: getTableState('new-table')
            }};
            
            const blob = new Blob([JSON.stringify(state)], {{ type: 'application/json' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'selection_state.json';
            document.body.appendChild(a);
            a.click();
            URL.revokeObjectURL(url);
            document.body.removeChild(a);
        }}

        // 导入选中状态
        function importSelectionState(event) {{
            const file = event.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = function(e) {{
                try {{
                    const state = JSON.parse(e.target.result);
                    applyTableState('existing-table', state.existing);
                    applyTableState('new-table', state.new);
                }} catch (error) {{
                    console.error('导入状态失败:', error);
                    alert('导入状态失败，请检查文件格式');
                }}
            }};
            reader.readAsText(file);
        }}

        // 获取表格选中状态
        function getTableState(tableId) {{
            const table = document.getElementById(tableId);
            const state = {{}};
            table.querySelectorAll('tbody tr').forEach(row => {{
                const checkbox = row.querySelector('input[type="checkbox"]');
                const artistName = row.querySelector('.name-cell').textContent;
                state[artistName] = checkbox.checked;
            }});
            return state;
        }}

        // 应用表格选中状态
        function applyTableState(tableId, state) {{
            const table = document.getElementById(tableId);
            table.querySelectorAll('tbody tr').forEach(row => {{
                const checkbox = row.querySelector('input[type="checkbox"]');
                const artistName = row.querySelector('.name-cell').textContent;
                if (state.hasOwnProperty(artistName)) {{
                    checkbox.checked = state[artistName];
                }}
            }});
        }}

        // 导出功能
        function exportSelected(type) {{
            let content = [];
            
            ['existing-table', 'new-table'].forEach(tableId => {{
                const table = document.getElementById(tableId);
                const rows = table.querySelectorAll('tbody tr');
                rows.forEach(row => {{
                    const checkbox = row.querySelector('input[type="checkbox"]');
                    if (checkbox && checkbox.checked) {{
                        if (type === 'artists') {{
                            const artistName = row.querySelector('.name-cell').textContent;
                            content.push(artistName);
                        }} else if (type === 'files') {{
                            const filesList = row.querySelector('.files-list').innerHTML;
                            content.push(...filesList.split('<br>'));
                        }}
                    }}
                }});
            }});
            
            if (content.length > 0) {{
                const blob = new Blob([content.join('\\n')], {{ type: 'text/plain' }});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = type === 'artists' ? 'selected_artists.txt' : 'selected_files.txt';
                document.body.appendChild(a);
                a.click();
                URL.revokeObjectURL(url);
                document.body.removeChild(a);
            }} else {{
                alert('请先选择要导出的内容！');
            }}
        }}

        // 初始化
        setupSelectAll('#existing-table', 'existing-select-all');
        setupSelectAll('#new-table', 'new-select-all');
    </script>
</body>
</html>
'''
        
        def generate_table_row(preview: ArtistPreview) -> str:
            files_list = '<br>'.join(preview.files)
            if preview.is_existing:
                return f"""
                    <tr>
                        <td><input type="checkbox" checked></td>
                        <td class="name-cell">{preview.name}</td>
                        <td><div class="files-list">{files_list}</div></td>
                    </tr>
                """
            else:
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
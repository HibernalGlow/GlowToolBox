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
            
            try:
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
                            img_url = img['src']
                            if not img_url.startswith('http'):
                                img_url = f"https:{img_url}"
                            return img_url  # 直接返回第一个找到的图片URL
            
                    logger.warning(f"未找到画师 {clean_name} 的预览图")
                    return None
            except aiohttp.ClientError as e:
                logger.warning(f"请求画师 {clean_name} 预览图时网络错误: {e}")
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
        
        # 计算总数
        total_artists = len(existing_artists) + len(new_artists)
        processed_count = 0
        
        # 异步处理所有画师
        existing_previews = []
        new_previews = []
        
        # 处理已存在的画师
        logger.info(f"开始处理已存在画师 ({len(existing_artists)} 个)...")
        for folder, files in existing_artists.items():
            try:
                preview = await self.process_artist(folder, files, True)
                existing_previews.append(preview)
            except Exception as e:
                logger.error(f"处理已存在画师失败 {folder}: {e}")
                # 添加一个空的预览，保持数据完整性
                existing_previews.append(ArtistPreview(
                    name=folder.strip('[]'),
                    folder=folder,
                    preview_url="",
                    files=files,
                    is_existing=True
                ))
            processed_count += 1
            logger.info(f"进度: [{processed_count}/{total_artists}] - {folder}")
        
        # 处理新画师
        logger.info(f"\n开始处理新画师 ({len(new_artists)} 个)...")
        for folder, files in new_artists.items():
            try:
                preview = await self.process_artist(folder, files, False)
                new_previews.append(preview)
            except Exception as e:
                logger.error(f"处理新画师失败 {folder}: {e}")
                # 添加一个空的预览，保持数据完整性
                new_previews.append(ArtistPreview(
                    name=folder.strip('[]'),
                    folder=folder,
                    preview_url="",
                    files=files,
                    is_existing=False
                ))
            processed_count += 1
            logger.info(f"进度: [{processed_count}/{total_artists}] - {folder}")
        
        logger.info(f"\n处理完成! 总共处理了 {total_artists} 个画师")
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
            <input type="file" id="importArtists" style="display: none" accept=".txt" onchange="importArtistsList(event)">
            <button class="btn" onclick="document.getElementById('importArtists').click()">导入画师列表</button>
        </div>
        <div class="btn-group">
            <button class="btn" onclick="refreshImages()">刷新未加载图片</button>
            <div class="mode-switch active" data-mode="table">表格模式</div>
            <div class="mode-switch" data-mode="grid">图墙模式</div>
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
            let state = {{
                existing: {{}},
                new: {{}}
            }};
            
            ['existing-table', 'new-table'].forEach(tableId => {{
                const table = document.getElementById(tableId);
                const rows = table.querySelectorAll('tbody tr');
                rows.forEach(row => {{
                    const checkbox = row.querySelector('input[type="checkbox"]');
                    const artistName = row.querySelector('.name-cell').textContent;
                    if (checkbox) {{
                        state[tableId === 'existing-table' ? 'existing' : 'new'][artistName] = checkbox.checked;
                        if (checkbox.checked) {{
                            if (type === 'artists') {{
                                content.push(artistName);
                            }} else if (type === 'files') {{
                                const filesList = row.querySelector('.files-list').innerHTML;
                                content.push(...filesList.split('<br>'));
                            }}
                        }}
                    }}
                }});
            }});
            
            if (content.length > 0) {{
                // 导出纯文本文件
                const textBlob = new Blob([content.join('\\n')], {{ type: 'text/plain' }});
                const textUrl = URL.createObjectURL(textBlob);
                const textLink = document.createElement('a');
                textLink.href = textUrl;
                textLink.download = type === 'artists' ? 'selected_artists.txt' : 'selected_files.txt';
                document.body.appendChild(textLink);
                textLink.click();
                URL.revokeObjectURL(textUrl);
                document.body.removeChild(textLink);

                // 导出带状态的JSON文件
                const jsonData = {{
                    content: content,
                    state: state,
                    exportType: type,
                    exportTime: new Date().toISOString()
                }};
                const jsonBlob = new Blob([JSON.stringify(jsonData, null, 2)], {{ type: 'application/json' }});
                const jsonUrl = URL.createObjectURL(jsonBlob);
                const jsonLink = document.createElement('a');
                jsonLink.href = jsonUrl;
                jsonLink.download = type === 'artists' ? 'selected_artists_with_state.json' : 'selected_files_with_state.json';
                document.body.appendChild(jsonLink);
                jsonLink.click();
                URL.revokeObjectURL(jsonUrl);
                document.body.removeChild(jsonLink);
            }} else {{
                alert('请先选择要导出的内容！');
            }}
        }}

        // 生成预览链接
        function generatePreviewUrl(artistName) {{
            return `https://www.wn01.uk/search/?q=${{encodeURIComponent(artistName)}}`;
        }}

        // 初始化
        setupSelectAll('#existing-table', 'existing-select-all');
        setupSelectAll('#new-table', 'new-select-all');

        // 为每个画师名添加预览链接
        document.querySelectorAll('.name-cell').forEach(cell => {{
            const artistName = cell.textContent;
            const previewUrl = generatePreviewUrl(artistName);
            const previewLink = document.createElement('a');
            previewLink.href = previewUrl;
            previewLink.target = '_blank';
            previewLink.className = 'preview-link btn';
            previewLink.textContent = '预览';
            previewLink.style.marginLeft = '10px';
            previewLink.style.fontSize = '12px';
            previewLink.style.padding = '2px 8px';
            cell.innerHTML = `${{artistName}} `;
            cell.appendChild(previewLink);
        }});

        // 刷新未加载图片
        async function refreshImages() {{
            const refreshButton = document.querySelector('button[onclick="refreshImages()"]');
            refreshButton.disabled = true;
            refreshButton.textContent = '刷新中...';
            
            try {{
                const images = document.querySelectorAll('.preview-cell');
                let refreshCount = 0;
                
                for (const cell of images) {{
                    if (cell.textContent === '无预览图' || cell.querySelector('img[src=""]')) {{
                        const row = cell.closest('tr');
                        const artistName = row.querySelector('.name-cell').textContent.trim();
                        const searchUrl = generatePreviewUrl(artistName);
                        
                        try {{
                            const response = await fetch(searchUrl);
                            const html = await response.text();
                            const parser = new DOMParser();
                            const doc = parser.parseFromString(html, 'text/html');
                            
                            const galleryItems = doc.querySelectorAll('.gallary_item');
                            for (const item of galleryItems) {{
                                const img = item.querySelector('img');
                                if (img && img.src) {{
                                    const imgUrl = 'https:' + img.getAttribute('src');
                                    try {{
                                        const imgResponse = await fetch(imgUrl);
                                        if (imgResponse.ok) {{
                                            cell.innerHTML = `<img src="${imgUrl}" class="preview-img">`;
                                            refreshCount++;
                                            break;
                                        }}
                                    }} catch (error) {{
                                        continue;
                                    }}
                                }}
                            }}
                        }} catch (error) {{
                            console.error(`刷新 ${artistName} 的预览图失败:`, error);
                        }}
                    }}
                }}
                
                alert(`刷新完成！成功加载 ${refreshCount} 张预览图`);
            }} catch (error) {{
                console.error('刷新图片时出错:', error);
                alert('刷新图片时出错，请查看控制台了解详情');
            }} finally {{
                refreshButton.disabled = false;
                refreshButton.textContent = '刷新未加载图片';
            }}
        }}

        // 导入画师列表
        async function importArtistsList(event) {{
            const file = event.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = function(e) {{
                try {{
                    const artists = e.target.result.split('\\n')
                        .map(line => line.trim())
                        .filter(line => line.length > 0);
                    
                    // 取消所有选中状态
                    ['existing-table', 'new-table'].forEach(tableId => {{
                        const table = document.getElementById(tableId);
                        const checkboxes = table.querySelectorAll('tbody input[type="checkbox"]');
                        checkboxes.forEach(checkbox => checkbox.checked = false);
                    }});
                    
                    // 选中匹配的画师
                    let matchCount = 0;
                    artists.forEach(artistName => {{
                        ['existing-table', 'new-table'].forEach(tableId => {{
                            const table = document.getElementById(tableId);
                            table.querySelectorAll('tbody tr').forEach(row => {{
                                const nameCell = row.querySelector('.name-cell');
                                const rowArtistName = nameCell.textContent.trim();
                                if (rowArtistName === artistName) {{
                                    const checkbox = row.querySelector('input[type="checkbox"]');
                                    if (checkbox) {{
                                        checkbox.checked = true;
                                        matchCount++;
                                    }}
                                }}
                            }});
                        }});
                    }});
                    
                    // 更新全选框状态
                    ['existing-table', 'new-table'].forEach(tableId => {{
                        const selectAllId = tableId === 'existing-table' ? 'existing-select-all' : 'new-select-all';
                        const selectAll = document.getElementById(selectAllId);
                        const table = document.getElementById(tableId);
                        const checkboxes = table.querySelectorAll('tbody input[type="checkbox"]');
                        const allChecked = Array.from(checkboxes).every(cb => cb.checked);
                        selectAll.checked = allChecked;
                    }});
                    
                    alert(`导入完成！匹配到 ${matchCount} 个画师`);
                }} catch (error) {{
                    console.error('导入画师列表失败:', error);
                    alert('导入画师列表失败，请检查文件格式');
                }}
            }};
            reader.readAsText(file);
            event.target.value = ''; // 清除文件选择，允许重复导入同一个文件
        }}
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
        # 生成带中文时间戳的文件名
        current_time = datetime.now()
        timestamp = current_time.strftime("%Y年%m月%d日_%H时%M分%S秒")
        output_path = Path(yaml_path).parent / f'画师预览_{timestamp}.html'
    
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
    
    # 设置输出路径（带中文时间戳）
    current_time = datetime.now()
    timestamp = current_time.strftime("%Y年%m月%d日_%H时%M分%S秒")
    output_path = Path(yaml_path).parent / f'画师预览_{timestamp}.html'
    
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
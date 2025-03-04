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
import shutil
from tqdm import tqdm
from tqdm.asyncio import tqdm as atqdm

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
        self.template_dir = Path(__file__).parent / 'artist_preview'
        
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

    def _generate_table_row(self, preview: ArtistPreview) -> str:
        """生成表格行HTML"""
        files_list = '<br>'.join(preview.files)
        preview_link = f'<a href="#" onclick="openPreview(\'{preview.name}\')" class="preview-link">预览</a>'
        
        if preview.is_existing:
            return f"""
                <tr>
                    <td><input type="checkbox" data-artist="{preview.name}" checked></td>
                    <td class="artist-name">{preview.name}</td>
                    <td>{preview_link}</td>
                    <td><div class="files-list">{files_list}</div></td>
                </tr>
            """
        else:
            preview_img = f'<img src="{preview.preview_url}" class="preview-img" onclick="openPreview(\'{preview.name}\')">' if preview.preview_url else '无预览图'
            return f"""
                <tr>
                    <td><input type="checkbox" data-artist="{preview.name}"></td>
                    <td class="preview-cell">{preview_img}</td>
                    <td class="artist-name">{preview.name}</td>
                    <td>{preview_link}</td>
                    <td><div class="files-list">{files_list}</div></td>
                </tr>
            """

    def _generate_grid_item(self, preview: ArtistPreview) -> str:
        """生成网格视图项HTML"""
        files_list = '<br>'.join(preview.files)
        preview_img = preview.preview_url if not preview.is_existing else ""
        
        return f"""
            <div class="grid-item">
                <img src="{preview_img}" class="preview-img" onclick="openPreview('{preview.name}')" 
                     onerror="this.src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='">
                <h4>{preview.name}</h4>
                <div class="checkbox-wrapper">
                    <input type="checkbox" data-artist="{preview.name}" {' checked' if preview.is_existing else ''}>
                </div>
                <div class="files-list">{files_list}</div>
            </div>
        """

    async def process_yaml(self, yaml_path: str) -> Tuple[List[ArtistPreview], List[ArtistPreview]]:
        """处理yaml文件，返回新旧画师预览信息"""
        # 读取yaml文件
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # 获取画师信息
        existing_artists = data['artists']['existing_artists']
        new_artists = data['artists']['new_artists']
        
        # 创建进度条
        print("处理已存在画师...")
        existing_tasks = [
            self.process_artist(folder, files, True)
            for folder, files in existing_artists.items()
        ]
        
        print("处理新画师...")
        new_tasks = [
            self.process_artist(folder, files, False)
            for folder, files in new_artists.items()
        ]
        
        # 使用tqdm显示进度
        existing_previews = await atqdm.gather(*existing_tasks, 
                                             desc="处理已存在画师",
                                             ncols=80,
                                             colour="green")
        
        new_previews = await atqdm.gather(*new_tasks,
                                         desc="处理新画师",
                                         ncols=80,
                                         colour="blue")
        
        return existing_previews, new_previews

    def _ensure_template_files(self):
        """确保模板文件存在"""
        if not self.template_dir.exists():
            logger.info("创建模板目录结构...")
            self.template_dir.mkdir(parents=True, exist_ok=True)
            (self.template_dir / 'templates').mkdir(exist_ok=True)
            (self.template_dir / 'static' / 'js').mkdir(parents=True, exist_ok=True)
            (self.template_dir / 'static' / 'css').mkdir(parents=True, exist_ok=True)

    def generate_html(self, existing_previews: List[ArtistPreview], 
                     new_previews: List[ArtistPreview], 
                     output_path: str):
        """生成HTML预览页面"""
        self._ensure_template_files()
        
        print("生成HTML内容...")
        with tqdm(total=4, desc="生成页面", ncols=80, colour="cyan") as pbar:
            # 生成表格行和网格项
            existing_rows = '\n'.join(self._generate_table_row(p) for p in existing_previews)
            new_rows = '\n'.join(self._generate_table_row(p) for p in new_previews)
            pbar.update(1)
            
            existing_grid = '\n'.join(self._generate_grid_item(p) for p in existing_previews)
            new_grid = '\n'.join(self._generate_grid_item(p) for p in new_previews)
            pbar.update(1)
            
            # 读取模板文件
            template_path = self.template_dir / 'templates' / 'index.html'
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
            pbar.update(1)
            
            # 替换模板变量
            html_content = template.format(
                existing_rows=existing_rows,
                new_rows=new_rows,
                existing_grid=existing_grid,
                new_grid=new_grid
            )
            
            # 复制静态文件
            output_dir = Path(output_path).parent
            static_dir = output_dir / 'static'
            if static_dir.exists():
                shutil.rmtree(static_dir)
            shutil.copytree(self.template_dir / 'static', static_dir)
            
            # 保存HTML文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            pbar.update(1)
        
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
            import bs4
            import tqdm
        except ImportError:
            print("正在安装必要的依赖...")
            os.system("pip install aiohttp beautifulsoup4 tqdm")
            import aiohttp
            import bs4
            import tqdm
        
        # 运行生成器
        asyncio.run(generate_preview_tables(yaml_path, str(output_path)))
        print(f"\n预览页面已生成: {output_path}")
    except Exception as e:
        print(f"\n生成预览页面时出错: {e}")
        if input("是否显示详细错误信息？(y/n): ").lower() == 'y':
            import traceback
            traceback.print_exc() 
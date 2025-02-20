import os
import json
import time
import re
from datetime import datetime, timedelta
import requests
import logging
from tqdm import tqdm
import hashlib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('update_check.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def get_page_content(artist_name):
    url = f"https://www.wn05.cc/search/?q={artist_name}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
        'Connection': 'keep-alive',
    }
    
    session = requests.Session()
    session.verify = False
    requests.packages.urllib3.disable_warnings()
    
    try:
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        content = response.text
        
        # 计算内容hash
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        
        return {
            'content': content,
            'hash': content_hash,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        logging.error(f"获取页面失败: {str(e)}")
        return None

def load_html_history(history_file='html_history.json'):
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_html_history(data, history_file='html_history.json'):
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def extract_artist_name(folder_name):
    paren_match = re.search(r'\((.*?)\)', folder_name)
    if paren_match:
        return paren_match.group(1)
    
    bracket_match = re.search(r'\[(.*?)\]', folder_name)
    if bracket_match:
        return bracket_match.group(1)
    
    return folder_name

def main():
    base_path = r"E:\1BACKUP\ehv\update"
    image_history = load_image_history()
    updates = {}
    
    folders = os.listdir(base_path)
    logging.info(f"开始检查更新，共 {len(folders)} 个文件夹")
    
    for folder in tqdm(folders, desc="检查画师更新"):
        if os.path.isdir(os.path.join(base_path, folder)):
            artist_name = extract_artist_name(folder)
            logging.info(f"检查画师: {artist_name}")
            
            # 获取当前搜索结果中的图片
            current_images = get_search_images(artist_name)
            if not current_images:
                continue
            
            # 检查是否是首次记录
            if artist_name not in image_history:
                logging.info(f"首次记录画师: {artist_name}")
                image_history[artist_name] = {
                    'images': current_images,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'is_first_record': True
                }
                continue
            
            # 检查是否有新图片
            old_images = set(image_history[artist_name]['images'])
            new_images = set(current_images) - old_images
            if new_images:
                updates[artist_name] = {
                    'new_images': list(new_images),
                    'last_check': image_history[artist_name]['timestamp'],
                    'current_check': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                logging.info(f"发现新图片: {artist_name}")
            
            # 更新历史记录
            image_history[artist_name].update({
                'images': current_images,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'is_first_record': False
            })
            
            # 保存页面内容（可选）
            os.makedirs('html_archive', exist_ok=True)
            with open(f'html_archive/{artist_name}_{current_page["timestamp"].replace(":", "-")}.html', 'w', encoding='utf-8') as f:
                f.write(current_page['content'])
            
            time.sleep(2)  # 防止请求过快
    
    # 保存历史记录
    save_html_history(image_history)
    
    # 生成更新报告
    if updates:
        report = f"# 画师页面更新 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n"
        for artist, update_info in updates.items():
            report += f"## {artist}\n"
            report += f"- 上次检查: {update_info['last_check']}\n"
            report += f"- 本次检查: {update_info['current_check']}\n\n"
        
        with open('updates.md', 'a', encoding='utf-8') as f:
            f.write(report)
        logging.info("已生成更新报告")
    else:
        logging.info("暂无更新")

if __name__ == "__main__":
    logging.info("启动更新检查程序")
    while True:
        try:
            main()
        except Exception as e:
            logging.error(f"程序错误: {str(e)}", exc_info=True)
        
        next_check = datetime.now() + timedelta(hours=1)
        logging.info(f"下次检查时间: {next_check.strftime('%Y-%m-%d %H:%M:%S')}")
        time.sleep(3600)
import os
import re
from zipfile import ZipFile
from PIL import Image

def compare_zips(base_path, special_keywords=None, filter_keywords=None, size_difference_threshold=1024):
    if special_keywords is None:
        special_keywords = []
    if filter_keywords is None:
        filter_keywords = []

    def clean_name(name):
        # 移除括号内的内容以便于比较
        name = re.sub(r'\[[^\[\]]*?\]', '', name)  # 移除 []
        name = re.sub(r'\([^)]*?\)', '', name)     # 移除 ()
        return name.strip()

    from zipfile import ZipFile, BadZipFile
    from PIL import Image

    def count_images_in_zip(zip_path):
        try:
            # 尝试打开 ZIP 文件
            with ZipFile(zip_path, 'r') as zip_file:
                image_count = 0
                for filename in zip_file.namelist():
                    if filename.lower().endswith(('.jpg', '.jpeg', '.avif', '.jxl', '.tdel', '.webp', '.png')):
                        image_count += 1
                        # try:
                        #     with zip_file.open(filename) as img_file:
                        #         Image.open(img_file).verify()
                                # image_count += 1
                        # except Exception as e:
                        #     print(f"Error verifying image {filename} in {zip_path}: {e}")
                return image_count
        except BadZipFile:
            print(f"Warning: {zip_path} is not a valid ZIP file.")
            return None    
    def has_special_keywords(name):
        return any(keyword in name for keyword in special_keywords)

    def has_filter_keywords(name):
        return any(keyword in name for keyword in filter_keywords)

    zips_info = {}

    for root, _, files in os.walk(base_path):
        for file in files:
            if file.lower().endswith('.zip'):
                zip_path = os.path.join(root, file)
                name = os.path.splitext(file)[0]
                base_name = clean_name(name)
                if root not in zips_info:
                    zips_info[root] = {}
                if base_name not in zips_info[root]:
                    zips_info[root][base_name] = []
                zips_info[root][base_name].append((zip_path, name))

    for folder, folder_zips in zips_info.items():
        for base_name, zips in folder_zips.items():
            if len(zips) > 1:
                # 过滤掉包含过滤关键词的文件
                filtered_zips = [(zip_path, name) for zip_path, name in zips if not has_filter_keywords(name)]

                # 检查文件大小差异
                sizes = [os.path.getsize(zip_path) for zip_path, _ in filtered_zips]
                if max(sizes) - min(sizes) > size_difference_threshold:
                    continue

                # 检查图片数量
                image_counts = [count_images_in_zip(zip_path) for zip_path, _ in filtered_zips]
                if len(set(image_counts)) != 1:
                    continue

                # 检查文件名相似度
                cleaned_names = [clean_name(name) for _, name in filtered_zips]
                if len(set(cleaned_names)) != 1 or len(cleaned_names[0]) <= same_name_threshold :
                    continue

                # 保留不包含特殊关键词的压缩包
                no_keyword_zips = [(zip_path, name) for zip_path, name in filtered_zips if not has_special_keywords(name)]

                if no_keyword_zips:
                    # 保留不包含特殊关键词的文件
                    shortest_zip = min(no_keyword_zips, key=lambda x: len(clean_name(x[1])))
                    files_to_remove = [zip_path for zip_path, _ in filtered_zips if zip_path != shortest_zip[0]]
                else:
                    # 如果没有特殊关键词，则保留更短的文件名
                    shortest_zip = min(filtered_zips, key=lambda x: len(clean_name(x[1])))
                    files_to_remove = [zip_path for zip_path, _ in filtered_zips if zip_path != shortest_zip[0]]

                # 将选中的文件进行重命名加后缀 .cbz
                for zip_path in files_to_remove:
                    try:
                        if os.path.exists(zip_path):
                            new_zip_path = zip_path + '.cbz'
                            os.rename(zip_path, new_zip_path)
                            print(f"Renamed zip: {zip_path} to {new_zip_path}")
                        else:
                            print(f"Warning: File not found, skipping rename: {zip_path}")
                    except (FileNotFoundError, PermissionError) as e:
                        print(f"Error while renaming zip file {zip_path}: {e}")

# Usage example
base_path = input("请输入目标目录路径: ")
same_name_threshold=3
special_keywords = ['^','_']  # Keywords for zips that must be retained
filter_keywords = ['全彩']  # Keywords for zips that should be filtered out
size_difference_threshold = 1000  # 文件大小差异阈值
compare_zips(base_path, special_keywords, filter_keywords, size_difference_threshold)
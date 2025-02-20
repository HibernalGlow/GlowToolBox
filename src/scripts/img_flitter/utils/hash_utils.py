import json
from datetime import datetime
from ..services.logging_service import LoggingService
import logging
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), '1ehv'))
from nodes.pics.calculate_hash_custom import ImageHashCalculator


class HashFileHandler:
    """处理哈希文件的类"""
    
    # 用于临时存储相似性记录的类变量
    similarity_records = []
    
    @staticmethod
    def clear_similarity_records():
        """清空相似性记录"""
        HashFileHandler.similarity_records = []
    
    @staticmethod
    def record_similarity(file_path, similar_uri, hamming_distance):
        """记录相似文件的对应关系到内存中
        
        Args:
            file_path: 当前处理的文件路径
            similar_uri: 相似文件的URI
            hamming_distance: 汉明距离
        """
        try:
            # 添加相似性信息
            similarity_info = {
                'file_path': file_path,
                'similar_uri': similar_uri,
                'hamming_distance': hamming_distance,
                'timestamp': datetime.now().isoformat()
            }
            
            HashFileHandler.similarity_records.append(similarity_info)
            logging.info( f"[#update_log]已记录相似性: {file_path} -> {similar_uri} (距离: {hamming_distance})")
            # 添加哈希操作面板标识
            
        except Exception as e:
            logging.info(f"[#update_log]- 记录相似性时出错: {str(e)}")

    @staticmethod
    def get_similarity_records():
        """获取所有相似性记录"""
        return HashFileHandler.similarity_records

    @staticmethod
    def load_hash_file(hash_file_path):
        """加载哈希文件并对哈希值进行预处理
        
        Args:
            hash_file_path: 哈希文件路径
            
        Returns:
            tuple: (哈希值列表, 哈希值到URI的映射字典)
        """
        try:
            if not hash_file_path:
                logging.info("[#file_ops]未提供哈希文件路径")
                return [], {}
                
            logging.info(f"[#file_ops]尝试加载哈希文件: {hash_file_path}")
            
            if not os.path.exists(hash_file_path):
                logging.info(f"[#file_ops]哈希文件不存在: {hash_file_path}")
                return [], {}
                
            with open(hash_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            logging.info(f"[#update_log]✅ 成功读取哈希文件: {hash_file_path}")
            
            # 提取所有哈希值并建立映射关系
            hash_to_uri = {}
            hash_values = []
            
            # 首先尝试新格式 (hashes字段)
            hashes_data = data.get('hashes', {})
            if not hashes_data:
                # 如果没有hashes字段,尝试旧格式 (results字段)
                hashes_data = data.get('results', {})
            
            total_count = len(hashes_data)
            loaded_count = 0
            
            for uri, info in hashes_data.items():
                # 处理不同格式的哈希值
                if isinstance(info, dict):
                    # 新格式: {'hash': 'xxx'} 或旧格式: {'hash_value': 'xxx'}
                    hash_str = str(info.get('hash') or info.get('hash_value', ''))
                elif isinstance(info, str):
                    # 直接是哈希字符串
                    hash_str = info
                else:
                    continue
                    
                # 验证哈希值
                if not hash_str:
                    continue
                    
                # 统一使用小写
                hash_str = hash_str.lower()
                hash_values.append(hash_str)
                hash_to_uri[hash_str] = uri
                
                loaded_count += 1
                if loaded_count % 1000 == 0:  # 每1000个显示一次进度
                    percentage = (loaded_count / total_count) * 100
                    logging.info(f"[@hash_calc] 加载哈希文件 {percentage:.1f}%")
            
            # 合并日志输出
            logging.info(f"[#hash_calc]加载哈希文件完成")
            logging.info(f"[#update_log]✅ 哈希文件加载完成 - 总数: {len(hash_values)}个")
            logging.info(f"[#hash_calc]哈希值数量: {len(hash_values)}")
            logging.info(f"[#hash_calc]URI映射数量: {len(hash_to_uri)}")
            
            return hash_values, hash_to_uri
                
        except Exception as e:
            logging.error(f"[#hash_calc]❌ 加载哈希文件失败: {str(e)}")
            return [], {}

    @staticmethod
    def find_similar_hash(target_hash, ref_hashes, hash_to_uri, hamming_distance_threshold):
        """遍历所有哈希值进行完整比较
        
        Args:
            target_hash: 目标哈希值（可以是字典格式或字符串格式）
            ref_hashes: 参考哈希值列表
            hash_to_uri: 哈希值到URI的映射字典
            hamming_distance_threshold: 汉明距离阈值
            
        Returns:
            tuple: (是否找到相似值, 相似哈希值, 对应的URI)
        """
        try:
            # 如果没有外部哈希文件，直接返回未找到
            if not ref_hashes:
                return False, None, None

            # 统一获取哈希值字符串
            def get_hash_str(hash_obj):
                if isinstance(hash_obj, dict):
                    return str(hash_obj.get('hash') or hash_obj.get('phash') or hash_obj.get('hash_value', '')).lower()
                return str(hash_obj).lower()
                
            # 提取目标哈希值
            target_hash_str = get_hash_str(target_hash)
            target_url = target_hash.get('url', '') if isinstance(target_hash, dict) else ''
            
            # 记录比较过程
            logging.debug(f"[#hash_calc]开始查找相似哈希值: {target_hash_str}" + (f" (来自: {target_url})" if target_url else ""))
            
            compared_count = 0
            max_diff = 2 ** hamming_distance_threshold  # 最大可能的差异值
            
            # 遍历所有哈希值进行比较
            for current_hash in ref_hashes:
                # 提取当前哈希值
                current_hash_str = get_hash_str(current_hash)
                current_url = current_hash.get('url', '') if isinstance(current_hash, dict) else ''
                
                # 计算汉明距离
                hamming_distance = ImageHashCalculator.calculate_hamming_distance(target_hash_str, current_hash_str)
                
                compared_count += 1
                
                if hamming_distance <= hamming_distance_threshold:
                    # 找到相似的哈希值
                    result_msg = f"[#hash_calc]找到相似哈希值: {current_hash_str}"
                    if current_url:
                        result_msg += f" (来自: {current_url})"
                    result_msg += f", 汉明距离: {hamming_distance}, URI: {hash_to_uri[current_hash_str]}"
                    logging.info(result_msg)
                    return True, current_hash_str, hash_to_uri[current_hash_str]
            
            return False, None, None
            
        except Exception as e:
            logging.info(f"[#hash_calc]查找相似哈希值时出错: {str(e)}")
            return False, None, None


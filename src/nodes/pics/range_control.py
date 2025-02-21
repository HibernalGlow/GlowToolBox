from typing import List, Tuple, Union, Optional, Set
import os

class RangeControl:
    """处理文件范围控制的类"""
    
    @staticmethod
    def normalize_range(range_tuple: Tuple[Optional[int], Optional[int]], total_length: int) -> Tuple[int, int]:
        """
        将范围元组标准化为正整数索引
        
        Args:
            range_tuple: (start, end) 范围元组，可以包含None和负数
            total_length: 总长度
            
        Returns:
            Tuple[int, int]: 标准化后的(start, end)索引对
        """
        start, end = range_tuple
        
        # 处理起始索引
        if start is None:
            start = 0
        elif start < 0:
            start = max(0, total_length + start)
        else:
            start = min(start, total_length)
            
        # 处理结束索引
        if end is None:
            end = total_length
        elif end < 0:
            end = max(0, total_length + end + 1)  # +1是为了包含end位置
        else:
            end = min(end, total_length)
            
        return (start, end)
    
    @staticmethod
    def combine_ranges(ranges: List[Tuple[int, int]], mode: str = "union") -> List[Tuple[int, int]]:
        """
        合并多个范围
        
        Args:
            ranges: 范围列表，每个范围是(start, end)元组
            mode: 合并模式，"union"表示并集，"intersection"表示交集
            
        Returns:
            List[Tuple[int, int]]: 合并后的范围列表
        """
        if not ranges:
            return []
            
        # 排序范围
        sorted_ranges = sorted(ranges, key=lambda x: (x[0], x[1]))
        
        if mode == "intersection":
            # 求交集
            result = [sorted_ranges[0]]
            for current in sorted_ranges[1:]:
                last = result[-1]
                # 找到重叠部分
                start = max(last[0], current[0])
                end = min(last[1], current[1])
                if start <= end:
                    result[-1] = (start, end)
                else:
                    return []  # 无交集
            return result
            
        else:  # union模式
            # 合并重叠的范围
            result = [sorted_ranges[0]]
            for current in sorted_ranges[1:]:
                last = result[-1]
                if current[0] <= last[1] + 1:
                    # 范围重叠或相邻，合并
                    result[-1] = (last[0], max(last[1], current[1]))
                else:
                    # 新的不重叠范围
                    result.append(current)
            
            return result
    
    @staticmethod
    def get_indices_from_ranges(ranges: List[Tuple[int, int]]) -> Set[int]:
        """
        从范围列表获取所有索引的集合
        
        Args:
            ranges: 范围列表，每个范围是(start, end)元组，end是包含的
            
        Returns:
            Set[int]: 所有索引的集合
        """
        indices = set()
        for start, end in ranges:
            indices.update(range(start, end + 1))  # 修改为包含 end
        return indices
    
    @staticmethod
    def process_range_control(range_control: dict, total_length: int) -> Set[int]:
        """
        处理范围控制配置
        
        Args:
            range_control: 范围控制配置字典
            total_length: 总文件数
            
        Returns:
            Set[int]: 需要处理的文件索引集合
        """
        if not range_control or "ranges" not in range_control:
            return set(range(total_length))
            
        # 标准化所有范围
        normalized_ranges = [
            RangeControl.normalize_range(r, total_length)
            for r in range_control["ranges"]
        ]
        
        # 合并范围
        mode = range_control.get("combine", "union")
        combined_ranges = RangeControl.combine_ranges(normalized_ranges, mode)
        
        # 获取所有索引
        return RangeControl.get_indices_from_ranges(combined_ranges) 
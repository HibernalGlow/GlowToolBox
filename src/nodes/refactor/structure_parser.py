import yaml
import networkx as nx
from typing import Dict, List, Set, Optional
from pathlib import Path

class StructureDefinition:
    """目标结构定义解析器"""
    def __init__(self, structure_file: str):
        self.structure_file = structure_file
        self.structure: Dict[str, Dict] = {}
        self.function_mapping: Dict[str, str] = {}  # 函数名到类路径的映射
        self.variable_mapping: Dict[str, str] = {}  # 变量名到类路径的映射
        self.class_dependencies: Dict[str, Set[str]] = {}  # 类之间的依赖关系
        
    def parse_structure(self) -> None:
        """解析YAML结构定义文件"""
        with open(self.structure_file, 'r', encoding='utf-8') as f:
            structure_data = yaml.safe_load(f)
            
        # 处理类定义
        for class_name, class_data in structure_data.items():
            self.structure[class_name] = {
                'functions': [],
                'variables': [],
                'inner_classes': {},
                'description': class_data.get('description', '类描述')
            }
            self.class_dependencies[class_name] = set()
            
            # 处理函数
            if 'functions' in class_data:
                for func in class_data['functions']:
                    func_name = func.replace('()', '')
                    self.structure[class_name]['functions'].append(func_name)
                    self.function_mapping[func_name] = class_name
                    
                    # 分析函数名中的依赖关系
                    for other_class in self.class_dependencies:
                        if other_class != class_name and other_class.lower() in func_name.lower():
                            self.class_dependencies[class_name].add(other_class)
            
            # 处理变量
            if 'variables' in class_data:
                for var in class_data['variables']:
                    self.structure[class_name]['variables'].append(var)
                    self.variable_mapping[var] = class_name
            
            # 处理内部类
            if 'inner_classes' in class_data:
                for inner_name, inner_data in class_data['inner_classes'].items():
                    inner_class = {
                        'functions': [],
                        'variables': [],
                        'description': inner_data.get('description', '内部类描述')
                    }
                    
                    # 处理内部类函数
                    if 'functions' in inner_data:
                        for func in inner_data['functions']:
                            func_name = func.replace('()', '')
                            inner_class['functions'].append(func_name)
                            path = f"{class_name}.{inner_name}"
                            self.function_mapping[func_name] = path
                    
                    # 处理内部类变量
                    if 'variables' in inner_data:
                        for var in inner_data['variables']:
                            inner_class['variables'].append(var)
                            path = f"{class_name}.{inner_name}"
                            self.variable_mapping[var] = path
                            
                    self.structure[class_name]['inner_classes'][inner_name] = inner_class

    def get_class_order(self) -> List[str]:
        """获取类的依赖顺序"""
        # 创建有向图
        graph = nx.DiGraph()
        for class_name, deps in self.class_dependencies.items():
            graph.add_node(class_name)
            for dep in deps:
                graph.add_edge(class_name, dep)
                
        try:
            # 尝试拓扑排序
            return list(nx.topological_sort(graph))
        except nx.NetworkXUnfeasible:
            # 如果有循环依赖，返回原始顺序
            return list(self.structure.keys())

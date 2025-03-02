import ast
import re
from typing import Dict, List, Set, Tuple, Optional
import networkx as nx
from pathlib import Path
import yaml
import json

# 导入新的YAML结构解析器
from nodes.refactor.structure_parser import StructureDefinition

class CodeAnalyzer:
    def __init__(self, source_file: str):
        self.source_file = source_file
        self.functions: Dict[str, ast.FunctionDef] = {}
        self.classes: Dict[str, ast.ClassDef] = {}
        self.imports: List[str] = []
        self.globals: Dict[str, ast.Assign] = {}
        self.call_graph = nx.DiGraph()
        self.docstrings: Dict[str, str] = {}
        self.other_nodes: List[ast.AST] = []  # 存储其他未分类的节点
        self.original_source: str = ""  # 存储原始源代码
        self.function_paths = {}  # {func_name: (class_name, parent_class, full_path)}
        self.class_hierarchy = {}  # {class_name: parent_class_name}
        
    def parse_file(self) -> None:
        """解析源文件"""
        with open(self.source_file, 'r', encoding='utf-8') as f:
            self.original_source = f.read()
        
        tree = ast.parse(self.original_source)
        self._collect_definitions(tree)
        self._build_call_graph(tree)
        
    def _collect_definitions(self, tree: ast.AST) -> None:
        """收集所有函数、类定义和全局变量"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self.functions[node.name] = node
                docstring = ast.get_docstring(node)
                if docstring:
                    self.docstrings[node.name] = docstring
                    
            elif isinstance(node, ast.ClassDef):
                self.classes[node.name] = node
                docstring = ast.get_docstring(node)
                if docstring:
                    self.docstrings[node.name] = docstring
                    
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                self.imports.append(ast.unparse(node))
                
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.globals[target.id] = node
                        
        # 收集未分类的节点
        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
                self.other_nodes.append(node)

    def _build_call_graph(self, tree: ast.AST) -> None:
        """构建函数调用关系图"""
        # 记录完整的函数调用路径
        self.function_paths = {}  # {func_name: (class_name, parent_class, full_path)}
        self.class_hierarchy = {}  # {class_name: parent_class_name}
        method_calls = []  # 存储所有方法调用
        
        # 第一遍：收集类的继承关系和函数的完整路径
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # 记录类的继承关系
                if node.bases:
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            self.class_hierarchy[node.name] = base.id
                
                # 收集类中的所有方法
                for method in ast.walk(node):
                    if isinstance(method, ast.FunctionDef):
                        full_path = f"{node.name}.{method.name}"
                        parent_class = self.class_hierarchy.get(node.name)
                        self.function_paths[method.name] = (node.name, parent_class, full_path)
        
        # 第二遍：收集和分析所有方法调用
        for func_name, func_node in self.functions.items():
            self.call_graph.add_node(func_name)
            current_class = self.function_paths.get(func_name, (None, None, None))[0]
            
            for node in ast.walk(func_node):
                if isinstance(node, ast.Call):
                    method_calls.append((func_name, node, current_class))
        
        # 处理收集到的方法调用
        for caller_name, call_node, caller_class in method_calls:
            # 直接函数调用 (func())
            if isinstance(call_node.func, ast.Name):
                called_func = call_node.func.id
                if called_func in self.functions:
                    # 检查是否是同类中的调用
                    called_class = self.function_paths.get(called_func, (None, None, None))[0]
                    if called_class == caller_class:
                        # 应该使用self调用
                        print(f"建议修改 {caller_name} 中的 {called_func} 为 self.{called_func}")
                    self.call_graph.add_edge(caller_name, called_func)
            
            # 方法调用 (obj.method())
            elif isinstance(call_node.func, ast.Attribute):
                if isinstance(call_node.func.value, ast.Name):
                    obj_name = call_node.func.value.id
                    method_name = call_node.func.attr
                    
                    # self调用
                    if obj_name == 'self':
                        # 检查是否存在于当前类或父类中
                        current_class = caller_class
                        while current_class:
                            for func, (cls, _, _) in self.function_paths.items():
                                if func == method_name and cls == current_class:
                                    self.call_graph.add_edge(caller_name, method_name)
                                    break
                            current_class = self.class_hierarchy.get(current_class)
                    
                    # 其他对象调用
                    else:
                        # 1. 检查是否是类的直接调用
                        if obj_name in self.classes:
                            # 使用完整路径
                            for func, (cls, _, full_path) in self.function_paths.items():
                                if func == method_name and cls == obj_name:
                                    print(f"找到类方法调用: {obj_name}.{method_name}")
                                    self.call_graph.add_edge(caller_name, method_name)
                                    break
                        
                        # 2. 检查是否是已知函数
                        elif method_name in self.functions:
                            print(f"补充调用关系: {caller_name} -> {method_name}")
                            self.call_graph.add_edge(caller_name, method_name)
        
        # 第三遍：补充分析，确保所有可能的调用都被记录
        print("开始补充分析可能遗漏的调用关系...")
        for func_name, func_node in self.functions.items():
            current_class = self.function_paths.get(func_name, (None, None, None))[0]
            
            for node in ast.walk(func_node):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        method_name = node.func.attr
                        
                        # 如果这个方法存在于任何类中
                        if method_name in self.functions:
                            # 检查是否已经存在这条边
                            if not self.call_graph.has_edge(func_name, method_name):
                                # 获取方法的完整路径
                                _, _, full_path = self.function_paths.get(method_name, (None, None, None))
                                if full_path:
                                    print(f"补充完整调用路径: {func_name} -> {full_path}")
                                self.call_graph.add_edge(func_name, method_name)

    def _get_ordered_functions(self, functions: Set[str]) -> List[str]:
        """根据调用关系对函数进行排序"""
        # 创建子图
        subgraph = self.call_graph.subgraph(functions)
        try:
            # 尝试拓扑排序
            ordered = list(nx.topological_sort(subgraph))
            # 确保所有函数都在结果中
            for func in functions:
                if func not in ordered:
                    ordered.append(func)
            return ordered
        except nx.NetworkXUnfeasible:
            # 如果有循环依赖，使用原始顺序
            return sorted(functions)

class CodeRestructurer:
    def __init__(self, analyzer: CodeAnalyzer, structure: StructureDefinition):
        self.analyzer = analyzer
        self.structure = structure
        self.indentation = "    "
        self.processed_functions = set()  # 记录已处理的函数
        self.processed_variables = set()  # 记录已处理的变量
        
    def restructure(self) -> str:
        """根据目标结构重组代码"""
        output = []
        
        # 添加文件头部注释
        output.append('"""')
        output.append('重组后的代码文件')
        output.append('根据目标结构自动生成')
        output.append('"""')
        output.append("")
        
        # 添加导入语句
        output.extend(sorted(self.analyzer.imports))
        output.append("")
        
        # 添加未分类的全局变量和其他语句
        for node in self.analyzer.other_nodes:
            if isinstance(node, ast.Assign):
                var_name = node.targets[0].id if isinstance(node.targets[0], ast.Name) else None
                if var_name and var_name not in self.processed_variables:
                    output.append(ast.unparse(node))
                    self.processed_variables.add(var_name)
            else:
                output.append(ast.unparse(node))
        output.append("")
        
        # 获取类的依赖顺序
        ordered_classes = self.structure.get_class_order()
        
        # 按照依赖顺序处理类
        for class_name in ordered_classes:
            class_def = self.structure.structure[class_name]
            
            # 添加类定义
            output.append(f"class {class_name}:")
            if class_name in self.analyzer.docstrings:
                output.append(f'{self.indentation}"""{self.analyzer.docstrings[class_name]}"""')
            else:
                output.append(f'{self.indentation}"""')
                output.append(f'{self.indentation}{class_def.get("description", "类描述")}')
                output.append(f'{self.indentation}"""')
            
            # 添加类变量
            for var in class_def['variables']:
                if var in self.analyzer.globals:
                    output.append(f"{self.indentation}{ast.unparse(self.analyzer.globals[var])}")
                    self.processed_variables.add(var)
            
            # 添加内部类
            for inner_class, inner_def in class_def['inner_classes'].items():
                output.append("")
                output.append(f"{self.indentation}class {inner_class}:")
                
                # 添加内部类变量
                for var in inner_def['variables']:
                    if var in self.analyzer.globals:
                        output.append(f"{self.indentation*2}{ast.unparse(self.analyzer.globals[var])}")
                        self.processed_variables.add(var)
                
                # 添加内部类函数
                ordered_funcs = self._get_ordered_functions(inner_def['functions'])
                for func in ordered_funcs:
                    if func in self.analyzer.functions and func not in self.processed_functions:
                        # 获取函数代码并修改调用方式
                        func_node = self.analyzer.functions[func]
                        modified_func = self._modify_function_calls(func_node, inner_class)
                        func_code = ast.unparse(modified_func)
                        func_code = "\n".join(f"{self.indentation*2}{line}" 
                                            for line in func_code.split("\n"))
                        output.append("")
                        output.append(func_code)
                        self.processed_functions.add(func)
                
            # 添加类方法
            ordered_funcs = self._get_ordered_functions(class_def['functions'])
            for func in ordered_funcs:
                if func in self.analyzer.functions and func not in self.processed_functions:
                    # 获取函数代码并修改调用方式
                    func_node = self.analyzer.functions[func]
                    modified_func = self._modify_function_calls(func_node, class_name)
                    func_code = ast.unparse(modified_func)
                    func_code = "\n".join(f"{self.indentation}{line}" 
                                        for line in func_code.split("\n"))
                    output.append("")
                    output.append(func_code)
                    self.processed_functions.add(func)
            
            output.append("")
        
        # 添加未分类的函数到统一的类中
        remaining_funcs = set(self.analyzer.functions.keys()) - self.processed_functions
        if remaining_funcs:
            output.append("class UnclassifiedFunctions:")
            output.append(f'{self.indentation}"""')
            output.append(f'{self.indentation}未分类的函数集合')
            output.append(f'{self.indentation}"""')
            output.append("")
            
            ordered_remaining = self._get_ordered_functions(remaining_funcs)
            for func in ordered_remaining:
                func_node = self.analyzer.functions[func]
                modified_func = self._modify_function_calls(func_node, "UnclassifiedFunctions")
                func_code = ast.unparse(modified_func)
                func_code = "\n".join(f"{self.indentation}{line}" 
                                    for line in func_code.split("\n"))
                output.append(func_code)
                output.append("")
        
        return "\n".join(output)
        
    def _get_ordered_functions(self, functions: Set[str]) -> List[str]:
        """根据调用关系对函数进行排序"""
        # 创建子图
        subgraph = self.analyzer.call_graph.subgraph(functions)
        try:
            # 尝试拓扑排序
            ordered = list(nx.topological_sort(subgraph))
            # 确保所有函数都在结果中
            for func in functions:
                if func not in ordered:
                    ordered.append(func)
            return ordered
        except nx.NetworkXUnfeasible:
            # 如果有循环依赖，使用原始顺序
            return sorted(functions)

    def _modify_function_calls(self, func_node: ast.FunctionDef, current_class: Optional[str]) -> ast.FunctionDef:
        """修改函数中的调用方式"""
        class FunctionCallTransformer(ast.NodeTransformer):
            def __init__(self, analyzer, current_class, structure):
                self.analyzer = analyzer
                self.current_class = current_class
                self.structure = structure
                
            def get_function_class(self, func_name):
                """获取函数所属的类"""
                # 1. 检查是否在结构定义中
                for class_name, class_def in self.structure.structure.items():
                    if func_name in class_def['functions']:
                        return class_name
                    for inner_class, inner_def in class_def['inner_classes'].items():
                        if func_name in inner_def['functions']:
                            return f"{class_name}.{inner_class}"
                # 2. 如果不在结构定义中，返回UnclassifiedFunctions
                return "UnclassifiedFunctions"
                
            def is_same_class_function(self, func_name):
                """检查函数是否属于同一个类"""
                # 检查当前类的函数列表
                if self.current_class in self.structure.structure:
                    class_def = self.structure.structure[self.current_class]
                    # 检查主类函数
                    if func_name in class_def['functions']:
                        return True
                    # 检查内部类函数
                    for inner_def in class_def['inner_classes'].values():
                        if func_name in inner_def['functions']:
                            return True
                return False
                
            def visit_FunctionDef(self, node):
                """处理函数定义，确保有self参数"""
                # 如果是类方法且没有self参数，添加self参数
                if self.current_class and (not node.args.args or node.args.args[0].arg != 'self'):
                    # 创建self参数
                    self_arg = ast.arg(arg='self', annotation=None)
                    # 在参数列表开头添加self
                    node.args.args.insert(0, self_arg)
                    print(f"为函数 {node.name} 添加self参数")
                
                # 继续处理函数体
                self.generic_visit(node)
                return node
                
            def visit_Call(self, node):
                # 递归处理所有子节点
                self.generic_visit(node)
                
                # 处理直接函数调用
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if func_name in self.analyzer.functions:
                        # 检查是否是同一个类中的函数
                        if self.is_same_class_function(func_name):
                            print(f"转换为self调用: {func_name} -> self.{func_name}")
                            return ast.Call(
                                func=ast.Attribute(
                                    value=ast.Name(id='self', ctx=ast.Load()),
                                    attr=func_name,
                                    ctx=ast.Load()
                                ),
                                args=node.args,
                                keywords=node.keywords
                            )
                        else:
                            # 其他类的函数调用
                            target_class = self.get_function_class(func_name)
                            print(f"转换为完整路径调用: {func_name} -> {target_class}.{func_name}")
                            return ast.Call(
                                func=ast.Attribute(
                                    value=ast.Name(id=target_class, ctx=ast.Load()),
                                    attr=func_name,
                                    ctx=ast.Load()
                                ),
                                args=node.args,
                                keywords=node.keywords
                            )
                
                # 处理属性调用 (obj.method())
                elif isinstance(node.func, ast.Attribute):
                    method_name = node.func.attr
                    if method_name in self.analyzer.functions:
                        # 如果是通过其他对象调用的方法
                        if isinstance(node.func.value, ast.Name):
                            obj_name = node.func.value.id
                            # 如果不是self调用，检查是否需要转换为类调用
                            if obj_name != 'self':
                                # 检查是否是同一个类中的函数
                                if self.is_same_class_function(method_name):
                                    print(f"转换为self调用: {obj_name}.{method_name} -> self.{method_name}")
                                    return ast.Call(
                                        func=ast.Attribute(
                                            value=ast.Name(id='self', ctx=ast.Load()),
                                            attr=method_name,
                                            ctx=ast.Load()
                                        ),
                                        args=node.args,
                                        keywords=node.keywords
                                    )
                                else:
                                    target_class = self.get_function_class(method_name)
                                    print(f"转换对象调用为类调用: {obj_name}.{method_name} -> {target_class}.{method_name}")
                                    return ast.Call(
                                        func=ast.Attribute(
                                            value=ast.Name(id=target_class, ctx=ast.Load()),
                                            attr=method_name,
                                            ctx=ast.Load()
                                        ),
                                        args=node.args,
                                        keywords=node.keywords
                                    )
                
                return node
                
        # 创建转换器并应用转换
        transformer = FunctionCallTransformer(self.analyzer, current_class, self.structure)
        modified_node = transformer.visit(func_node)
        ast.fix_missing_locations(modified_node)  # 修复AST节点位置信息
        return modified_node

def process_python_file(source_file: str, structure_file: str, output_file: str) -> None:
    """处理Python文件并生成重组后的代码"""
    try:
        # 解析目标结构 (使用YAML解析器)
        structure = StructureDefinition(structure_file)
        structure.parse_structure()
        
        # 分析源代码
        analyzer = CodeAnalyzer(source_file)
        analyzer.parse_file()
        
        # 重组代码
        restructurer = CodeRestructurer(analyzer, structure)
        restructured_code = restructurer.restructure()
        
        # 保存重组后的代码
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(restructured_code)
            
        print(f"代码重组完成，结果已保存到 {output_file}")
        
    except Exception as e:
        print(f"处理文件时出错: {e}")
        raise

if __name__ == "__main__":
    source_file = r"D:\1VSCODE\GlowToolBox\src\scripts\comic\manga_archive_classifier.py"  # 源文件
    structure_file = r"D:\1VSCODE\GlowToolBox\src\scripts\refactor\target_structure.yaml"  # 目标结构文件 (.yaml扩展名)
    output_file = r"D:\1VSCODE\GlowToolBox\src\scripts\refactor\restructured_code.py"  # 输出文件
    
    process_python_file(source_file, structure_file, output_file)
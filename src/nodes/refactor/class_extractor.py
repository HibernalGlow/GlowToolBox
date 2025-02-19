import os
import ast
from pathlib import Path

class ClassExtractor:
    def __init__(self, source_file, output_dir='extracted_classes'):
        self.source_file = source_file
        self.output_dir = output_dir
        self.imports = set()
        self.class_dependencies = {}
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    def analyze_source(self):
        """分析源代码文件，提取类和依赖关系"""
        with open(self.source_file, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())

        # 收集所有类定义
        self.classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]

        # 收集导入语句
        for node in tree.body:
            if isinstance(node, ast.Import):
                self.imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                self.imports.update(f"{module}.{alias.name}" for alias in node.names)

        # 分析类依赖
        for cls in self.classes:
            self._find_class_dependencies(cls)

    def _find_class_dependencies(self, class_node):
        """递归查找类的依赖关系"""
        dependencies = set()
        for node in ast.walk(class_node):
            if isinstance(node, ast.Name):
                if node.id in [c.name for c in self.classes]:
                    dependencies.add(node.id)
            elif isinstance(node, ast.Attribute):
                if node.attr in [c.name for c in self.classes]:
                    dependencies.add(node.attr)
        self.class_dependencies[class_node.name] = dependencies

    def extract_classes(self):
        """提取类到单独文件"""
        # 生成每个类的文件
        for cls in self.classes:
            self._generate_class_file(cls)

        # 生成 __init__.py
        self._generate_init_file()

    def _generate_class_file(self, class_node):
        """生成单个类文件"""
        filename = f"{class_node.name}.py"  # 完全保留原始类名
        output_path = os.path.join(self.output_dir, filename)

        # 收集需要的导入
        required_imports = self._get_required_imports(class_node)

        # 生成文件内容
        with open(output_path, 'w', encoding='utf-8') as f:
            # 写入导入语句
            f.write("# Auto-generated by ClassExtractor\n\n")
            for imp in sorted(required_imports):
                f.write(f"from . import {imp}\n" if imp in self.class_dependencies else f"import {imp}\n")
            f.write("\n")
            
            # 写入类代码
            f.write(ast.get_source_segment(
                open(self.source_file, 'r', encoding='utf-8').read(),
                class_node
            ))

    def _get_required_imports(self, class_node):
        """获取类需要的导入"""
        required = set()
        # 添加类依赖的其他类
        required.update(self.class_dependencies[class_node.name])
        # 添加外部依赖
        required.update(self.imports)
        return required - {class_node.name}

    def _generate_init_file(self):
        """生成 __init__.py"""
        init_path = os.path.join(self.output_dir, '__init__.py')
        with open(init_path, 'w', encoding='utf-8') as f:
            f.write("# Auto-generated init file\n\n")
            for cls in self.classes:
                f.write(f"from .{cls.name.lower()} import {cls.name}\n")

if __name__ == "__main__":
    # 使用示例（修改为实际路径）
    extractor = ClassExtractor(
        source_file='src/scripts/archive/011-去重复.py',
        output_dir='src\scripts\comic-img-flitter'
    )
    extractor.analyze_source()
    extractor.extract_classes()
    print("类提取完成！") 
# 代码重构工具

这个工具可以根据预先定义的YAML结构描述文件自动重构现有的Python代码。

## 使用方法

1. 创建一个YAML结构定义文件（参考`example_structure.yaml`）
2. 运行重构脚本：
   ```python
   python code_restructure.py
   ```

## 结构定义文件格式

YAML结构文件定义了代码重构的目标结构，格式如下：

```yaml
ClassName:
  description: 类的描述
  variables:
    - 变量名1
    - 变量名2
  functions:
    - 函数名1()
    - 函数名2()
  inner_classes:
    InnerClassName:
      description: 内部类描述
      variables:
        - 内部变量1
      functions:
        - 内部函数1()
```

## 功能说明

- 根据结构文件自动重组代码
- 智能分析函数调用关系
- 生成符合面向对象设计的类结构
- 保留原始注释和文档字符串
- 自动调整类方法调用（添加self等）

## 依赖

- Python 3.6+
- PyYAML
- NetworkX

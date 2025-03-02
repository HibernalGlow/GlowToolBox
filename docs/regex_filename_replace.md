# 使用正则表达式批量替换文件名中的模式

## 替换文件名中的 `_\d+` 模式（下划线后跟数字）

### 1. PowerShell 方法

```powershell
# 替换当前目录下所有文件名中的 _数字 部分
Get-ChildItem -File | ForEach-Object {
    $newName = $_.Name -replace '_\d+', ''
    if ($_.Name -ne $newName) {
        Rename-Item -Path $_.FullName -NewName $newName -Force
        Write-Host "已重命名: $($_.Name) -> $newName"
    }
}

# 如果需要递归处理子文件夹，添加 -Recurse 参数：
# Get-ChildItem -File -Recurse | ForEach-Object { ... }
```

### 2. Python 脚本

```python
import os
import re

def rename_files(directory, pattern='_\d+', replacement=''):
    """
    在指定目录中重命名文件，替换文件名中的正则表达式模式
    
    参数:
        directory (str): 要处理的目录路径
        pattern (str): 要替换的正则表达式模式
        replacement (str): 替换成的字符串
    """
    renamed_count = 0
    
    for filename in os.listdir(directory):
        if os.path.isfile(os.path.join(directory, filename)):
            new_name = re.sub(pattern, replacement, filename)
            if new_name != filename:
                try:
                    os.rename(
                        os.path.join(directory, filename),
                        os.path.join(directory, new_name)
                    )
                    print(f"已重命名: {filename} -> {new_name}")
                    renamed_count += 1
                except Exception as e:
                    print(f"重命名 {filename} 时出错: {e}")
    
    print(f"共重命名了 {renamed_count} 个文件")

# 使用示例
# rename_files('D:/YourFolder')
```

### 3. 批量重命名工具

#### 使用 Bulk Rename Utility

1. 下载并安装 [Bulk Rename Utility](https://www.bulkrenameutility.co.uk/)
2. 打开程序并浏览到包含文件的文件夹
3. 选择需要重命名的文件
4. 在"Regex"部分（10号面板）:
   - "Match"框中输入: `_\d+`
   - "Replace"框中留空（或根据需要填写替换内容）
5. 点击"Rename"按钮执行重命名

#### 使用 Advanced Renamer

1. 下载并安装 [Advanced Renamer](https://www.advancedrenamer.com/)
2. 添加包含要重命名文件的文件夹
3. 添加"Replace"方法
4. 选择"Regular expressions"选项
5. "Replace"字段中输入: `_\d+`
6. "With"字段留空（或根据需要填写）
7. 点击"Start Batch"执行重命名

### 4. Windows 命令行（使用 FOR 循环）

```batch
@echo off
setlocal enabledelayedexpansion

for %%F in (*) do (
    set "filename=%%F"
    set "newname=!filename!"
    
    for /f "tokens=1* delims=_" %%A in ("!filename!") do (
        set "first=%%A"
        set "rest=%%B"
        
        :: 检查第二部分是否为纯数字
        echo !rest! | findstr /r "^[0-9]*$" >nul
        if not errorlevel 1 (
            :: 如果是纯数字，则移除_数字部分
            set "newname=!first!"
        )
    )
    
    if not "!filename!" == "!newname!" (
        echo 重命名: !filename! -^> !newname!
        ren "!filename!" "!newname!"
    )
)

endlocal
```

### 5. Linux/Mac 终端（使用 find 和 rename）

```bash
# 对当前目录中的文件使用perl正则表达式进行重命名
# 安装rename工具（如果尚未安装）
# Debian/Ubuntu: sudo apt-get install rename
# CentOS/RHEL: sudo yum install prename

# 替换当前目录下的所有文件
rename 's/_\d+//' *

# 递归处理子目录中的所有文件
find . -type f -name "*_*" -exec rename 's/_\d+//' {} \;
```

## 注意事项

1. **备份重要数据**: 在执行批量重命名前，务必备份重要文件。
2. **测试少量文件**: 首先在少量文件上测试您的重命名模式。
3. **正则表达式变体**:
   - `_\d+` 匹配下划线后跟一个或多个数字
   - `_\d*` 匹配下划线后跟零个或多个数字
   - `_[0-9]+` 在某些工具中可替代 `_\d+`

## 高级用例

### 仅替换文件名中特定位置的模式

如果您只想替换文件名中特定位置的 `_\d+` 模式，可以使用更精确的正则表达式：

- 替换文件名末尾的数字: `_\d+(\.\w+)$` 替换为 `$1`
- 替换文件名开头的数字: `^([^_]*)_\d+` 替换为 `$1`

### 保留部分数字

如果您想保留部分格式但修改数字，例如将 `file_123.txt` 改为 `file_X.txt`：

```python
# Python 示例
new_name = re.sub(r'_\d+', '_X', filename)
```

### 使用捕获组保留文件扩展名

```powershell
# PowerShell 示例
$newName = $_.Name -replace '(_\d+)(\.\w+)$', '$2'
```

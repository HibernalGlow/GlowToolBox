# 从 Git 历史中删除文件

如果你需要从 Git 历史中完全删除这些文件，有两种主要方法：

## 方法 1：使用 BFG Repo-Cleaner（推荐）

BFG 是一个比 git filter-branch 更快的替代工具。

1. 下载 BFG: https://rtyley.github.io/bfg-repo-cleaner/
2. 运行以下命令：
   ```bash
   # 备份你的仓库
   git clone --mirror git://example.com/my-repo.git
   
   # 运行 BFG 删除文件
   java -jar bfg.jar --delete-files performance_config.json my-repo.git
   java -jar bfg.jar --delete-files archive_check_history.yaml my-repo.git
   java -jar bfg.jar --delete-files 1.md my-repo.git
   
   # 清理和更新仓库
   cd my-repo.git
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   git push
   ```

## 方法 2：使用 git filter-branch

```bash
# 警告：这可能非常慢，特别是对于大型仓库
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch src/nodes/config/performance_config.json src/scripts/folder/archive_check_history.yaml src/scripts/md/1.md" \
  --prune-empty --tag-name-filter cat -- --all

# 强制垃圾回收和推送
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push origin --force --all
```

## 注意事项

- 这些操作会重写历史记录，对共享仓库可能造成问题
- 所有协作者需要重新克隆或小心地处理他们的本地仓库
- 在执行之前，确保备份你的仓库

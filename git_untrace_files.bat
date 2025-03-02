@echo off
echo 正在从 Git 追踪中移除指定文件...

git rm --cached src/nodes/config/performance_config.json
git rm --cached src/scripts/folder/archive_check_history.yaml
git rm --cached src/scripts/md/1.md

echo 变更已准备好，请执行提交：
echo git commit -m "停止追踪特定文件"
echo.
echo 如果需要从 Git 历史中彻底删除这些文件，请考虑使用 BFG Repo-Cleaner 或 git filter-branch

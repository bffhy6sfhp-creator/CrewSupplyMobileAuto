@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
echo 仅修复“页面一直显示 running，但实际没有任务”的状态。
python -c "import json; from mobile_server import reconcile_stale_status; print(json.dumps(reconcile_stale_status(), ensure_ascii=False, indent=2))"
pause

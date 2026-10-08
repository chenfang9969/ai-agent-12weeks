@echo off
chcp 65001 >nul
cd /d "D:\DeepSeekHarness\12周计划"
python progress.py --check
echo.
echo (按任意键关闭)
pause >nul

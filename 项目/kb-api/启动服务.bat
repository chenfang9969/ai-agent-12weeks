@echo off
chcp 65001 >nul
title 企业知识库助手 · kb-api :8100
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

echo ============================================================
echo   企业知识库助手 · 聊天窗入口
echo   启动后浏览器打开:  http://127.0.0.1:8100/
echo   接口文档:          http://127.0.0.1:8100/docs
echo   关闭本窗口 = 停止服务
echo ============================================================
echo.

python server.py
echo.
echo [服务已退出] 退出码: %ERRORLEVEL%
echo 常见原因: 8100 端口被占用（先关掉旧窗口）或 没装 fastapi/uvicorn
pause

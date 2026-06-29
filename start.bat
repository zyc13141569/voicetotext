@echo off
chcp 65001 >nul
REM 语音记笔记 - 一键启动网页版
cd /d "%~dp0"

REM 若存在虚拟环境则优先使用
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

echo 正在启动语音记笔记网页版...
REM 稍后自动打开浏览器(端口默认 8000, 如改了 WEB_PORT 请同步修改下行)
start "" /min cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8000"

%PY% -m web.server

echo.
echo 服务已停止。按任意键关闭窗口。
pause >nul

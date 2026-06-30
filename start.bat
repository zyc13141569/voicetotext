@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   语音记笔记 - 启动器
echo   首次运行会自动检查环境并安装依赖
echo ============================================
echo.

REM ---------- 1. 检查 Python ----------
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto :no_python

%PY% -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)" 2>nul
if errorlevel 1 goto :bad_version

REM ---------- 2. 创建虚拟环境 ----------
if exist ".venv\Scripts\python.exe" goto :have_venv
echo [1/4] 正在创建虚拟环境 .venv ...
%PY% -m venv .venv
if errorlevel 1 goto :venv_fail
goto :venv_done
:have_venv
echo [1/4] 虚拟环境已存在。
:venv_done
set "VENV_PY=.venv\Scripts\python.exe"

REM ---------- 3. 安装/更新依赖 ----------
REM 与上次安装时的快照对比 requirements.txt, 内容变了才重装
set "NEED=0"
if not exist ".venv\.deps.txt" set "NEED=1"
if "!NEED!"=="0" fc /b "requirements.txt" ".venv\.deps.txt" >nul 2>nul || set "NEED=1"
if "!NEED!"=="1" goto :install
echo [2/4] 依赖已是最新，跳过安装。
goto :deps_done
:install
echo [2/4] 正在安装依赖，首次或有更新时可能需要几分钟...
"%VENV_PY%" -m pip install --upgrade pip
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :pip_fail
copy /y "requirements.txt" ".venv\.deps.txt" >nul
:deps_done

REM ---------- 4. 准备配置文件 ----------
if exist ".env" goto :env_exists
if not exist ".env.example" goto :env_done
copy /y ".env.example" ".env" >nul
echo [3/4] 已生成配置文件 .env，可启动后在网页右上角齿轮里填 API Key。
goto :env_done
:env_exists
echo [3/4] 配置文件 .env 已存在。
:env_done

REM ---------- 5. 启动服务 ----------
echo [4/4] 正在启动服务: http://127.0.0.1:8000
echo.
echo   关闭此窗口即可停止服务。
echo ============================================
echo.
set "VTT_OPEN_BROWSER=1"
"%VENV_PY%" -m web.server
goto :stopped

:no_python
echo.
echo [错误] 未检测到 Python。请先安装 Python 3.11 或更高版本:
echo     https://www.python.org/downloads/
echo 安装时务必勾选 "Add Python to PATH"，装好后重新双击本文件。
goto :hold

:bad_version
echo.
echo [错误] Python 版本过低，需要 3.9 及以上。请升级:
echo     https://www.python.org/downloads/
goto :hold

:venv_fail
echo.
echo [错误] 创建虚拟环境失败。
goto :hold

:pip_fail
echo.
echo [错误] 依赖安装失败，请检查网络后重试。
goto :hold

:hold
echo.
pause
exit /b 1

:stopped
echo.
echo 服务已停止。按任意键关闭窗口。
pause >nul

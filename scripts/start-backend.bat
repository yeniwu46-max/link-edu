@echo off
chcp 65001 >nul
cd /d "%~dp0..\backend"
if errorlevel 1 (
  echo 无法进入 backend 目录。
  pause
  exit /b 1
)

set "VENV_DIR=.venv"
if exist "%VENV_DIR%\Scripts\python.exe" (
  "%VENV_DIR%\Scripts\python.exe" -V >nul 2>&1
  if errorlevel 1 set "VENV_DIR=.venv-local"
)
if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo 正在创建 Python 虚拟环境...
  python -m venv "%VENV_DIR%"
)
"%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt -q
if errorlevel 1 (
  echo 后端依赖安装失败，请检查 Python 和网络。
  pause
  exit /b 1
)
if not exist .env (
  copy .env.example .env >nul
  echo 已根据 .env.example 生成 backend\.env
)
echo 正在初始化数据库...
"%VENV_DIR%\Scripts\python.exe" init_db.py
if errorlevel 1 (
  echo 数据库初始化失败，请检查 backend\.env 中的 DATABASE_URL。
  pause
  exit /b 1
)
echo 启动后端: http://127.0.0.1:5000
"%VENV_DIR%\Scripts\python.exe" app.py
pause

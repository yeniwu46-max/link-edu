@echo off
chcp 65001 >nul
cd /d "%~dp0..\frontend"
if errorlevel 1 (
  echo 无法进入 frontend 目录。
  pause
  exit /b 1
)
if not exist node_modules (
  echo 正在安装前端依赖...
  call npm install
  if errorlevel 1 (
    echo 前端依赖安装失败，请检查 Node.js 和网络。
    pause
    exit /b 1
  )
)
echo 启动前端: http://127.0.0.1:5188
call npm run dev -- --open
pause

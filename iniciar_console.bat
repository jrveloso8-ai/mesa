@echo off
setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
title Mesa de Operacoes B3 - Modo Console Puro

echo ====================================================================
echo        INICIANDO MESA DE OPERACOES B3 (MODO CONSOLE RICH)
echo ====================================================================
echo.

cd /d "%~dp0"

set "PYTHON_EXE=python"
if exist "C:\Users\Acer\AppData\Local\Programs\Python\Python313\python.exe" (
    set "PYTHON_EXE=C:\Users\Acer\AppData\Local\Programs\Python\Python313\python.exe"
)

"%PYTHON_EXE%" --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao foi encontrado no sistema!
    pause
    exit /b 1
)

"%PYTHON_EXE%" main.py


echo.
echo ====================================================================
echo   Execucao finalizada. Pressione qualquer tecla para fechar.
echo ====================================================================
pause
endlocal

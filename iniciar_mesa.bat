@echo off
setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
title Mesa de Operacoes B3 - Dashboard Visual Interativo

echo ====================================================================
echo        INICIANDO MESA DE OPERACOES B3 (PAINEL VISUAL INTERATIVO)
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
    echo Certifique-se de ter o Python 3.10 ou superior instalado.
    echo.
    pause
    exit /b 1
)

echo Iniciando servidor Uvicorn / FastAPI...
echo O navegador abrira automaticamente em: http://localhost:8000
echo.

"%PYTHON_EXE%" server.py


echo.
echo ====================================================================
echo   Servidor finalizado. Pressione qualquer tecla para fechar.
echo ====================================================================
pause
endlocal


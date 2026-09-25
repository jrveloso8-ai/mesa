@echo off
chcp 65001 >nul
title Atualizar Repositório GitHub - Mesa de Operações B3
color 0B

echo ========================================================
echo    MESA DE OPERAÇÕES B3 - SINCRONIZAÇÃO GITHUB
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/4] Verificando status dos arquivos modificados...
git status -s
echo.

set /p MSG_COMMIT="Digite a mensagem do commit (ou ENTER para automtica): "

if "%MSG_COMMIT%"=="" (
    for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
    set MSG_COMMIT=update: Atualizacao automatica da mesa em %date% as %time:~0,5%
)

echo.
echo [2/4] Adicionando arquivos modificados (git add .)...
git add .

echo.
echo [3/4] Gravando commit: "%MSG_COMMIT%"...
git commit -m "%MSG_COMMIT%"

echo.
echo [4/4] Enviando alteracoes para o GitHub (git push origin main)...
git push origin main

if %ERRORLEVEL% equ 0 (
    echo.
    echo ========================================================
    echo  [SUCESSO] Repositório GitHub atualizado com sucesso!
    echo  https://github.com/jrveloso8-ai/mesa
    echo ========================================================
) else (
    echo.
    echo ========================================================
    echo  [AVISO] Ocorreu uma falha ao enviar para o GitHub.
    echo  Verifique sua conexao ou permissoes de acesso.
    echo ========================================================
)

echo.
pause

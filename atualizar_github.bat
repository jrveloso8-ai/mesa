@echo off
setlocal
title Atualizar Repositorio GitHub - Mesa de Operacoes B3

echo ====================================================================
echo        MESA DE OPERACOES B3 - SINCRONIZACAO COM O GITHUB
echo ====================================================================
echo.

cd /d "%~dp0"

echo [1/4] Verificando status dos arquivos modificados...
git status -s
echo.

set "MSG_COMMIT=update: Sincronizacao automatica da mesa"
set "INPUT_COMMIT="
set /p INPUT_COMMIT=Digite a mensagem do commit ou pressione ENTER para automatica: 

if defined INPUT_COMMIT (
    set "MSG_COMMIT=%INPUT_COMMIT%"
)

echo.
echo [2/4] Adicionando arquivos modificados: git add .
git add .

echo.
echo [3/4] Gravando commit: %MSG_COMMIT%
git commit -m "%MSG_COMMIT%"

echo.
echo [4/4] Enviando alteracoes para o GitHub: git push origin main
git push origin main

if errorlevel 1 (
    echo.
    echo ====================================================================
    echo  [AVISO] Ocorreu uma falha ao enviar para o GitHub.
    echo  Verifique sua conexao ou permissoes de acesso.
    echo ====================================================================
) else (
    echo.
    echo ====================================================================
    echo  [SUCESSO] Repositorio GitHub atualizado com sucesso!
    echo  https://github.com/jrveloso8-ai/mesa
    echo ====================================================================
)

echo.
pause
endlocal

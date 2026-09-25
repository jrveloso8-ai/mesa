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

set "MSG_COMMIT="
set /p "MSG_COMMIT=Digite a mensagem do commit ou pressione ENTER para automatica: "

if not defined MSG_COMMIT (
    set "MSG_COMMIT=update: Sincronizacao automatica da mesa"
)

echo.
echo [2/4] Adicionando arquivos modificados: git add .
git add .

echo.
echo [3/4] Gravando commit: %MSG_COMMIT%
git commit -m "%MSG_COMMIT%"

echo.
echo.
echo [4/5] Enviando alteracoes para o GitHub: git push origin main
git push origin main

echo.
echo [5/5] Atualizando producao no Vercel: vercel --prod --yes
call vercel --prod --yes

if errorlevel 1 (
    echo.
    echo ====================================================================
    echo  [AVISO] Verifique a publicacao manual no Vercel.
    echo ====================================================================
) else (
    echo.
    echo ====================================================================
    echo  [SUCESSO] GitHub e Vercel atualizados com sucesso!
    echo  GitHub: https://github.com/jrveloso8-ai/mesa
    echo  Vercel: https://mesa-ochre.vercel.app
    echo ====================================================================
)

echo.
pause
endlocal

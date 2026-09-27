@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title Atualizar Repositorio GitHub - Mesa de Operacoes B3

echo ====================================================================
echo        MESA DE OPERACOES B3 - SINCRONIZACAO COM O GITHUB
echo ====================================================================
echo.

cd /d "%~dp0"

echo [Portão 1/3] Executando suite de testes pytest...
python -m pytest --tb=short -q
if errorlevel 1 (
    echo.
    echo ====================================================================
    echo [ERRO - ABORTADO] A suite de testes falhou!
    echo Corrija as falhas nos testes antes de tentar sincronizar o repositorio.
    echo ====================================================================
    pause
    exit /b 1
)
echo [OK] Testes passaram com sucesso.
echo.

echo [Portão 2/3] Verificando vazamento de credenciais via scripts/varrer_segredos.py...
git diff --name-only HEAD | python scripts/varrer_segredos.py
if errorlevel 1 (
    echo.
    echo ====================================================================
    echo [ERRO - ABORTADO] Possivel vazamento de credenciais detectado nos arquivos modificados!
    echo Remova as credenciais antes de prosseguir.
    echo ====================================================================
    pause
    exit /b 1
)

git ls-files --others --exclude-standard | python scripts/varrer_segredos.py
if errorlevel 1 (
    echo.
    echo ====================================================================
    echo [ERRO - ABORTADO] Possivel vazamento de credenciais detectado nos arquivos novos!
    echo Remova as credenciais antes de prosseguir.
    echo ====================================================================
    pause
    exit /b 1
)

git rev-parse --verify origin/main >nul 2>&1
if errorlevel 1 (
    git ls-files | python scripts/varrer_segredos.py
) else (
    git diff --name-only origin/main..HEAD | python scripts/varrer_segredos.py
)
if errorlevel 1 (
    echo.
    echo ====================================================================
    echo [ERRO - ABORTADO] Possivel vazamento de credenciais detectado nos commits nao publicados!
    echo Remova as credenciais antes de prosseguir.
    echo ====================================================================
    pause
    exit /b 1
)
echo [OK] Nenhuma credencial exposta encontrada.
echo.

echo [Portão 3/3] Verificando arquivos proibidos no status do git...
for /f "tokens=*" %%A in ('git status --porcelain') do (
    set "LINE=%%A"
    for %%P in (04_auditoria 05_correcao 03_entrega .zip .log entrega/) do (
        echo !LINE! | findstr /i "%%P" >nul 2>&1
        if !errorlevel! equ 0 (
            echo.
            echo ====================================================================
            echo [ERRO - ABORTADO] Arquivo proibido detectado no git status: !LINE!
            echo Padrao proibido correspondente: %%P
            echo Adicione o arquivo ao .gitignore ou remova-o do repositorio antes de commitar.
            echo ====================================================================
            pause
            exit /b 1
        )
    )
)
echo [OK] Nenhum arquivo proibido detectado.
echo.

echo ====================================================================
echo Resumo dos arquivos modificados e novos para inclusao:
echo ====================================================================
git status -s
echo.

set "CONFIRM_PUB="
set /p "CONFIRM_PUB=Para confirmar a publicacao e prosseguir com o git add, digite PUBLICAR: "
if not "!CONFIRM_PUB!"=="PUBLICAR" (
    echo.
    echo ====================================================================
    echo [ABORTADO] Publicacao cancelada pelo usuario. Nenhuma alteracao foi commitada.
    echo ====================================================================
    pause
    exit /b 0
)
echo [OK] Confirmacao recebida.
echo.

set "MSG_COMMIT="
set /p "MSG_COMMIT=Digite a mensagem do commit ou pressione ENTER para automatica: "

if not defined MSG_COMMIT (
    set "MSG_COMMIT=update: Sincronizacao automatica da mesa"
)

echo.
echo Adicionando arquivos modificados: git add .
git add .

echo.
echo Gravando commit: %MSG_COMMIT%
git commit -m "%MSG_COMMIT%"

echo.
echo Enviando alteracoes para o GitHub: git push origin main
git push origin main

echo.
echo Atualizando producao no Vercel: vercel --prod --yes
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

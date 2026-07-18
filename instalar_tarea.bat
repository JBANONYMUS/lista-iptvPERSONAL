@echo off
chcp 65001 >nul
echo ==========================================
echo INSTALANDO TAREA - Teleantillas Updater
echo ==========================================
echo.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo EJECUTA COMO ADMINISTRADOR
    pause
    exit /b 1
)

set "SCRIPT=%~dp0teleantillas_updater.py"
set "PY=python"

%PY% --version >nul 2>&1 || set "PY=py"
%PY% --version >nul 2>&1 || (
    echo Instala Python primero
    pause
    exit /b 1
)

echo Creando tarea programada...

schtasks /create /tn "TeleantillasUpdater" /tr "\"%PY%\" \"%SCRIPT%\"" /sc minute /mo 30 /rl HIGHEST /f /np

if %errorLevel% equ 0 (
    echo.
    echo ==========================================
    echo INSTALADO - Cada 30 minutos
    echo ==========================================
    echo Probando ahora...
    cd /d "%~dp0"
    %PY% "%SCRIPT%"
) else (
    echo Error creando tarea
)

pause
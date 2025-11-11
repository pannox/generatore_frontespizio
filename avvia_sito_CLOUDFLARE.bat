@echo off
title Generatore Frontespizio - Server Flask + Cloudflare Tunnel
echo ========================================
echo   GENERATORE FRONTESPIZIO - CLOUDFLARE TUNNEL
echo ========================================
echo.

REM Verifica se cloudflared esiste
where cloudflared >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ATTENZIONE: cloudflared non trovato!
    echo.
    echo ========================================
    echo   INSTALLAZIONE CLOUDFLARED
    echo ========================================
    echo.
    echo Cloudflare Tunnel e' GRATUITO e senza limiti di banda.
    echo NO REGISTRAZIONE - NO CHIAVI API - NO LIMITI
    echo.
    echo ========================================
    echo   DOWNLOAD AUTOMATICO
    echo ========================================
    echo.
    echo Scarico cloudflared nella cartella del progetto...
    echo.

    REM Crea cartella cloudflared se non esiste
    if not exist "cloudflared" mkdir cloudflared

    REM Download del file usando PowerShell
    echo Download in corso...
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile 'cloudflared\cloudflared.exe'}"

    if exist "cloudflared\cloudflared.exe" (
        echo.
        echo ========================================
        echo   DOWNLOAD COMPLETATO!
        echo ========================================
        echo.
        echo cloudflared installato in: cloudflared\cloudflared.exe
        echo.
        echo Premi un tasto per avviare il tunnel...
        pause >nul
    ) else (
        echo.
        echo ========================================
        echo   ERRORE DOWNLOAD
        echo ========================================
        echo.
        echo Download automatico fallito.
        echo.
        echo SCARICA MANUALMENTE:
        echo   1. Vai su: https://github.com/cloudflare/cloudflared/releases
        echo   2. Scarica: cloudflared-windows-amd64.exe
        echo   3. Rinominalo in: cloudflared.exe
        echo   4. Mettilo nella cartella: cloudflared\
        echo.
        echo Poi riavvia questo script.
        echo.
        pause
        exit /b 1
    )
)

REM Imposta il percorso di cloudflared
if exist "cloudflared\cloudflared.exe" (
    set CLOUDFLARED_PATH=cloudflared\cloudflared.exe
) else (
    set CLOUDFLARED_PATH=cloudflared
)

echo Verifica e installazione dipendenze Python...
echo.
python -m pip install --quiet Flask reportlab Werkzeug pypdf pdfrw

echo.
echo Terminazione processi precedenti...
taskkill /F /IM python.exe 2>nul
taskkill /F /IM cloudflared.exe 2>nul

echo.
echo ========================================
echo   AVVIO SERVIZI
echo ========================================
echo.

REM Avvia Flask in background
echo Avvio server Flask su porta 5000...
start /B python app.py

REM Attendi che Flask si avvii
timeout /t 3 /nobreak >nul

echo.
echo Avvio tunnel Cloudflare...
echo.
echo ========================================
echo   CLOUDFLARE TUNNEL ATTIVO
echo ========================================
echo.
echo Il tuo sito sara' accessibile tramite un URL pubblico gratuito!
echo.
echo VANTAGGI CLOUDFLARE TUNNEL:
echo  - Completamente GRATUITO
echo  - Nessun limite di banda
echo  - URL piu' professionale (*.trycloudflare.com)
echo  - Nessuna registrazione richiesta per test
echo.
echo L'URL pubblico apparira' qui sotto:
echo ========================================
echo.

REM Avvia cloudflared in modalità quick tunnel (questo bloccherà il terminale)
%CLOUDFLARED_PATH% tunnel --url http://localhost:5000

echo.
echo Tunnel Cloudflare terminato.
pause

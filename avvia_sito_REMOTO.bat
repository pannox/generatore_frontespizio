@echo off
title Generatore Frontespizio - Server Flask + ngrok
echo ========================================
echo   GENERATORE FRONTESPIZIO - ACCESSO REMOTO
echo ========================================
echo.

REM Verifica se ngrok esiste
if not exist "ngrok\ngrok.exe" (
    echo ERRORE: ngrok non trovato!
    echo.
    echo Esegui prima 'installa_ngrok.bat' per installare ngrok
    echo.
    pause
    exit /b 1
)

echo Verifica e installazione dipendenze Python...
echo.
python -m pip install --quiet Flask reportlab Werkzeug pypdf pdfrw

echo.
echo Terminazione processi precedenti...
taskkill /F /IM python.exe 2>nul
taskkill /F /IM ngrok.exe 2>nul

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
echo Avvio tunnel ngrok...
echo.
echo ========================================
echo   TUNNEL NGROK ATTIVO
echo ========================================
echo.
echo Il tuo sito è ora accessibile da remoto!
echo.
echo Apri il browser e vai su: http://localhost:4040
echo per vedere l'URL pubblico generato da ngrok
echo.
echo ========================================

REM Avvia ngrok (questo bloccherà il terminale)
ngrok\ngrok.exe http 5000

echo.
echo Tunnel ngrok terminato.
pause

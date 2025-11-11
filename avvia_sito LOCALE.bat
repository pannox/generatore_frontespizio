@echo off
title Generatore Frontespizio - Server Flask
echo ========================================
echo   GENERATORE FRONTESPIZIO - FLOTTE TRENI
echo ========================================
echo.
echo Verifica e installazione dipendenze...
echo.

python -m pip install --quiet Flask reportlab Werkzeug pypdf pdfrw

echo.
taskkill /F /IM python.exe
echo Avvio del server in corso...
echo.

python app.py

pause

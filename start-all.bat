
@echo off
:: Chemin du projet = dossier contenant ce fichier .bat
set SPARKY_DIR=%~dp0
echo ================================================
echo   SPARKY - Demarrage complet
echo   Dossier : %SPARKY_DIR%
echo ================================================

echo.
echo [1/3] Demarrage Backend (port 8000)...
start "SPARKY Backend" cmd /k "cd /d "%SPARKY_DIR%backend" && call venv\Scripts\activate.bat && uvicorn main:app --reload --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak > nul

echo [2/3] Demarrage Frontend (port 4200)...
start "SPARKY Frontend" cmd /k "cd /d "%SPARKY_DIR%frontend" && npm start"

timeout /t 2 /nobreak > nul

echo [3/3] Demarrage n8n (port 5678)...
start "SPARKY n8n" cmd /k "n8n start"

echo.
echo ================================================
echo   Tout est lance !
echo   Backend  : http://localhost:8000
echo   Frontend : http://localhost:4200
echo   n8n      : http://localhost:5678
echo ================================================
echo.
pause

@echo off
REM setup_windows.bat — grok-x-farm on Windows (no Docker)
REM Requirements: Go 1.22+, Python 3.12+ (uv recommended), curl
setlocal
set INSTALL_DIR=%~dp0..
set G2A=%INSTALL_DIR%\gateway\grok2api

echo [1/4] Downloading grok2api source...
if not exist "%G2A%" (
  curl -sL -o "%TEMP%\g2a.zip" https://codeload.github.com/chenyme/grok2api/zip/refs/heads/main
  powershell -NoProfile -Command "Expand-Archive -Force '%TEMP%\g2a.zip' '%TEMP%\g2a_x'; Move-Item '%TEMP%\g2a_x\grok2api-main' '%G2A%'"
)

echo [2/4] Generating config + secrets...
cd /d "%G2A%"
if not exist config.yaml copy config.example.yaml config.yaml
powershell -NoProfile -ExecutionPolicy Bypass -File "%INSTALL_DIR%\gateway\gen_secrets.ps1" -Config "%G2A%\config.yaml" -SecretsOut "%INSTALL_DIR%\SECRETS.local.txt"

echo [3/4] Building gateway (5-10 min first time)...
cd backend
go build -o ..\grok2api.exe .\cmd\grok2api
if errorlevel 1 ( echo BUILD FAILED & exit /b 1 )
cd ..

echo [4/4] Starting gateway on 127.0.0.1:8000 ...
start "grok2api" /B grok2api.exe --config "%G2A%\config.yaml" > gateway.log 2>&1
timeout /t 8 /nobreak > nul
curl -s -o nul -w "healthz:%%{http_code}\n" http://127.0.0.1:8000/healthz
echo.
echo [+] Done. Admin password in %INSTALL_DIR%\SECRETS.local.txt
echo [+] Next: cd autoreg tooling, then: python farm.py doctor
endlocal

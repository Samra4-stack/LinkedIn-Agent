@echo off
echo ==============================================
echo       Starting LinkedIn AI Agent...
echo ==============================================
echo.

echo [1/2] Starting FastAPI Server on port 8000...
start cmd /k "cd /d %~dp0 && call venv\Scripts\activate && uvicorn app.main:app --reload"

echo [2/2] Starting public tunnel (localtunnel)...
start cmd /k "cd /d %~dp0 && npx localtunnel --port 8000 --subdomain linkedin-agent-samra"

echo.
echo ==============================================
echo  Agent is running in the background windows!
echo  URL: https://linkedin-agent-samra.loca.lt
echo ==============================================
echo You can safely close this initial window.
timeout /t 5 > nul

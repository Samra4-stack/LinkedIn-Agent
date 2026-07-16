@echo off
:: ============================================
:: LinkedIn AI Agent — Silent Auto-Starter
:: Starts FastAPI server + Localtunnel quietly
:: ============================================

cd /d "%~dp0"

:: Start FastAPI server (minimized)
start /min "LinkedIn-Agent-Server" cmd /c "call venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8000"

:: Wait 5 seconds for server to boot before starting tunnel
timeout /t 5 /nobreak > nul

:: Start localtunnel (minimized)
start /min "LinkedIn-Agent-Tunnel" cmd /c "npx localtunnel --port 8000 --subdomain linkedin-agent-samra"

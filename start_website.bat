@echo off
cd /d %~dp0
set PATH=%PATH%;"C:\Program Files (x86)\cloudflared"
echo Starting Judgemental Padosi Aunty website...
echo.
start "Aunty Server" /D "%~dp0" python -m uvicorn server:app --port 8000
timeout /t 4 >nul
start "Cloudflare Tunnel" cloudflared tunnel --url http://localhost:8000
echo.
echo Both windows started.
echo - The "Aunty Server" window runs the backend on http://localhost:8000
echo - Check the "Cloudflare Tunnel" window for the https://....trycloudflare.com address
echo - The public link is temporary: it changes each run and stops when the tunnel stops
echo - Make sure .env contains your OPENROUTER_API_KEY before starting

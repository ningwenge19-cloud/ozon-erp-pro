@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating local Python environment...
  python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
cd backend
"..\.venv\Scripts\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8899

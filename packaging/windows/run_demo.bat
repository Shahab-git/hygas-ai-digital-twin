@echo off
rem HYGAS-AI Digital Twin - local demo. No database, no keys, no network needed once the packages are installed.
rem First start: creates a private Python environment in .venv and installs the packages (offline from the "wheels" folder when it exists).
setlocal
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto :nopython

if exist ".venv\Scripts\python.exe" goto :run
echo Creating the Python environment (first start only)...
%PY% -m venv .venv
if errorlevel 1 goto :fail
if exist "wheels" (
  ".venv\Scripts\python.exe" -m pip install --no-index --find-links wheels -r requirements.txt
) else (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
if errorlevel 1 goto :fail

:run
rem The demo never writes to any database, and tells the app it has none.
set "HYGAS_ALLOW_DB_WRITES=0"
set "HYGAS_LOCAL_DEMO=1"
echo Starting the demo. A browser tab opens at http://localhost:8501 - close this window to stop it.
".venv\Scripts\python.exe" -m streamlit run app.py --server.headless false --browser.gatherUsageStats false
goto :end

:nopython
echo Python 3 was not found. Install Python 3.11 or newer from python.org (tick "Add python.exe to PATH"), then start this file again.
goto :end

:fail
echo The installation failed. See the messages above. The "wheels" folder (if present) only fits the Python version named at the end of README_DEMO.txt; otherwise delete it to install from the internet.

:end
pause

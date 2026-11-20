@echo off
rem HYGAS-AI Digital Twin - local demo. No database, no keys, no network needed once the packages are installed.
rem First start: creates a private Python environment in .venv and installs the packages (offline from the "wheels" folder when it exists).
setlocal
cd /d "%~dp0"

rem Some machines have a damaged PATH (no Windows folder in it), so nothing here relies on a clean PATH.
set "PATH=%SystemRoot%\System32;%SystemRoot%;%PATH%"

set "PY="
set "CAND=py -3"
call :try
if not defined PY set "CAND=python"
if not defined PY call :try
if not defined PY for /d %%D in ("%LocalAppData%\Programs\Python\Python3*" "%ProgramFiles%\Python3*") do if not defined PY if exist "%%~D\python.exe" (
  set CAND="%%~D\python.exe"
  call :try
)
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

:try
rem Accept a candidate only if it really runs Python 3.11 or newer (the Microsoft Store stub does not).
%CAND% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=%CAND%"
exit /b 0

:nopython
echo Python 3.11 or newer was not found. Install it from python.org (tick "Add python.exe to PATH"), then start this file again.
goto :end

:fail
echo The installation failed. See the messages above. The "wheels" folder (if present) only fits the Python version named at the end of README_DEMO.txt; otherwise delete it to install from the internet.

:end
pause

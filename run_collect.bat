@echo off
rem Lab Atlas - stage 2 data collection (Windows). Double-click or run from cmd.
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if not exist pipeline\output mkdir pipeline\output
set LOG=pipeline\output\run_log.txt
del /q pipeline\output\run_done.txt 2>nul
echo [%date% %time%] start > %LOG%

if exist .venv\Scripts\python.exe goto :haveenv
set PY=
py -3 --version >nul 2>&1 && set PY=py -3
if not defined PY python --version >nul 2>&1 && set PY=python
if not defined PY (
  echo ERROR: Python 3 not found. Install from https://www.python.org/downloads/ >> %LOG%
  echo NOPYTHON > pipeline\output\run_done.txt
  exit /b 1
)
%PY% --version >> %LOG% 2>&1
%PY% -m venv .venv >> %LOG% 2>&1
if errorlevel 1 (
  echo ERROR: venv creation failed >> %LOG%
  echo VENVFAIL > pipeline\output\run_done.txt
  exit /b 1
)
:haveenv
echo --- pip install >> %LOG%
.venv\Scripts\python.exe -m pip install --disable-pip-version-check -q -r pipeline\requirements.txt >> %LOG% 2>&1
echo --- tests >> %LOG%
.venv\Scripts\python.exe -m pytest -q pipeline\tests >> %LOG% 2>&1
echo --- pipeline >> %LOG%
.venv\Scripts\python.exe -m pipeline.run --stage collect %* >> %LOG% 2>&1
echo EXIT %errorlevel% > pipeline\output\run_done.txt
echo [%date% %time%] end >> %LOG%

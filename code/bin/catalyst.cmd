@echo off
set "REPO=C:\Users\Lenovo\OneDrive\Desktop\codexu\catalyst"
set "VENV_PY=%REPO%\.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
  "%VENV_PY%" "%REPO%\scripts\catalyst.py" %*
) else (
  python "%REPO%\scripts\catalyst.py" %*
)

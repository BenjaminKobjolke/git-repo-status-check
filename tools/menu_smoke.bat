@echo off
pushd "%~dp0.."
uv run python tools/menu_smoke.py
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%

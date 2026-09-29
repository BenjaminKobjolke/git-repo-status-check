@echo off
uv run pytest tests/integration -v
exit /b %ERRORLEVEL%

@echo off
uv run pytest tests/unit -v
exit /b %ERRORLEVEL%

@echo off
where uv >nul 2>nul
if errorlevel 1 (
    echo uv is not installed. See https://docs.astral.sh/uv/
    exit /b 1
)
uv sync --all-extras
uv run pytest tests/unit -v

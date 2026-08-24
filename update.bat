@echo off
uv lock --upgrade
uv sync --all-extras
uv run ruff check .
uv run ruff format --check .
uv run mypy src main.py
uv run pytest tests/unit -v

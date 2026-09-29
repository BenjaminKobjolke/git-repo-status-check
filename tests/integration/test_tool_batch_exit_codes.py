"""Check that tool batch wrappers propagate child process failures."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(os.name != "nt", reason="Windows batch files require cmd")
@pytest.mark.parametrize(
    "batch_name",
    [
        "analyze_code.bat",
        "analyze_changed_and_new_files.bat",
        "fix_ruff_issues.bat",
        "fix_ruff_issues_dry_run.bat",
    ],
)
def test_tool_batch_returns_child_failure(tmp_path: Path, batch_name: str) -> None:
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    source = Path(__file__).resolve().parents[2] / "tools" / batch_name
    shutil.copy2(source, tools_dir / batch_name)
    missing_analyzer = tmp_path / "missing-analyzer"
    (tools_dir / "analyze_code_config.bat").write_text(
        f'@echo off\nset "CLI_ANALYZER_PATH={missing_analyzer}"\nset "LANGUAGE=python"\n'
    )

    result = subprocess.run(
        ["cmd", "/c", str(tools_dir / batch_name)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode != 0, result.stdout + result.stderr

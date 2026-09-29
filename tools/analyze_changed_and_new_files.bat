@echo off
if not exist "%~dp0analyze_code_config.bat" (
    echo ERROR: analyze_code_config.bat not found.
    echo Copy analyze_code_config.example.bat to analyze_code_config.bat and set your CLI_ANALYZER_PATH and LANGUAGE.
    exit /b 1
)
call "%~dp0analyze_code_config.bat"
cd /d "%~dp0.."

set "NOIN="
if "%TICKETS_WATCHER_COMMAND_RUN%"=="1" set "NOIN=<NUL"
"%CLI_ANALYZER_PATH%\venv\Scripts\python.exe" "%CLI_ANALYZER_PATH%\main.py" --language %LANGUAGE% --path "." --only-changed --verbosity minimal --output "code_analysis_results" --rules "code_analysis_rules.json" %NOIN%

set "RC=%ERRORLEVEL%"
cd /d "%~dp0"
exit /b %RC%

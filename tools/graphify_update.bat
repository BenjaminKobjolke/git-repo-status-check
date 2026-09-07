@echo off
setlocal enabledelayedexpansion
REM ===========================================================================
REM graphify_update.bat  --  TEMPLATE
REM
REM Manual, no-AI code-graph refresh + smoke test. Copy this into your
REM project's  tools\  folder and adjust CODE_DIR below to your source folder
REM (lib / src / app / internal ...). Run it any time to check graphify works.
REM
REM What it does (no LLM, no API key, no token cost):
REM   [1/2] Code-only AST refresh via `graphify update` -- re-extracts code only.
REM         NOTE: this writes the AST cache under CODE_DIR\graphify-out\. It does
REM         NOT rebuild the live root graphify-out\graph.json that queries read.
REM         For an authoritative DIRECTED rebuild of the live graph, run
REM              /graphify CODE_DIR --directed
REM         inside Claude (the skill flow) -- a .bat cannot do that step.
REM   [2/2] Smoke test -- confirm the live root graph exists, is directed, and
REM         answers a query. This is the "does graphify actually work here" check.
REM ===========================================================================

REM ---- adjust this to your project's code folder -------------------------------
set "CODE_DIR=src"
REM -----------------------------------------------------------------------------

REM This bat lives in tools\ ; run everything from the repo root so graphify
REM resolves the live graph at .\graphify-out\ (relative to cwd).
pushd "%~dp0.."

REM Resolve the graphify launcher: prefer PATH, else derive from the interpreter
REM the last build saved (graphify.exe sits next to that python.exe).
set "GRAPHIFY=graphify"
where graphify >nul 2>nul
if errorlevel 1 (
  if exist "graphify-out\.graphify_python" (
    set /p GPY=<graphify-out\.graphify_python
    set "GRAPHIFY=!GPY:python.exe=graphify.exe!"
  ) else (
    echo ERROR: graphify not on PATH and no graphify-out\.graphify_python found.
    echo Build the graph once in Claude:  /graphify %CODE_DIR% --directed
    popd & endlocal & exit /b 1
  )
)

echo === [1/2] code-only AST refresh (no LLM) : %CODE_DIR% ===
"%GRAPHIFY%" update "%CODE_DIR%"
echo.

echo === [2/2] smoke test: live root graph ===
if not exist "graphify-out\graph.json" (
  echo ERROR: graphify-out\graph.json not found.
  echo Build it in Claude:  /graphify %CODE_DIR% --directed
  popd & endlocal & exit /b 1
)
REM Report directed flag + node count of the LIVE root graph (should be directed:True).
if exist "graphify-out\.graphify_python" (
  set /p GPY2=<graphify-out\.graphify_python
  "!GPY2!" -c "import json;d=json.load(open('graphify-out/graph.json',encoding='utf-8'));print('directed:',d.get('directed'),'  nodes:',len(d.get('nodes',[])))"
)
echo.
echo --- god nodes (top 5) ---
"%GRAPHIFY%" god-nodes --top 5
echo.
echo --- sample query ---
"%GRAPHIFY%" query "What are the main modules and how do they connect?"

popd
endlocal

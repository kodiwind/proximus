@echo off
setlocal
set OUT=%~dp0repo_generator_output.txt
cd /d "%~dp0"
echo Running _repo_generator.py > "%OUT%"
echo Working directory: %CD% >> "%OUT%"
echo. >> "%OUT%"
python _repo_generator.py >> "%OUT%" 2>&1
echo. >> "%OUT%"
echo Exit code: %ERRORLEVEL% >> "%OUT%"
echo. >> "%OUT%"
echo --- Directory listing after run --- >> "%OUT%"
dir /s /b >> "%OUT%"
echo.
echo Done. See repo_generator_output.txt
pause

@echo off
setlocal

cd /d %~dp0

echo Running Test Database Generator...
python src/generate_test_db.py %*

pause
goto :EOF
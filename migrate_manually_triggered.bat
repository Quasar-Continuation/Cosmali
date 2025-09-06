@echo off
echo Running manually_triggered migration...
cd /d "%~dp0"
cd src
python migrate_manually_triggered.py
pause

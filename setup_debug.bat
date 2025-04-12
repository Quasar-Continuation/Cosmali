@echo off
setlocal

cd /d %~dp0

python src/generate_certificates.py

python src/main.py

pause
goto :EOF

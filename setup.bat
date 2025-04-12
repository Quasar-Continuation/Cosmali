@echo off
setlocal

cd /d %~dp0

python src/generate_certificates.py

hypercorn --certfile cert.pem --keyfile key.pem -b 0.0.0.0:8000 src/main:app

pause
goto :EOF
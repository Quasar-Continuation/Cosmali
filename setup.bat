@echo off
setlocal

cd /d %~dp0
pushd src

python generate_certificates.py

if not defined NUMBER_OF_PROCESSORS (
	for /f "usebackq delims=" %%N in (`powershell -NoProfile -Command "(Get-CimInstance Win32_Processor).NumberOfLogicalProcessors"`) do set NUMBER_OF_PROCESSORS=%%N
)

if not defined NUMBER_OF_PROCESSORS set NUMBER_OF_PROCESSORS=2

rem (2 * logical_processors) + 1
set /A WORKERS=(%NUMBER_OF_PROCESSORS%*2)+1
if %WORKERS% LSS 1 set WORKERS=1

echo Detected logical processors: %NUMBER_OF_PROCESSORS%, starting %WORKERS% worker(s)

echo Starting Uvicorn...
uvicorn main:app --host 0.0.0.0 --port 5000 --ssl-certfile cert.pem --ssl-keyfile key.pem --workers %WORKERS%

popd

endlocal
pause
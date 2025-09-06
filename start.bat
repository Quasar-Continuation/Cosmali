@echo off
echo Starting backend with SSL support...
cd src
hypercorn main:app --bind 0.0.0.0:40175 --certfile ../cert.pem --keyfile ../key.pem
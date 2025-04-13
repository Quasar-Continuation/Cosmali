#!/bin/bash

cd "$(dirname "$0")"

# This is how you install hypercorn if you don't have it (idk how to do it without breaking system packages)
#apt install python3-hypercorn --break-system-packages

python src/generate_certificates.py

hypercorn --certfile cert.pem --keyfile key.pem -b 0.0.0.0:5000 src/main:app

echo "Press Enter to continue..."
read
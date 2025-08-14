#!/bin/bash

cd "$(dirname "$0")"

python src/generate_certificates.py

# (2 * CPU) + 1
CPU_COUNT=$(nproc 2>/dev/null || echo 2)
WORKERS=$((CPU_COUNT * 2 + 1))

echo "Starting Uvicorn with $WORKERS workers..."
uvicorn src.main:app --host 0.0.0.0 --port 5000 --ssl-certfile cert.pem --ssl-keyfile key.pem --workers $WORKERS --loop uvloop --http httptools

echo "Press Enter to continue..."
read
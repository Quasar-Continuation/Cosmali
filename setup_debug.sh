#!/bin/bash

# Change to the script's directory
cd "$(dirname "$0")"

python src/generate_certificates.py

python src/main.py

echo "Press Enter to continue..."
read
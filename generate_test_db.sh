#!/bin/bash

# Change to the script's directory
cd "$(dirname "$0")"

echo "Running Test Database Generator..."
python src/generate_test_db.py "$@"

echo "Press Enter to continue..."
read
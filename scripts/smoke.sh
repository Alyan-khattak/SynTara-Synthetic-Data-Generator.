#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# smoke.sh — full demo path smoke test
# ═══════════════════════════════════════════════════════════════════
set -e

echo "Running Hardcoding Scan..."
python scripts/check_no_hardcoding.py

echo "Running Unit Tests..."
pytest

echo "Starting Backend API in background..."
python app.py &
APP_PID=$!
sleep 3

echo "Pinging Backend Config..."
curl -s -f http://127.0.0.1:8000/api/config > /dev/null

echo "Pinging Backend Runs..."
curl -s -f http://127.0.0.1:8000/api/runs > /dev/null

echo "Killing Backend API..."
kill $APP_PID

echo "Smoke Test Passed!"

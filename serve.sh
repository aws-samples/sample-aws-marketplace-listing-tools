#!/bin/bash
echo "==> Serving frontend at http://localhost:8080"
echo "    Open http://localhost:8080 in your browser"
echo "    Press Ctrl+C to stop"
cd "$(dirname "$0")/frontend"
python3 -m http.server 8080

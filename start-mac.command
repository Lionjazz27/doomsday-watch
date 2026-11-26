#!/bin/bash
# Double-click to keep watching from this Mac (checks every ~3 minutes).
cd "$(dirname "$0")"
python3 -m pip install --quiet --user requests 2>/dev/null
caffeinate -i python3 watcher.py --loop 180

#!/bin/bash
# Restart Flask dev server on 192.168.2.30
cd /home/NRWcup
pkill -f 'python3.*app_main' 2>/dev/null
sleep 2
nohup venv/bin/python3 app_main.py >> /tmp/flask.log 2>&1 &
echo "Flask started (PID $!)"
sleep 3
tail -4 /tmp/flask.log

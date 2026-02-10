#!/bin/sh
# gitbackup.sh 
# Location: /home/pi/gitbackup.sh

cd /home/pi

HOUR=$(date +%-H)
HOUR=$((HOUR + 1))
if [ "$HOUR" -eq 24 ]; then
    HOUR=00
fi
DATE=$(date +"%m%d-")${HOUR}$(date +%M)

gitingest ./NRWCup \
    -e backups \
    -e migrations \
    -e doc_archives \
    -e tests \
    -e venv \
    -e backup_script.py \
    -e requirements.txt \
    -e .gitignore \
    -e __pycache__ \
    -e static \
    -e app/static/ \
    -e utils \
    -e instance/ \
    -e gitback.sh \
    -e workspace.code-workspace \
    -e app/routes/backups/ \
    -e app/templates/*.pyc \
    -e '*.pyc' \
    -e '*.pyo' \
    -e '*.log' \
    -o "/home/pi/nrwcup-${DATE}.txt"


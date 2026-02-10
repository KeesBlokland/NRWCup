#!/bin/bash
# root_gitbackup.sh v3
cd /home/NRWcup/
source venv/bin/activate
 
HOUR=`date +%-H`
HOUR=$((HOUR + 1))
if [ $HOUR -eq 24 ]; then
    HOUR=00
fi
DATE=$(date +"%m%d-")${HOUR}$(date +%M)

gitingest /home/NRWcup/NRWcup/ \
    -e /backups \
    -e /instance \
    -e /utils \
    -e /doc_archives \
    -e /venv \
    -e /migrations \
    -e /.git \
    -e __pycache__ \
    -e *.pyc \
    -e *.pyo \
    -e *.pyd \
    -e .pytest_cache \
    -e .coverage \
    -e static/css/vendor \
    -e static/js/vendor \
    -e static/css/main_styles.css \
    -e *.min.css \
    -e *.min.js \
    -e bootstrap*.* \
    -e jquery*.* \
    -e popper*.* \
    -e test_*.py \
    -e *.log \
    -e *.bak \
    -e *.swp \
    -e .DS_Store \
    -e temp/ \
    -e tmp/ \
    -e favicon.ico \
    -e workspace.* \
    -e backup_script.py \
    -e .gitignore \
    -o /home/NRWcup/nrwcup-${DATE}.txt

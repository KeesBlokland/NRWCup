#!/bin/bash
"""
File: dir_setup.sh
Version: 1.0.0
Created: 2024-12-04
Last Updated: 2024-12-04
Description: Setup script for NRW Cup directory structure
"""

# Create main directory structure
mkdir -p blueprints
mkdir -p templates/teilnehmer
mkdir -p templates/teams
mkdir -p templates/contest
mkdir -p templates/scoring
mkdir -p templates/reports
mkdir -p templates/system
mkdir -p static/css
mkdir -p static/js

# Create blueprint __init__
touch blueprints/__init__.py

# Create blueprint files with proper naming
touch blueprints/bp_teilnehmer.py
touch blueprints/bp_teams.py
touch blueprints/bp_contest.py
touch blueprints/bp_scoring.py
touch blueprints/bp_reports.py
touch blueprints/bp_system.py

# Create templates with clear naming
touch templates/home_main.html
touch templates/teilnehmer/teilnehmer_main.html
touch templates/teilnehmer/teilnehmer_add.html
touch templates/teilnehmer/teilnehmer_edit.html
touch templates/teams/teams_main.html
touch templates/teams/teams_create.html
touch templates/contest/contest_main.html
touch templates/scoring/scoring_main.html
touch templates/reports/reports_main.html
touch templates/system/system_main.html

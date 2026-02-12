# NRW Cup 2025 - Project Reference

## Project Overview
Flask web application for managing NRW Cup 2025 model aircraft competition.
Runs on Raspberry Pi with SQLite database.

## Architecture
- **Entry point**: app_main.py (Flask app, 12 registered blueprints)
- **Database**: SQLite at instance/NRWCup2025.db (auto-detected path)
- **Models**: app/models.py (User, Teilnehmer, Flugzeuge, Team, Location, Event, Round, TeamRound, TaskType, Score, ScoreValue, SystemConfig, AuditLog)
- **Config**: app/config.py (DB, email, admin password)

## Registered Blueprints
| Blueprint | Prefix | File |
|-----------|--------|------|
| teilnehmer_bp | /teilnehmer | bp_teilnehmer.py |
| teams_bp | /teams | bp_teams.py |
| contest_bp | /contest | bp_contest.py |
| scoring_bp | /scoring | bp_scoring.py |
| reports_bp | /reports | bp_reports.py |
| system_bp | /system | bp_system.py |
| flugzeuge_bp | /flugzeuge | bp_flugzeuge.py |
| figures_bp | /figures | bp_figures.py |
| formular_bp | /formular | bp_formular.py |
| testdata_bp | /testdata | bp_testdata.py |
| cleanup_bp | /cleanup | bp_cleanup.py |
| start_order_bp | /start_order | bp_start_order.py |


## Environment & Workflow
- **Dev server (30)**: 192.168.2.30 — git repo, all editing here, path: `/home/NRWcup`
- **Pi (83)**: 192.168.2.83 — production, path: `/home/pi/NRWCup` (capital C!), user: `pi`, pass: `13TM31n`
- **SSH to Pi**: `sshpass -p '13TM31n' ssh pi@192.168.2.83`
- **Gitea**: 192.168.2.7:3000 — LOCAL git remote, commit here during working sessions
- **GitHub**: github.com/KeesBlokland/NRWCup — PUBLIC remote, push only when explicitly asked
- **VPS**: nrwcup.scale-f-schlepp.de (194.164.90.238) — public site, gunicorn+systemd, user: `scalefschleppwilga2008`
- Python: Flask 2.3.3, SQLAlchemy 1.4.54, CSRFProtect (flask_wtf)
- Pi uses system python3 (no venv)
- Deploy to Pi: `sshpass -p '13TM31n' rsync -avz --exclude='instance/' --exclude='venv/' --exclude='backups/' --exclude='doc_archives/' --exclude='__pycache__/' /home/NRWcup/ pi@192.168.2.83:/home/pi/NRWCup/`
- Flask restart on Pi: `sshpass -p '13TM31n' ssh pi@192.168.2.83 "kill \$(pgrep -f 'python3.*app_main') 2>/dev/null; sleep 1; cd /home/pi/NRWCup && nohup python3 app_main.py > /dev/null 2>&1 &"`
- **Always start Claude from /home/NRWcup** (not /root)
- **TODOs go in todo.md**, not here

## Scoring Rules (verified 2026-02-10)

### Qualitätswertung (judged 0-10, multiplied by K-factor)
| Figure | DB Code | K-Factor |
|--------|---------|----------|
| Bodenstart | STRT | 15 |
| Platzrunde | PLZU | 20 |
| Kür: Platzrunde M | PLTZ-M | 22 |
| Kür: Platzrunde M-K | PLTZ-MK | 23 |
| Platzüberflug | HKURV | 10 |
| Kür: Platzüberflug Oval | PLTZ-1OV | 13 |
| Kür: Platzüberflug Kreis | PLTZ-2KR | 12 |
| Ausklinken | AUSKL | 10 |
| Verfahrenskurve | VKURV | 10 |
| Seilabwurf (quality) | SEILW | 15 |
| Landeanflug Motormodell | LANM | 10 |
| Landung Motormodell | LANDM | 10 |
| Landeanflug Segelmodell | LANDGS | 10 |
| Landung Segelmodell | LANDS | 10 |
| Naturge. Erscheinungsb. | ERSCH | 15 |

### Messwertung (objective, not averaged across judges)
| Item | DB Code | Values |
|------|---------|--------|
| Gesamt-Flugzeit Segelmodell | SEGZEIT | seconds → MAX(0, 300-(|200-time|*3)) |
| Zielabwurf Schleppseil | SEILZ | 0, 5, 10, 20, 30 |
| Ziellandung Motormodell | LANDGM | 0, 5, 10, 20, 30 |
| Ziellandung Segelmodell | LANS | 0, 5, 10, 20, 30 |

TaG (Touch and Go) — dropped for 2025.

### Kürfiguren
- ONE optional figure per group (or none):
  - Platzrunde group: M or M-K
  - Platzüberflug group: Kreis or Oval
- Unchosen variants score 0

### Calculation
- Qualitätswertung: averaged across judges (drop lowest if 4+ judges)
- Messwertung: single value, first non-zero from any judge
- Per-round normalization to 1000 (highest team = 1000)
- Final standings: drop lowest round if 3+ rounds, sum remaining, normalize to 1000
- **UNRESOLVED**: code drops lowest round, original Excel drops highest — verify with organizers!

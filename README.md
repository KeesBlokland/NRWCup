# NRW Cup -- Wettbewerbsverwaltung

Flask web application for managing the NRW Cup model aircraft competition (Schleppflug / Segelflug).
Runs offline on a Raspberry Pi or any Linux server.

Built with assistance from Claude (Anthropic).

---

## Features

- **Teilnehmer & Teams** -- Manage pilots, tow pilots, judges, and team composition
- **Flugzeuge** -- Register gliders and tow planes
- **Startlisten** -- Generate and print start lists per round, drag-and-drop reorder
- **Wertung** -- Score entry per judge, per team, per round
  - Qualitaetswertung (0-10 x K-factor) with judge drop rule (4 judges: drop highest; 5: drop highest + lowest)
  - Messwertung (SEGZEIT, SEILZ, LANDGM, LANS) -- entered once, replicated to all judges
  - Varianten-Programme (Steigflug / Ueberflug exclusive groups)
  - Alle-Null button for crash/withdrawal -- replicates zeros to all judges automatically
- **Ergebnisse** -- Per-round Promille-Punkte normalization (winner = 1000), final standings with drop-worst-round, tiebreaker by Streicher
- **Berichte** -- PDF scoresheets (organizer), results email to pilots (no per-judge breakdown)
- **Benutzerhandbuch** -- Built-in help page + downloadable PDF manual

Scoring rules follow BeMod-F-Schlepp 2026.

---

## Tech Stack

- Python 3 / Flask 2.3
- SQLAlchemy 1.4 / SQLite
- Bootstrap 5
- Runs on Raspberry Pi (system Python, no venv needed on Pi)

---

## Setup (Development)

```bash
git clone https://github.com/KeesBlokland/NRWCup.git
cd NRWCup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit with your settings
python3 app_main.py
```

Open http://localhost:5000

### Environment variables (.env)

```
SECRET_KEY=change-this-to-a-random-string
ADMIN_PASSWORD=your-admin-password
MAIL_SERVER=smtp.example.com
MAIL_PORT=465
MAIL_USERNAME=your@email.com
MAIL_PASSWORD=your-mail-password
MAIL_ENABLED=false
```

All credentials are loaded from environment variables -- nothing is hardcoded.

---

## Deployment (Raspberry Pi)

The app is designed to run as a systemd service on a Raspberry Pi in hotspot mode
(no internet required at the event).

```bash
# Sync code to Pi
rsync -avz --exclude='venv' --exclude='__pycache__' --exclude='instance' \
  ./ pi@<PI_IP>:/home/NRWcup/

# Fix ownership
ssh pi@<PI_IP> 'sudo chown -R pi:pi /home/NRWcup'

# Restart service
ssh pi@<PI_IP> 'sudo systemctl restart nrwcup-flask.service'
```

The Pi runs a WiFi hotspot. Judges and organisers connect to it and open the app in a browser.

---

## Scoring Rules (BeMod-F-Schlepp 2026)

### Qualitaetswertung
- Each figure scored 0-10 by each judge, multiplied by K-factor
- Judge drop: 3 judges = no drop; 4 = drop highest; 5 = drop highest + lowest
- Average remaining, round to 3 decimal places, multiply by K-factor

### Messwertung
- SEGZEIT: MAX(0, 200 - |200 - time|) -- target 200s, max 200 pts
- SEILZ, LANDGM, LANS: 0 / 10 / 20 / 30 pts

### Normalization
- Per round: winner = 1000 Promille-Punkte, others proportional
- Final: drop worst round when total rounds >= threshold (default: 3)
- Tiebreaker: higher Streicher (dropped round score) wins

---

## License

MIT

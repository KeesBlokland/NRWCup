# NRWcup Session Handover — 16 Apr 2026

## System overview

| Machine | Role | Access |
|---------|------|--------|
| 192.168.2.87 | Live Pi (production) | sshpass -p '13TM31n' ssh -o PubkeyAuthentication=no pi@192.168.2.87 |
| 192.168.2.30 | Dev Pi (backup/staging) | same credentials |
| 192.168.2.7:3000 | Gitea repo | http://192.168.2.7:3000/kees/NRWcup.git |

App on live Pi: /home/NRWcup/ — NOT a git repo. Deploy via scp after git commit/push.
Service on live Pi: nrwcup-flask.service (systemd). Restart: `sudo systemctl restart nrwcup-flask.service`

Local clone: /home/kees/Documents/VSCode-projects/NRWcup-git/

---

## Issue fixed this session: SEGZEIT formula wrong

### What was wrong
Figure 16 (SEGZEIT — Flugzeit Segelmodell):
- Rules: 300 points max, -3 points per STARTED second over/under 200s target
- Code had: `MAX(0, 200 - ABS(200 - t))` — wrong max (200), wrong deduction (1pt/s, not 3pt/s started)
- Correct formula: `MAX(0, 300 - 3 * CEIL(ABS(t - 200)))`

### What was fixed
`app/services/services_scoring.py` — committed and deployed to live Pi:
- Line 420: calculation inside `aggregate_judge_scores()`
- Line 658: calculation inside `calculate_seglerzeit()`
- `import math` added
- Docstrings updated

### Still needs fixing — NOT yet done
The old formula also appears as display text and JavaScript in templates.
These are cosmetic (display only) except where JS does a live preview calculation —
those will show the wrong live preview until fixed.

| File | Line | What | Status |
|------|------|------|--------|
| app/templates/scoring/score_form.html | 249 | Display text | DONE |
| app/templates/scoring/score_form.html | 384 | JS comment | DONE |
| app/templates/scoring/score_form.html | 392 | JS live calc: `Math.max(0, 200 - Math.abs(200 - parseFloat(actualTime)))` | DONE — wrong live preview |
| app/templates/scoring/combined_score_form.html | 165 | Jinja server-side display: `{{ '%.1f' % [0, 200 - (val - 200)|abs]|max }}` | DONE — shows wrong points |
| app/templates/scoring/combined_score_form.html | 169 | Display text | DONE |
| app/templates/scoring/combined_score_form.html | 275 | JS live calc: `Math.max(0, 200 - Math.abs(200 - t))` | DONE — wrong live preview |
| app/templates/scoring/unified_scoring.html | 455 | Display text in info modal | DONE |
| app/routes/bp_scoring.py | 441 | Comment only | DONE |
| app/templates/system/hilfe.html | 1013 | Help page table | DONE |
| app/templates/system/hilfe.html | 1036 | Help page text | DONE |
| README.md | 96 | Documentation | DONE |

### Correct JS replacement
```javascript
// Old (wrong):
Math.max(0, 200 - Math.abs(200 - parseFloat(actualTime)))

// New (correct):
Math.max(0, 300 - 3 * Math.ceil(Math.abs(parseFloat(actualTime) - 200)))
```

### Correct Jinja replacement (combined_score_form.html line 165)
```
// Old:
{{ '%.1f' % [0, 200 - (val - 200)|abs]|max }}

// New (note: Jinja has no ceil filter by default — check if it is registered,
// or compute as integer: 300 - 3 * ((val - 200)|abs|int + (1 if (val - 200)|abs % 1 > 0 else 0)))
// Simplest safe option: delegate display to a template filter or accept minor rounding in display only.
```

---

## Deployment procedure (this project)

1. Edit in /home/kees/Documents/VSCode-projects/NRWcup-git/
2. `git commit && git push` to Gitea
3. `sshpass -p '13TM31n' scp -o PubkeyAuthentication=no <file> pi@192.168.2.87:/home/NRWcup/<file>`
4. `sshpass -p '13TM31n' ssh -o PubkeyAuthentication=no pi@192.168.2.87 "echo '13TM31n' | sudo -S systemctl restart nrwcup-flask.service"`

Note: restart_flask.sh in /home/NRWcup/ is stale — has a comment saying .30 but runs locally.
Use systemctl restart instead.

---

## Open questions / pending work

- Dev Pi (.30): formula fix not deployed there — left as backup/staging, intentional
- Demo server (194.164.90.238): credentials and path unknown to Claude — user handles uploads manually

## Completed this session (16 Apr 2026)

- SEGZEIT formula fixed everywhere (services, routes, templates, JS, hilfe, README) — issues #202, #203, #204
- Max Bewertungspunkte corrected to 1740/1790 in unified_scoring.html and hilfe.html (was stale 1640/1690)
- PDF manual regenerated as v1.4 April 2026 — old version kept as NRWCup_Handbuch_komplett_v1.3_Mar2026.pdf
- All K-factors verified against BeMod-F-Schlepp.pdf dated 15 Apr 2026 — all correct
- Jinja ceil resolved: input is step=1 (integer seconds), so `(val - 200)|abs` without ceil is equivalent
- PDF generation procedure documented in issue #203 and deployment procedure below

## PDF regeneration procedure (run after any hilfe.html change)

```bash
# 1. Generate
google-chrome --headless --disable-gpu --no-sandbox \
  --print-to-pdf=/tmp/NRWCup_Handbuch_new.pdf \
  --print-to-pdf-no-header \
  http://192.168.2.87:5000/system/hilfe

# 2. Verify
pdftotext /tmp/NRWCup_Handbuch_new.pdf - | grep -i "version\|formel\|punkte"

# 3. Copy to repo and deploy
cp /tmp/NRWCup_Handbuch_new.pdf app/static/hilfe/NRWCup_Handbuch_komplett.pdf
# scp to Pi + demo server
```

Always rename the existing PDF with version+date before overwriting.

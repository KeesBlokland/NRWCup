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
| app/templates/scoring/score_form.html | 249 | Display text | OPEN |
| app/templates/scoring/score_form.html | 384 | JS comment | OPEN |
| app/templates/scoring/score_form.html | 392 | JS live calc: `Math.max(0, 200 - Math.abs(200 - parseFloat(actualTime)))` | OPEN — wrong live preview |
| app/templates/scoring/combined_score_form.html | 165 | Jinja server-side display: `{{ '%.1f' % [0, 200 - (val - 200)|abs]|max }}` | OPEN — shows wrong points |
| app/templates/scoring/combined_score_form.html | 169 | Display text | OPEN |
| app/templates/scoring/combined_score_form.html | 275 | JS live calc: `Math.max(0, 200 - Math.abs(200 - t))` | OPEN — wrong live preview |
| app/templates/scoring/unified_scoring.html | 455 | Display text in info modal | OPEN |
| app/routes/bp_scoring.py | 441 | Comment only | OPEN |
| app/templates/system/hilfe.html | 1013 | Help page table | OPEN |
| app/templates/system/hilfe.html | 1036 | Help page text | OPEN |
| README.md | 96 | Documentation | OPEN |

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

- Jinja ceil for combined_score_form.html line 165 — verify if a ceil filter is registered in app
- Update max_value display/validation where 200 appears as the max (should be 300) — search templates
- Dev Pi (.30): formula fix not deployed there yet (left as backup)
- README.md line 96: stale formula description

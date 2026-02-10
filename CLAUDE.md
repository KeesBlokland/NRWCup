# NRW Cup 2025 - Project Status & Notes

## Project Overview
Flask web application for managing NRW Cup 2025 model aircraft competition.
Runs on Raspberry Pi with SQLite database.

## Architecture
- **Entry point**: app_main.py (Flask app, 12 registered blueprints)
- **Database**: SQLite at /home/NRWcup/instance/NRWCup2025.db
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

## Unregistered Blueprints (NOT in app_main.py)
- **bp_public.py** - Public results view (missing imports at top of file!)
- **bp_rules.py** - Rule set management (references non-existent models: ScoringRuleSet, ScoringRule)

---

## Code Review Findings (2026-02-10)

### CRITICAL ISSUES

1. **bp_public.py - Missing imports** (app/routes/bp_public.py)
   - File has no import statements at all - missing `Blueprint`, `render_template`, `Event`, `Round`, `ScoringService`
   - Not registered in app_main.py so won't crash the app, but is broken if enabled

2. **bp_rules.py - References non-existent models** (app/routes/bp_rules.py:9)
   - `from app.models import db, ScoringRuleSet, ScoringRule` - these models don't exist in models.py
   - Not registered in app_main.py so won't crash the app, but is broken if enabled
   - The associated services (services_rules.py, rule_engine.py) likely reference the same missing models

3. **bp_system.py - Missing function `get_log_files_info`** (app/routes/bp_system.py:111)
   - Called in `index()` route but function is not defined anywhere in the codebase
   - This WILL crash when accessing /system/

### MODERATE ISSUES

4. **bp_scoring.py - `api_score` sort uses non-existent 'code' key** (line ~451)
   - `figures_data` items don't have a 'code' key, only 'name', 'value', 'k_factor', 'points'
   - Falls back to name sort via try/except, so it works but not as intended

5. **bp_scoring.py - `update_score` calls `create_score` instead of update** (line ~612)
   - When updating a score, it creates/replaces via `create_score()` which works because of upsert logic
   - But the original `score_id` passed in is never used - the old score object gets replaced
   - The score's `locked` status could be lost in the process

6. **bp_reports.py - `round_details` references template `reports/reports_round_details.html`** (line ~105)
   - Template exists but should be verified it renders correctly with the `raw_scores` variable

7. **Duplicate `clear_all_scores` import in bp_contest.py** (line 15 and 192)
   - Same import appears twice, no functional issue but messy

8. **bp_formular.py - `all_round_objects` used before assignment** (line ~181)
   - `all_round_objects` is defined inside `if active_event:` block but used in `if all_round_objects:` outside it
   - Will crash with NameError if no active_event

### MINOR / STYLE ISSUES

9. **Comment artifacts**: Several files have leftover comments like "# Add this route to..." suggesting incremental development
10. **Debug print statements** in `team_scoresheet_pdf` route (lines ~1169, 1174, 1185) - should use logger
11. **Score model comment**: models.py line 156 says "# ADD THESE THREE NEW FIELDS" - should be cleaned up
12. **test_scoresheet route** at end of bp_scoring.py (line 1295) - appears to be a debug route

### SCORING LOGIC REVIEW

The scoring calculation appears correct per the README spec:
- K-factor multiplication for standard figures
- SEGZEIT special formula: MAX(0, 300 - (ABS(200-time) * 3))
- Messwertung (LANDGM, LANS, SEILZ, SEGZEIT) added directly, not averaged
- Qualitaetswertung averaged across judges, lowest dropped if 4+ judges
- Normalization to 1000-point scale
- Final standings: drop lowest round if 3+ rounds, sum remaining
- Final normalization to 1000

### !! UNRESOLVED: ROUND DROPPING RULE — LOWEST vs HIGHEST !!

**CONFLICT**: The code and README drop the **LOWEST** (schwächste) round.
The original Excel spreadsheet drops the **HIGHEST** round.

- `services_scoring.py:410`: `min_score = min(temp_scores)` → drops lowest
- `README.md:82`: "Der schwächste Durchgang wird gestrichen" → drops lowest
- Original Excel: drops HIGHEST

**The official PDFs (Bewertungsbögen, Kürfiguren) do NOT contain a rule about this.**
These documents only cover per-round scoring and optional figure selection.
**This needs to be verified with the competition organizers (DMFV/NRW Cup rules).**

### RULES VALIDATION (vs official Bewertungsbögen NRW Cup.pdf & Kürfiguren 2025.pdf)

**Source docs**: Pi:/home/pi/NRWCup/doc_archives/
- "Bewertungsbögen NRW Cup.pdf" - Official scoring sheet (2023 format, per-round form only)
- "Kürfiguren 2025.pdf" - Optional figure selection form only
- **Neither document specifies the round-dropping rule or final standings calculation**

**Qualitätswertung figures (judged 0-10, multiplied by K-factor):**

| # | Scoresheet Figure | DB Code | K-Factor | Status |
|---|---|---|---|---|
| 1 | Bodenstart | STRT | 15 | OK |
| 2 | Platzrunde | PLZU | 20 | OK |
| 3 | Kür: Platzrunde M | PLTZ-M | 22 | OK (mutually exclusive) |
| 4 | Kür: Platzrunde M-K | PLTZ-MK | 23 | OK (mutually exclusive) |
| 5 | Platzüberflug | HKURV | 10 | OK |
| 6 | Kür: Platzüberflug Oval | PLTZ-1OV | 13 | OK (mutually exclusive) |
| 7 | Kür: Platzüberflug Kreis | PLTZ-2KR | 12 | OK (mutually exclusive) |
| 8 | Ausklinken | AUSKL | 10 | OK |
| 9 | Verfahrenskurve | VKURV | 10 | OK |
| 10 | Seilabwurf (quality) | SEILW | 15 | OK |
| 11 | Landeanflug Motormodell | LANM | 10 | OK |
| 12 | Landung Motormodell | LANDM | 10 | OK |
| 13 | Landeanflug Segelmodell | LANDGS | 10 | OK |
| 14 | Landung Segelmodell | LANDS | 10 | OK |
| 15 | Naturge. Erscheinungsb. | ERSCH | 15 | OK |

**Messwertung (objective measurements, not averaged across judges):**

| Scoresheet Item | DB Code | Values | Status |
|---|---|---|---|
| Gesamt-Flugzeit Segelmodell | SEGZEIT | seconds (special calc) | OK |
| Zielabwurf Schleppseil | SEILZ | 0,5,10,20,30 | OK |
| Ziellandung Motormodell | LANDGM | 0,5,10,20,30 | OK |
| Ziellandung Segelmodell | LANS | 0,5,10,20,30 | OK |
| **TaG** | **???** | 0,5,10,20,30 | **MISSING FROM DB!** |

**Kürfiguren rules** (from Kürfiguren 2025.pdf):
- Teams choose ONE optional figure PER GROUP (or none):
  - Platzrunde group: pick one of M or M-K (or neither)
  - Platzüberflug group: pick one of Kreis or Oval (or neither)
- Unchosen variants score 0
- System handles this via mutually exclusive groups in test data generator — CORRECT
- All judges must score the same variant for a given team/round (consistency verified)

**TaG = Touch and Go — DROPPED for 2025. System is correct without it.**

### MESSWERTUNG FLOW ANALYSIS (2026-02-10)

**Historical bug**: Messwertung values (Zielabwurf, Flugzeit) are measured by ONE judge, but
if values were entered on a different judge's scoresheet, they were averaged across all judges
(divided by 3). This was WRONG.

**Current code** (`aggregate_judge_scores()` in services_scoring.py:200-298) **handles this correctly**.

**How it works end-to-end:**

1. **Score form** (`score_form.html`): ALL judges see ALL figures (including Messwertung).
   - LANDGM/LANS/SEILZ: dropdown with options "-"(empty), 0, 5, 10, 20, 30
   - SEGZEIT: number input 0-300

2. **Form submission** (`bp_scoring.py`):
   - `enter_score`: passes all fields including empty strings
   - `update_score`: filters out empty strings (`and value`)

3. **`create_score()`** (services_scoring.py:99-101):
   - `if value is None or value == '': continue` — empty/unset fields create NO ScoreValue row
   - Explicit "0" DOES create a ScoreValue with value=0

4. **`aggregate_judge_scores()`** (services_scoring.py:265-274):
   ```python
   non_zero = [v for v in values if v != 0]
   if non_zero:
       chosen = non_zero[0]  # First non-zero value
   else:
       chosen = 0            # All zero = genuine zero score
   ```

**Scenario results:**

| Scenario | Judge 1 | Judge 2 | Judge 3 | List | Result |
|----------|---------|---------|---------|------|--------|
| Normal (J1 enters) | 20 | "-" | "-" | [20] | 20 OK |
| J2 enters instead | "-" | 20 | "-" | [20] | 20 OK |
| J1 enters, others set 0 | 20 | 0 | 0 | [20,0,0] | 20 OK |
| All enter same | 20 | 20 | 20 | [20,20,20] | 20 OK (warning logged) |
| Genuine zero | 0 | "-" | "-" | [0] | 0 OK |
| SEGZEIT=180 on J1 | 180→240pts | "-" | "-" | [240] | 240 OK |
| **Conflict: different values** | **20** | **30** | **"-"** | **[20,30]** | **First one (ambiguous!)** |

**Key design points:**
- Empty/unset dropdown ("-") → no ScoreValue → not in the list at all
- Explicit 0 → ScoreValue exists but filtered by `non_zero` check
- Takes first non-zero regardless of which judge entered it → works for any judge
- Warning logged if multiple non-zero values (shouldn't happen in practice)
- **Edge case**: If two judges enter DIFFERENT non-zero values, result depends on DB query order

**Verdict: The averaging bug is FIXED. Current code correctly picks the single measurement value
regardless of which judge's form it was entered on.**

### TEMPLATES STATUS

All referenced templates exist. Key templates:
- base.html (main layout)
- scoring/unified_scoring.html (main scoring view)
- scoring/score_form.html (score entry/edit)
- formular/formular_main.html (start lists)
- Missing: public/index.html, public/results.html, public/not_available.html (for unregistered bp_public)

---

## TODO / Next Steps

- [ ] Fix `get_log_files_info` missing function in bp_system.py (CRITICAL - crashes /system/)
- [ ] Fix `all_round_objects` NameError in bp_formular.py when no active event
- [ ] Add missing imports to bp_public.py if you want to enable it
- [ ] Add ScoringRuleSet/ScoringRule models if you want to enable bp_rules.py
- [ ] Register bp_public and bp_rules in app_main.py when ready
- [ ] Remove debug print statements from team_scoresheet_pdf
- [ ] Clean up comment artifacts
- [ ] Remove duplicate import in bp_contest.py
- [ ] Test the app end-to-end on the dev server
- [ ] Add 'code' key to figures_data in api_score route
- [x] ~~Clarify TaG~~: Touch and Go - dropped for 2025, no action needed
- [x] ~~Verify Kürfiguren~~: ONE per group (Platzrunde: M or M-K; Platzüberflug: Kreis or Oval). Test data generator is correct.
- [x] ~~Validate scoring calculations~~: Full verification completed (see below). All correct.
- [ ] **CRITICAL: Verify round-dropping rule** — code drops LOWEST, Excel drops HIGHEST. Ask competition organizers which is correct!

---

## Scoring Verification Results (2026-02-10, Pi database, Event 2: NRW Cup 2026)

Test data: 13 teams, 3 rounds (round_ids 4,5,6), 3 judges, 39 score sheets per round.

### Raw Score Calculation: ALL 39 MATCH
Manual recalculation of every team/round matches DB values exactly.
- Qualitätswertung: averaged across 3 judges (would drop lowest if 4+) — correct
- Messwertung (SEGZEIT, SEILZ, LANDGM, LANS): first non-zero value, not averaged — correct
- SEGZEIT formula: MAX(0, 300-(|200-time|*3)) — correct

### Normalization: ALL 39 MATCH
Per-round normalization to 1000-point scale (highest team = 1000) — correct.

### Kürfiguren Consistency: ALL OK
- All 3 judges agree on Kürfigur variants for every team/round
- No team has both variants in same group (mutual exclusion verified)
- Rules: ONE per group (Platzrunde: M or M-K; Platzüberflug: Kreis or Oval)

### Final Standings (drop lowest of 3 rounds, normalize to 1000):

| Rank | Team | R1 | R2 | R3 | Dropped | Sum | Final |
|------|------|----|----|----|---------|-----|-------|
| 1 | 4 | 994.59 | 954.34 | 998.22 | 954.34 | 1992.81 | 1000.00 |
| 2 | 2 | 940.33 | 1000.00 | 991.24 | 940.33 | 1991.24 | 999.21 |
| 3 | 1 | 985.27 | 940.44 | 999.75 | 940.44 | 1985.02 | 996.09 |
| 4 | 5 | 1000.00 | 933.81 | 984.64 | 933.81 | 1984.64 | 995.90 |
| 5 | 11 | 979.98 | 1000.00 | 945.16 | 945.16 | 1979.98 | 993.56 |
| 6 | 13 | 979.48 | 963.91 | 990.73 | 963.91 | 1970.21 | 988.66 |
| 7 | 14 | 940.58 | 970.79 | 980.20 | 940.58 | 1950.99 | 979.01 |
| 8 | 3 | 950.91 | 969.52 | 980.83 | 950.91 | 1950.35 | 978.69 |
| 9 | 7 | 962.24 | 957.28 | 983.62 | 957.28 | 1945.86 | 976.44 |
| 10 | 17 | 974.70 | 960.85 | 909.23 | 909.23 | 1935.54 | 971.26 |
| 11 | 6 | 956.07 | 978.57 | 916.97 | 916.97 | 1934.64 | 970.81 |
| 12 | 10 | 921.70 | 927.69 | 1000.00 | 921.70 | 1927.69 | 967.32 |
| 13 | 9 | 942.85 | 901.67 | 949.60 | 901.67 | 1892.45 | 949.64 |

---

## Environment Notes
- Python: Flask 2.3.3, SQLAlchemy 1.4.54
- Production runs on Raspberry Pi with SQLite
- Dev and production servers on local LAN

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

### RULES VALIDATION (vs official Bewertungsbögen NRW Cup.pdf & Kürfiguren 2025.pdf)

**Source docs**: Pi:/home/pi/NRWCup/doc_archives/
- "Bewertungsbögen NRW Cup.pdf" - Official scoring sheet (2023 format)
- "Kürfiguren 2025.pdf" - Optional figure selection form

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
- Teams choose ONE optional figure per round (or "Keine"/none)
- Options: Platzrunde M, Platzrunde M-K, Platzüberflug Kreis, Platzüberflug Oval
- Unchosen variants score 0
- System handles this via mutually exclusive groups in test data generator
- CONFIRMED: Teams pick ONE Kürfigur total (or "Keine"). NOT one per group.
- The test data generator incorrectly treats them as two separate groups — needs fixing.

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
- [x] ~~Verify Kürfiguren~~: ONE total (or none). Test data generator needs fix (treats as two groups)
- [ ] Fix test data generator: Kürfiguren should be ONE choice from all 4 variants (not one per group)
- [x] ~~Validate scoring calculations~~: Manual calc for team 9 round 1 matches DB (1388.5). Messwertung handling verified correct — no longer averages across judges.

---

## Environment Notes
- Python: Flask 2.3.3, SQLAlchemy 1.4.54
- Production runs on Raspberry Pi with SQLite
- Dev and production servers on local LAN

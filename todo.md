# NRW Cup - Open Tasks

## CRITICAL

- [ ] Fix `get_log_files_info` missing function in bp_system.py — crashes /system/ route (bp_system.py:111)
- [ ] Fix `all_round_objects` NameError in bp_formular.py when no active event (bp_formular.py:~181)
- [ ] **Verify round-dropping rule with competition organizers** — code drops LOWEST round, original Excel drops HIGHEST. Ask DMFV/NRW Cup which is correct!

## MODERATE

- [ ] bp_scoring.py: `api_score` sort uses non-existent 'code' key (~line 451) — falls back to name sort, works but not as intended
- [ ] bp_scoring.py: `update_score` calls `create_score` instead of update (~line 612) — works via upsert but `locked` status could be lost
- [ ] bp_reports.py: verify `round_details` template renders correctly with `raw_scores` variable
- [ ] bp_contest.py: duplicate `clear_all_scores` import (line 15 and 192)

## MINOR / CLEANUP

- [ ] Remove debug print statements from `team_scoresheet_pdf` (bp_scoring.py ~lines 1169, 1174, 1185)
- [ ] Clean up comment artifacts ("# Add this route to..." etc.)
- [ ] Remove "# ADD THESE THREE NEW FIELDS" comment in models.py:156
- [ ] Remove `test_scoresheet` debug route at end of bp_scoring.py (line 1295)

## UNREGISTERED BLUEPRINTS (enable when ready)

- [ ] bp_public.py — add missing imports (Blueprint, render_template, Event, Round, ScoringService)
- [ ] bp_public.py — create templates: public/index.html, public/results.html, public/not_available.html
- [ ] bp_rules.py — add ScoringRuleSet/ScoringRule models to models.py
- [ ] Register bp_public and bp_rules in app_main.py

## DONE

- [x] Clarify TaG: Touch and Go — dropped for 2025, no action needed
- [x] Verify Kürfiguren: ONE per group (Platzrunde: M or M-K; Platzüberflug: Kreis or Oval)
- [x] Validate scoring calculations: full verification completed, all 39 scores match
- [x] Fix Messwertung averaging bug: confirmed fixed in current code
- [x] Standardize button/badge sizes across all templates
- [x] Auto-detect database path in app_main.py
- [x] Clean GitHub repo (password exposure)

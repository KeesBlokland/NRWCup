# NRW Cup - Open Tasks

## CRITICAL

- [x] Fix `get_log_files_info` missing function in bp_system.py — added function (ada347f)
- [x] Fix `all_round_objects` NameError in bp_formular.py when no active event (ada347f)
- [x] Round-dropping rule resolved — drop LOWEST is safe, drop HIGHEST is dangerous with missing scores. See README.md section 4 for explanation.

## MODERATE

- [x] bp_scoring.py: `api_score` sort — fixed to use name_de instead of missing 'code' key (d7882fb)
- [x] bp_scoring.py: `update_score` — now preserves locked status when calling create_score (d7882fb)
- [x] bp_reports.py: `round_details` template verified — uses team_round.raw_score directly, renders correctly
- [x] bp_contest.py: removed duplicate `clear_all_scores` import (d7882fb)

## MINOR / CLEANUP

- [x] Removed debug print statements from `team_scoresheet_pdf` (d7882fb)
- [x] Cleaned up comment artifacts ("# Add this route to..." etc.) (d7882fb)
- [x] Removed "# ADD THESE THREE NEW FIELDS" comment in models.py (d7882fb)
- [x] Removed `test_scoresheet` debug route from bp_scoring.py (d7882fb)

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

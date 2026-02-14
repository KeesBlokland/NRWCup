# NRW Cup - Open Tasks

## CRITICAL

- [x] Fix `get_log_files_info` missing function in bp_system.py — added function (ada347f)
- [x] Fix `all_round_objects` NameError in bp_formular.py when no active event (ada347f)
- [x] Round-dropping rule resolved — drop LOWEST is safe, drop HIGHEST is dangerous with missing scores. See README.md section 4 for explanation.

## TODO

- [ ] Email availability check: before sending, test if mail server is reachable (Pi runs standalone without internet). Disable/hide email buttons or show clear error when offline.
- [ ] User/Auth system: connect the vestigial User model to actual authentication, populate audit trail fields (`entered_by`/`changed_by`), enforce roles (Admin/Judge/User). See `doc_archives/user_auth_review.md` for full analysis.

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


## DONE (2026-02-12)

- [x] Protect completed events from clear_all_scores — Completed events are NEVER cleared
- [x] Add email recipient selection modals — all 3 email senders now require explicit recipient selection
- [x] Fix results email send button (DOMContentLoaded) — script ran before modal HTML existed
- [x] Restore 2025 scores from Pi backup (nrwcup_backup_2026-02-10_08-22-58.zip)
- [x] Document Pi deployment details in CLAUDE.md (path, credentials, commands)
- [x] Audit logging wired into scoring, contest, cleanup, system blueprints
- [x] Log file management: download, cleanup of startup-only logs
- [x] Full project backup (not just DB + app/)
- [x] Fix all paths to use PROJECT_ROOT instead of os.getcwd()

## DONE (earlier)

- [x] Clarify TaG: Touch and Go — dropped for 2025, no action needed
- [x] Verify Kürfiguren: ONE per group (Platzrunde: M or M-K; Platzüberflug: Kreis or Oval)
- [x] Validate scoring calculations: full verification completed, all 39 scores match
- [x] Fix Messwertung averaging bug: confirmed fixed in current code
- [x] Standardize button/badge sizes across all templates
- [x] Auto-detect database path in app_main.py
- [x] Clean GitHub repo (password exposure)

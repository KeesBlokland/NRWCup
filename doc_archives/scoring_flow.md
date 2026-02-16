# Scoring Data Flow — Design Document

## Overview

The scoring system handles entry of judge scoresheets for model aircraft competitions.
Each team flies a round, and 3 judges independently score the flight on quality figures.
One judge (any of the three) also records objective measurements (Messwerte).

## Key Concepts

### Score Types
- **Qualitaetswertung** (quality scores): Subjective scores per judge (STRT, PLZU, AUSKL, etc.)
  - Averaged across judges in the final calculation
- **Messwertung** (measurement scores): Objective values entered once, shared across all judges
  - Codes: `SEGZEIT`, `LANDGM`, `LANS`, `SEILZ`
  - Added directly to the total (not averaged)
  - Entered by whichever judge happens to sit at the 0-line — there is NO fixed "center judge"

### Final Score Formula
```
Punkte = (avg of Judge1 + Judge2 + Judge3 quality scores) + Messwerte
```
Per the official Ausschreibung: quality scores are averaged, Messwerte are added once.

## Database Structure

```
Event → Round → TeamRound → Score → ScoreValue
                               ↑         ↑
                            per judge   per figure (task_type)
```

- **TeamRound**: one per team per round (e.g. Team 1 in Round 1)
- **Score**: one per judge per TeamRound (3 judges = 3 Score records)
- **ScoreValue**: one per figure per Score (quality figures + Messwerte)

## Data Lifecycle

### 1. Round Preparation (`generate_scoresheets_for_round`)
File: `app/routes/bp_formular.py`

When a round is started:
1. Creates `TeamRound` records for all active teams
2. Creates **empty** `Score` records for every team x judge combination
3. No `ScoreValue` records yet — those come from data entry

This means all Score records exist BEFORE anyone enters data. This is critical for
replication to work (it needs target Score records to copy Messwerte into).

**WARNING**: This function wipes and recreates everything for the round. Never call it
on a round that already has data.

### 2. Data Entry (`create_score`)
File: `app/services/services_scoring.py`

When a judge's scoresheet is entered (real form or test generator):
1. Finds the existing Score record (created in step 1) by team_round_id + judge_id
2. Deletes existing non-Messwerte ScoreValues on that Score
   - If the submission INCLUDES Messwerte codes → deletes ALL ScoreValues (full replace)
   - If the submission does NOT include Messwerte → preserves replicated Messwerte
3. Creates new ScoreValues from the submitted data
4. Commits
5. Calls `replicate_messwertung_values()` (see below)
6. Calls `update_team_round_scores()` to recalculate totals

### 3. Messwertung Replication (`replicate_messwertung_values`)
File: `app/services/services_scoring.py`

After every score save:
1. Checks if the saved Score has any Messwertung ScoreValues (SEGZEIT/LANDGM/LANS/SEILZ)
2. If none → returns (nothing to replicate)
3. Finds all OTHER Score records for the same TeamRound
4. For each: deletes their Messwertung ScoreValues, creates new ones with the source values
5. Commits

This ensures all judges' scoresheets show the same Messwerte, regardless of who entered them.

### 4. Score Aggregation (`aggregate_judge_scores`)
File: `app/services/services_scoring.py`

When calculating the team's total for a round:
- Quality scores: collected per figure, averaged across judges
- Messwerte: takes the non-zero value (should be identical across judges after replication)
- SEGZEIT has special calculation: `max(0, 300 - abs(200 - time) * 3)`

## Critical Rules

1. **Once entered, a judge's quality scores are NEVER modified by entering another judge's data.**
   `create_score()` only touches the Score record for the specific judge_id it's called with.

2. **Messwerte are entered once and replicated.** They are NOT re-entered per judge.
   Replication copies them to all other judges' Score records automatically.

3. **`create_score()` preserves replicated Messwerte.** When a judge's quality scores are
   entered without Messwerte, the existing replicated Messwerte on that Score are kept intact.

4. **`generate_scoresheets_for_round()` is destructive.** It wipes all data for the round
   and recreates from scratch. Only call it on rounds with no existing data.

## Test Data Generator
File: `app/routes/bp_testdata.py`

The test generator follows the exact same code path as real data entry:
1. Calls `generate_scoresheets_for_round()` ONLY if the round has no TeamRound records yet
2. For each selected judge, calls `create_score()` with generated values
3. Messwerte are generated once (on the first judge in the selection) and only if no
   Messwerte exist yet for that TeamRound — never overwrites existing Messwerte
4. Judges can be added incrementally (generate judge 1, then judge 2, then judge 3)
   without losing any previously entered data

## Display

- On the scoresheet form, Messwerte that were replicated (not originally entered on this
  sheet) are shown with a light blue background as visual indicator
- The `is_messwertung_owner` flag determines this: the first Score by ID for a TeamRound
  is considered the "owner" — purely visual, no functional difference
- All Messwerte fields remain editable on all sheets — correcting a value and saving
  triggers replication to update all other judges

## Event Status Protection

- **Pending**: test data, can be cleared entirely
- **Active**: competition running, scores can be entered
- **Completed**: locked, no changes allowed
- **Published**: locked + visible to public

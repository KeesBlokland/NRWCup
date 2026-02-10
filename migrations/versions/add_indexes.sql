CREATE INDEX IF NOT EXISTS idx_team_round_lookup ON team_rounds(round_id, team_id);
CREATE INDEX IF NOT EXISTS idx_score_lookup ON scores(team_round_id, judge_id);
CREATE INDEX IF NOT EXISTS idx_score_judge ON scores(judge_id);

"""
File: app/services/services_scoring.py
Version: 2.3.1
Created: 2025-03-26
Updated: 2026-04-16
Description: Scoring service with Messwertung/Qualitätswertung separation
"""

from sqlalchemy import or_
from app.models import db, Score, TaskType, TeamRound, Teilnehmer, Team, Round, Event, ScoreValue, SystemConfig
from app.services.base_service import BaseService
from datetime import datetime
import logging
import json
import math

logger = logging.getLogger(__name__)

class ScoringService(BaseService):
    """Service for scoring operations"""
    
    def __init__(self):
        super().__init__(Score)
    
    def get_active_figures(self):
        """
        Get all active scoring figures ordered by sort order.
        
        Returns:
            List of TaskType instances
        """
        return TaskType.query.filter_by(is_active=True).order_by(TaskType.sort_order).all()
    
    def get_judges(self, limit=None):
        """
        Get judges, optionally limited to first N (for event-specific num_judges).

        Returns:
            List of Teilnehmer instances who are judges
        """
        all_judges = Teilnehmer.query.filter_by(is_punktwerter=True).order_by(Teilnehmer.name).all()
        if limit and limit < len(all_judges):
            return all_judges[:limit]
        return all_judges
    
    def get_active_round(self):
        """
        Get the currently active round.
        
        Returns:
            Active Round instance or None
        """
        return Round.query.filter_by(status='Active').first()
    
    def get_scores_by_filters(self, round_id=None, judge_id=None):
        """
        Get scores filtered by round and/or judge.
        
        Args:
            round_id: Optional Round ID to filter by
            judge_id: Optional Judge ID to filter by
            
        Returns:
            List of Score instances
        """
        query = self.model_class.query
        
        if round_id:
            query = query.join(TeamRound).filter(TeamRound.round_id == round_id)
        
        if judge_id:
            query = query.filter(self.model_class.judge_id == judge_id)
            
        return query.all()
    
    def create_score(self, team_round_id, judge_id, score_values, notes=""):
        """Create a new score entry"""
        # Check if this combination already has a score
        existing = self.model_class.query.filter_by(
            team_round_id=team_round_id,
            judge_id=judge_id
        ).first()

        if existing:
            score = existing
            # Only delete ScoreValues for codes being submitted now.
            # Previously saved scores for fields left empty are preserved.
            submitted_codes = [c for c, v in score_values.items()
                               if v is not None and v != '']
            if submitted_codes:
                submitted_type_ids = [t.type_id for t in TaskType.query.filter(
                    TaskType.code.in_(submitted_codes)).all()]
                ScoreValue.query.filter(
                    ScoreValue.score_id == score.score_id,
                    ScoreValue.task_type_id.in_(submitted_type_ids)
                ).delete(synchronize_session='fetch')
        else:
            # Create new score
            score = self.model_class(
                team_round_id=team_round_id,
                judge_id=judge_id
            )
            db.session.add(score)
            db.session.flush()  # Get ID without committing yet

        # Update metadata
        score.entered_at = datetime.utcnow()
        score.notes = notes

        # Create score values
        for code, value in score_values.items():
            if value is None or value == '':
                continue

            # Find TaskType for this code
            task_type = TaskType.query.filter_by(code=code).first()
            if not task_type:
                continue

            try:
                # Convert value to appropriate type
                if task_type.score_type == 'float':
                    converted_value = float(value)
                else:
                    converted_value = int(value)

                # Create score value
                score_value = ScoreValue(
                    score_id=score.score_id,
                    task_type_id=task_type.type_id,
                    value=converted_value
                )
                db.session.add(score_value)

            except (ValueError, TypeError) as e:
                logger.error(f"Error converting value for {code}: {str(e)}")

        # Commit changes
        db.session.commit()

        # If judge 1 saved all zeros, replicate all scores to other judges
        first_score = Score.query.filter_by(team_round_id=team_round_id)\
            .order_by(Score.score_id).first()
        if first_score and first_score.score_id == score.score_id:
            all_values = ScoreValue.query.filter_by(score_id=score.score_id).all()
            if all_values and all(sv.value == 0 for sv in all_values):
                other_scores = Score.query.filter(
                    Score.team_round_id == team_round_id,
                    Score.score_id != score.score_id
                ).all()
                for other in other_scores:
                    ScoreValue.query.filter_by(score_id=other.score_id).delete(synchronize_session='fetch')
                    for sv in all_values:
                        db.session.add(ScoreValue(
                            score_id=other.score_id,
                            task_type_id=sv.task_type_id,
                            value=0
                        ))
                db.session.commit()
                logger.info(f"All-zero replication: copied zeros from score {score.score_id} to {len(other_scores)} other judges for team_round {team_round_id}")

        # Fix Kür mismatches: if judge 1 has chosen a variant, move any
        # conflicting entries on this score to the correct variant
        self.fix_kuer_mismatches(team_round_id, score.score_id)

        # Calculate and update raw score in team_round
        self.update_team_round_scores(team_round_id)

        return score

    def fix_kuer_mismatches(self, team_round_id, saved_score_id):
        """
        Fix Kür variant mismatches. The first judge (by score_id order) to enter
        a non-zero Kür value sets the chosen variant for the group. Any subsequent
        judge who scored the wrong variant gets their value moved to the correct one.
        """
        KUER_GROUPS = [
            ['PLTZR', 'PLTZR-M'],
            ['PLTZU', 'PLTZU-OV'],
        ]

        # Get all scores for this team_round, ordered by score_id (judge #1 first)
        all_scores = Score.query.filter_by(team_round_id=team_round_id)\
            .order_by(Score.score_id).all()
        if len(all_scores) < 2:
            return

        for group_codes in KUER_GROUPS:
            # Find the first score that has a non-zero choice for this group
            chosen_code = None
            authority_score_id = None
            for score in all_scores:
                for sv in score.values:
                    if sv.task_type and sv.task_type.code in group_codes:
                        if sv.value and sv.value > 0:
                            chosen_code = sv.task_type.code
                            authority_score_id = score.score_id
                            break
                if chosen_code:
                    break

            if not chosen_code:
                continue  # No one has chosen yet

            unchosen_codes = [c for c in group_codes if c != chosen_code]

            # Fix all OTHER scores that have the wrong variant
            for score in all_scores:
                if score.score_id == authority_score_id:
                    continue

                score_vals = {}
                for sv in score.values:
                    if sv.task_type and sv.task_type.code in group_codes:
                        score_vals[sv.task_type.code] = sv

                for wrong_code in unchosen_codes:
                    if wrong_code in score_vals and score_vals[wrong_code].value and score_vals[wrong_code].value > 0:
                        wrong_value = score_vals[wrong_code].value
                        logger.warning(
                            f"Kür mismatch: score {score.score_id} has {wrong_code}={wrong_value}, "
                            f"but {chosen_code} is the chosen variant. Moving value."
                        )

                        correct_type = TaskType.query.filter_by(code=chosen_code).first()
                        if not correct_type:
                            continue

                        # Move value to correct variant
                        existing_correct = ScoreValue.query.filter_by(
                            score_id=score.score_id,
                            task_type_id=correct_type.type_id
                        ).first()

                        if existing_correct:
                            if not existing_correct.value or existing_correct.value == 0:
                                existing_correct.value = wrong_value
                        else:
                            db.session.add(ScoreValue(
                                score_id=score.score_id,
                                task_type_id=correct_type.type_id,
                                value=wrong_value
                            ))

                        # Zero the wrong variant
                        score_vals[wrong_code].value = 0

        db.session.commit()

    def get_score_details(self, score_id):
        """
        Get detailed information about a score.
        
        Args:
            score_id: ID of the score
            
        Returns:
            Dict with score details
        """
        score = self.model_class.query.options(
            db.joinedload(Score.values).joinedload(ScoreValue.task_type)
        ).get(score_id)
        
        if not score:
            return None
            
        team_round = TeamRound.query.get(score.team_round_id)
        if not team_round:
            return None
            
        round_obj = Round.query.get(team_round.round_id)
        if not round_obj:
            return None
            
        team = Team.query.get(team_round.team_id)
        if not team:
            return None
            
        judge = Teilnehmer.query.get(score.judge_id)
        if not judge:
            return None
        
        # Get active figures
        active_figures = TaskType.query.filter_by(is_active=True).order_by(TaskType.sort_order).all()
        
        # Build a map of task_type codes to values
        value_map = {}
        for value in score.values:
            if value.task_type:
                value_map[value.task_type.code] = value.value
        
        # Build figures list with values
        figures = []
        for figure in active_figures:
            value = value_map.get(figure.code)
            figures.append({
                'code': figure.code,
                'name': figure.name_de,
                'value': value,
                'k_factor': figure.k_factor
            })
        
        return {
            'score_id': score.score_id,
            'round_id': round_obj.round_id,
            'round_number': round_obj.round_number,
            'team_id': team.team_id,
            'team_number': team.team_nummer,
            'judge_id': judge.teilnehmer_id,
            'judge_name': judge.name,
            'entered_at': score.entered_at.isoformat() if score.entered_at else None,
            'figures': figures
        }
    
    def aggregate_judge_scores(self, team_round_id):
        """
        Aggregate judge scores correctly separating Qualitaetswertung from Messwertung.

        Qualitaetswertung (subjective, 0-10 per judge):
          - Collect raw 0-10 values from each judge
          - Drop rule (2026 rules, page 8):
              3 judges -> no drop, average all
              4 judges -> drop the highest
              5 judges -> drop highest and lowest
          - Round average to 3 decimal places (commercial rounding)
          - Multiply by K-factor, round to whole integer Bewertungspunkte (commercial rounding)

        Messwertung (objective, stored directly on TeamRound):
          - SEGZEIT: MAX(0, 300 - 3 * CEIL(|t - 200|))
          - SEILZ / LANDGM / LANS: value IS the Bewertungspunkte
        """
        try:
            scores = Score.query.options(
                db.joinedload(Score.values).joinedload(ScoreValue.task_type)
            ).filter_by(team_round_id=team_round_id).all()

            if not scores:
                return 0

            # qualitaet_raw: {task_code: {'raws': [raw 0-10 per judge], 'k': k_factor}}
            qualitaet_raw = {}

            for score in scores:
                for sv in score.values:
                    if not sv.task_type or sv.value is None:
                        continue
                    if sv.task_type.is_messwertung:
                        continue  # Messwerte are now on TeamRound, not ScoreValues
                    code = sv.task_type.code
                    k = sv.task_type.k_factor or 1
                    if code not in qualitaet_raw:
                        qualitaet_raw[code] = {'raws': [], 'k': k}
                    qualitaet_raw[code]['raws'].append(sv.value)

            total_score = 0

            # --- Messwertung (from TeamRound columns) ---
            team_round = TeamRound.query.get(team_round_id)
            if team_round:
                if team_round.mess_segzeit is not None:
                    pts = max(0, 300 - 3 * math.ceil(abs(team_round.mess_segzeit - 200)))
                    total_score += pts
                    logger.debug("Messwertung SEGZEIT: %.1fs -> %d pts", team_round.mess_segzeit, pts)
                if team_round.mess_seilz is not None:
                    total_score += team_round.mess_seilz
                if team_round.mess_landgm is not None:
                    total_score += team_round.mess_landgm
                if team_round.mess_lans is not None:
                    total_score += team_round.mess_lans

            # --- Qualitaetswertung ---
            for code, data in qualitaet_raw.items():
                raws = data['raws']
                k = data['k']
                if not raws:
                    continue
                n = len(raws)
                if n >= 5:
                    filtered = sorted(raws)[1:-1]   # drop highest and lowest
                    drop_label = 'dropped highest+lowest'
                elif n == 4:
                    filtered = sorted(raws)[:-1]    # drop highest only
                    drop_label = 'dropped highest'
                else:
                    filtered = raws                  # 3 or fewer: no drop
                    drop_label = 'no drop'
                avg = sum(filtered) / len(filtered)
                avg_r = math.floor(avg * 1000 + 0.5) / 1000  # commercial rounding to 3 decimals
                figure_pts = math.floor(avg_r * k + 0.5)     # commercial rounding to integer
                total_score += figure_pts
                logger.debug(
                    "Qualitaetswertung %s: raw=%s %s -> avg=%.3f *%d -> %d pts",
                    code, raws, drop_label, avg_r, k, figure_pts
                )

            logger.info("Team round %s total score: %s", team_round_id, total_score)
            return total_score

        except Exception as e:
            logger.error("Error aggregating scores for team_round %s: %s", team_round_id, str(e))
            return 0

        
    
    def normalize_round_scores(self, round_id):
        """
        Normalize scores to 1000-point scale for a round.
        
        Args:
            round_id: Round ID
            
        Returns:
            Dict of team_id to normalized score
        """
        # Initialize raw_scores first to avoid 'raw_scores is undefined' error
        raw_scores = {}
        
        team_rounds = TeamRound.query.filter_by(round_id=round_id).all()
        if not team_rounds:
            return {}
            
        # Calculate raw scores for all teams
        for team_round in team_rounds:
            team_id = team_round.team_id
            raw_score = self.aggregate_judge_scores(team_round.team_round_id)
            if raw_score is not None:  # Only include non-None scores
                raw_scores[team_id] = raw_score
            
        # Check if raw_scores has any values
        if not raw_scores:
            return {}
            
        # Find highest score for normalization - filter out None values
        valid_scores = [score for score in raw_scores.values() if score is not None]
        if not valid_scores:
            return {}
            
        highest_score = max(valid_scores)
        if highest_score == 0:
            return {}
            
        # Calculate normalized scores (0-1000 scale, divide by 10 for percentage display)
        normalized_scores = {}
        for team_id, raw_score in raw_scores.items():
            if raw_score is not None:
                normalized_scores[team_id] = (raw_score / highest_score) * 1000

        return normalized_scores
    
    def calculate_final_standings(self, event_id):
        """
        Calculate final standings with dropped rounds based on specified rules:
        - When there are 3+ rounds, drop the lowest-scoring round
        - When there are only 1-2 rounds, all rounds are counted
        - Final score is the sum of the remaining rounds (not average)
        
        Args:
            event_id: Event ID
            
        Returns:
            List of final standings
        """
        # Get rounds for this event that have actual team_rounds
        rounds_with_data = []
        all_rounds = Round.query.filter_by(event_id=event_id).all()
        
        for round_obj in all_rounds:
            team_rounds = TeamRound.query.filter_by(round_id=round_obj.round_id).all()
            # Only include rounds that have at least one score
            has_scores = False
            for team_round in team_rounds:
                if Score.query.filter_by(team_round_id=team_round.team_round_id).first():
                    has_scores = True
                    break
            
            if has_scores:
                rounds_with_data.append(round_obj)
        
        if not rounds_with_data:
            return [], []
        
        # Sort rounds by round_number to ensure consistent order
        rounds_with_data.sort(key=lambda r: r.round_number)
            
        # Get all teams that participated
        teams = {}  # team_id -> team data
        for round_obj in rounds_with_data:
            team_rounds = TeamRound.query.filter_by(round_id=round_obj.round_id).all()
            for team_round in team_rounds:
                team_id = team_round.team_id
                if team_id not in teams:
                    teams[team_id] = Team.query.get(team_id)
        
        # Calculate normalized scores for each round
        round_scores = {}  # team_id -> [round scores]
        
        # First initialize with empty scores for all teams
        for team_id in teams:
            round_scores[team_id] = [0] * len(rounds_with_data)
        
        # Then fill in actual scores
        for i, round_obj in enumerate(rounds_with_data):
            normalized_scores = self.normalize_round_scores(round_obj.round_id)
            for team_id, score in normalized_scores.items():
                if team_id in round_scores:
                    round_scores[team_id][i] = score
        
        # Read drop threshold from SystemConfig (default 3)
        threshold_config = SystemConfig.query.filter_by(config_key='drop_worst_round_threshold').first()
        drop_threshold = int(threshold_config.config_value) if threshold_config else 3

        # Apply final scoring rules
        final_scores = {}
        for team_id, scores in round_scores.items():
            # Apply dropping rules based on number of rounds
            if len(scores) >= drop_threshold:
                # For rounds >= threshold, drop the lowest score
                temp_scores = scores.copy()
                min_score = min(temp_scores)
                min_index = temp_scores.index(min_score)
                dropped_indices = [min_index]
                
                # FIXED: Calculate final score excluding dropped rounds
                final_score = 0
                for i, score in enumerate(scores):
                    if i not in dropped_indices:
                        final_score += score
                
                final_scores[team_id] = {
                    'score': final_score,
                    'round_scores': scores,
                    'dropped_indices': dropped_indices,
                    'streicher': scores[min_index]
                }
            else:
                # Below threshold — count all rounds
                final_scores[team_id] = {
                    'score': sum(scores),
                    'round_scores': scores,
                    'dropped_indices': [],
                    'streicher': 0
                }

        # Generate final standings
        standings = []
        for team_id, data in final_scores.items():
            standings.append({
                'team': teams[team_id],
                'score': data['score'],
                'round_scores': data['round_scores'],
                'dropped_indices': data['dropped_indices'],
                'streicher': data['streicher']
            })

        # Sort by Endstand, tiebreaker = Streicher (higher wins) per BeMod-F-Schlepp 2026 section K
        standings.sort(key=lambda x: (x['score'], x['streicher']), reverse=True)
        
        # Add rank
        for i, standing in enumerate(standings, 1):
            standing['rank'] = i
        
        # Endstand IS the sum of Promille-Punkte -- no further normalization
        # With 4 rounds (drop worst): max = 3000 (3 x 1000), with 3 rounds: max = 2000
        return standings, rounds_with_data
    
    def calculate_seglerzeit(self, actual_time):
        """
        Calculate points for glider time (2026 rules):
        MAX(0, 300 - 3 * CEIL(ABS(actual_time - 200)))
        Target is 200 seconds = 300 points, -3 points per started second of deviation.

        Args:
            actual_time: Actual time in seconds

        Returns:
            Calculated points (integer 0-300)
        """
        if actual_time is None:
            return 0
        return max(0, 300 - 3 * math.ceil(abs(actual_time - 200)))
    
    def update_team_round_scores(self, team_round_id):
        """Update the raw and normalized scores for a team round"""
        team_round = TeamRound.query.get(team_round_id)
        if not team_round:
            return
        
        # Calculate raw score
        raw_score = self.aggregate_judge_scores(team_round_id)
        team_round.raw_score = raw_score
        
        # Get all team rounds for this round to calculate normalized scores
        round_id = team_round.round_id
        all_team_rounds = TeamRound.query.filter_by(round_id=round_id).all()
        
        # Find highest raw score for normalization
        highest_score = 0
        for tr in all_team_rounds:
            if tr.raw_score and tr.raw_score > highest_score:
                highest_score = tr.raw_score
        
        # Update normalized scores and ranks
        if highest_score > 0:
            # First update the current team's normalized score
            team_round.normalized_score = (raw_score / highest_score) * 1000
            
            # Now update all scores and recalculate ranks
            scored_team_rounds = [tr for tr in all_team_rounds if tr.raw_score is not None]
            scored_team_rounds.sort(key=lambda tr: tr.raw_score, reverse=True)
            
            for rank, tr in enumerate(scored_team_rounds, 1):
                tr.rank = rank
                # Also update normalized score for other teams
                if tr.team_round_id != team_round_id:
                    tr.normalized_score = (tr.raw_score / highest_score) * 1000
        
        db.session.commit()
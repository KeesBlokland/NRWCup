"""
File: app/services/services_scoring.py
Version: 2.3.0
Created: 2025-03-26
Updated: 2025-04-19
Description: Scoring service with Messwertung/Qualitätswertung separation
"""

from sqlalchemy import or_
from app.models import db, Score, TaskType, TeamRound, Teilnehmer, Team, Round, Event, ScoreValue
from app.utils.utils_base_service import BaseService
from datetime import datetime
import logging
import json

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
    
    def get_judges(self):
        """
        Get all judges.
        
        Returns:
            List of Teilnehmer instances who are judges
        """
        return Teilnehmer.query.filter_by(is_punktwerter=True).order_by(Teilnehmer.name).all()
    
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
            # Update existing score
            score = existing
            # Delete existing score values
            ScoreValue.query.filter_by(score_id=score.score_id).delete()
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
        
        # Calculate and update raw score in team_round
        self.update_team_round_scores(team_round_id)
        
        return score

    
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
        Aggregate judge scores correctly separating Qualitätswertung from Messwertung
        
        Qualitätswertung (subjective): Average across judges
        Messwertung (objective): Add directly without averaging
        """
        try:
            # Get all scores for this team round
            scores = Score.query.options(
                db.joinedload(Score.values).joinedload(ScoreValue.task_type)
            ).filter_by(team_round_id=team_round_id).all()
            
            if not scores:
                return 0
            
            # Define which task types are Messwertung (objective measurements by measurement team)
            messwertung_codes = {
                'LANDGM',    # Genauigkeit der Landung (landing accuracy)
                'LANS',      # Landing accuracy measurements  
                'SEILZ',     # Seilabwurf (rope drop precision)
                'SEGZEIT',   # Flugzeit (flight time - 2 stopwatches)
            }
            
            # Separate scores by task type and judge
            qualitaet_scores = {}  # {task_code: [judge1_score, judge2_score, ...]}
            messwertung_scores = {}  # {task_code: [all values from all judges]}

            for score in scores:
                for score_value in score.values:
                    if not score_value.task_type or score_value.value is None:
                        continue

                    task_code = score_value.task_type.code

                    # Calculate the points for this score value
                    if task_code == 'SEGZEIT':
                        # Special calculation for Seglerzeit
                        target_time = 200
                        max_points = 300
                        penalty_factor = 3
                        time_diff = abs(target_time - score_value.value)
                        points = max(0, max_points - (time_diff * penalty_factor))
                    else:
                        # Standard calculation
                        k_factor = score_value.task_type.k_factor or 1
                        points = score_value.value * k_factor

                    if task_code in messwertung_codes:
                        # Messwertung: collect from ALL judges, we'll pick the right one below
                        if task_code not in messwertung_scores:
                            messwertung_scores[task_code] = []
                        messwertung_scores[task_code].append(points)
                    else:
                        # Qualitätswertung: Collect for averaging (subjective scores)
                        if task_code not in qualitaet_scores:
                            qualitaet_scores[task_code] = []
                        qualitaet_scores[task_code].append(points)

            # Calculate final score
            total_score = 0

            # Add Messwertung scores directly (no averaging)
            # Only ONE judge enters these — use the non-zero value from whichever judge has it.
            # If all judges have 0, the result is 0 (genuine zero score).
            for task_code, values in messwertung_scores.items():
                non_zero = [v for v in values if v != 0]
                if non_zero:
                    # Use the non-zero value (should be exactly one judge)
                    chosen = non_zero[0]
                    if len(non_zero) > 1:
                        logger.warning(f"Messwertung {task_code}: multiple non-zero values {non_zero}, using first")
                else:
                    chosen = 0
                total_score += chosen
                logger.debug(f"Messwertung {task_code}: candidates={values} -> used {chosen}")
            
            # Average Qualitätswertung scores and add
            for task_code, judge_scores in qualitaet_scores.items():
                if judge_scores:
                    # Apply dropping rule for 4+ judges
                    if len(judge_scores) >= 4:
                        # Drop lowest score
                        judge_scores_filtered = sorted(judge_scores)[1:]
                        avg_score = sum(judge_scores_filtered) / len(judge_scores_filtered)
                        logger.debug(f"Qualitätswertung {task_code}: {judge_scores} -> dropped lowest -> {judge_scores_filtered} -> avg: {avg_score}")
                    else:
                        # Simple average for 3 or fewer judges
                        avg_score = sum(judge_scores) / len(judge_scores)
                        logger.debug(f"Qualitätswertung {task_code}: {judge_scores} -> avg: {avg_score}")
                    
                    total_score += avg_score
            
            logger.info(f"Team round {team_round_id} total score: {total_score}")
            return total_score
            
        except Exception as e:
            logger.error(f"Error aggregating scores for team_round {team_round_id}: {str(e)}")
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
            return []
        
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
        
        # Apply final scoring rules
        final_scores = {}
        for team_id, scores in round_scores.items():
            # Apply dropping rules based on number of rounds
            if len(scores) >= 3:
                # For 3+ rounds, drop the lowest score
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
                    'dropped_indices': dropped_indices
                }
            else:
                # For 1-2 rounds, count all rounds
                final_scores[team_id] = {
                    'score': sum(scores),
                    'round_scores': scores,
                    'dropped_indices': []
                }
        
        # Generate final standings
        standings = []
        for team_id, data in final_scores.items():
            standings.append({
                'team': teams[team_id],
                'score': data['score'],
                'round_scores': data['round_scores'],
                'dropped_indices': data['dropped_indices']
            })
        
        # Sort by score (descending)
        standings.sort(key=lambda x: x['score'], reverse=True)
        
        # Add rank
        for i, standing in enumerate(standings, 1):
            standing['rank'] = i
        
        # Endstand IS the sum of percentages — no further normalization
        # With 4 rounds: max = 300 (3 × 100%), with 3 rounds: max = 200 (2 × 100%)
        return standings, rounds_with_data
    
    def calculate_seglerzeit(self, actual_time, target_time=200, max_points=300, penalty_factor=3):
        """
        Calculate points for glider time:
        MAX(0, 300 - (ABS(200-actual_time) * 3))
        
        Args:
            actual_time: Actual time in seconds
            target_time: Target time in seconds (default: 200)
            max_points: Maximum points (default: 300)
            penalty_factor: Penalty factor (default: 3)
            
        Returns:
            Calculated points
        """
        if actual_time is None:
            return 0
            
        time_diff = abs(target_time - actual_time) 
        points = max(0, max_points - (time_diff * penalty_factor))
        return points
    
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
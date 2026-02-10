"""
File: app/services/rule_engine.py
Version: 1.0.0
Created: 2025-03-02
Description: Engine for processing scoring rules based on configuration
"""

from app.models import db, ScoringRuleSet, ScoringRule, TeamRound, Score, CompetitionScore
from sqlalchemy.exc import SQLAlchemyError
import json
import logging

# Configure logger
logger = logging.getLogger(__name__)

class RuleEngine:
    """Engine for processing scoring rules based on configuration"""
    
    def __init__(self, rule_set_id=None):
        """
        Initialize the rule engine with a rule set.
        
        Args:
            rule_set_id: ID of the rule set or None to use active rule set
        """
        if rule_set_id:
            self.rule_set = ScoringRuleSet.query.get(rule_set_id)
        else:
            # Get active rule set
            self.rule_set = ScoringRuleSet.query.filter_by(is_active=True).first()
            
        if not self.rule_set:
            raise ValueError("No active rule set found")
            
        # Load rules
        self.rules = sorted(self.rule_set.rules, key=lambda r: r.order)
        logger.info(f"Initialized RuleEngine with rule set '{self.rule_set.name}' ({len(self.rules)} rules)")
        
    def process_round(self, round_id):
        """
        Process all scores for a round using the configured rules.
        
        Args:
            round_id: ID of the round to process
            
        Returns:
            Dict with processing results and normalized scores
        """
        result_log = []
        
        # Get all team rounds for this round
        team_rounds = TeamRound.query.filter_by(round_id=round_id).all()
        if not team_rounds:
            logger.warning(f"No team rounds found for round ID {round_id}")
            return {'status': 'error', 'message': 'No team rounds found'}
            
        logger.info(f"Processing {len(team_rounds)} team rounds for round ID {round_id}")
        
        try:
            # Process each rule in sequence
            raw_scores = {}
            normalized_scores = {}
            
            # First collect all raw scores
            for team_round in team_rounds:
                team_id = team_round.team_id
                raw_scores[team_id] = self._calculate_raw_score(team_round.team_round_id)
                
            # Process judge averaging rule
            judge_averaging_rule = self._find_rule_by_type('judge_averaging')
            if judge_averaging_rule:
                logger.info("Applying judge averaging rule")
                avg_scores = self._apply_judge_averaging(raw_scores, json.loads(judge_averaging_rule.parameters))
                result_log.append({
                    'rule_type': 'judge_averaging',
                    'parameters': json.loads(judge_averaging_rule.parameters),
                    'result': avg_scores
                })
            else:
                avg_scores = raw_scores
            
            # Process normalization rule
            normalization_rule = self._find_rule_by_type('normalization')
            if normalization_rule:
                logger.info("Applying normalization rule")
                normalized_scores = self._apply_normalization(avg_scores, json.loads(normalization_rule.parameters))
                result_log.append({
                    'rule_type': 'normalization',
                    'parameters': json.loads(normalization_rule.parameters),
                    'result': normalized_scores
                })
            else:
                normalized_scores = avg_scores
                
            # Save normalized scores to the database
            self._save_competition_scores(round_id, normalized_scores, raw_scores)
            
            return {
                'status': 'success',
                'log': result_log,
                'raw_scores': raw_scores,
                'normalized_scores': normalized_scores
            }
            
        except Exception as e:
            logger.error(f"Error processing round: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def process_event(self, event_id):
        """
        Process all rounds for an event and calculate final standings.
        
        Args:
            event_id: ID of the event to process
            
        Returns:
            Dict with final standings
        """
        from app.models import Round
        
        # Get all rounds for this event
        rounds = Round.query.filter_by(event_id=event_id).all()
        if not rounds:
            logger.warning(f"No rounds found for event ID {event_id}")
            return {'status': 'error', 'message': 'No rounds found'}
            
        logger.info(f"Processing {len(rounds)} rounds for event ID {event_id}")
        
        try:
            # Process each round
            for round_obj in rounds:
                self.process_round(round_obj.round_id)
                
            # Calculate final standings with round dropping
            final_standings = self._calculate_final_standings(event_id, rounds)
            
            return {
                'status': 'success',
                'final_standings': final_standings
            }
            
        except Exception as e:
            logger.error(f"Error processing event: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _calculate_raw_score(self, team_round_id):
        """
        Calculate raw score for a team round from judge scores.
        
        Args:
            team_round_id: ID of the team round
            
        Returns:
            Dict mapping judge_id to score
        """
        from app.models import Score, ScoreValue
        
        # Get all scores for this team round
        scores = Score.query.filter_by(team_round_id=team_round_id).all()
        
        # Calculate raw score for each judge
        judge_scores = {}
        for score in scores:
            judge_id = score.judge_id
            judge_scores[judge_id] = 0
            
            # Calculate sum of (value * k_factor) for all tasks
            score_values = ScoreValue.query.filter_by(score_id=score.score_id).all()
            for score_value in score_values:
                # Get task type for K-factor
                task_type = score_value.task_type
                if task_type:
                    k_factor = task_type.k_factor or 1
                    judge_scores[judge_id] += score_value.value * k_factor
                    
        return judge_scores
        
    def _apply_judge_averaging(self, raw_scores, params):
        """
        Apply judge averaging rule to raw scores.
        
        Args:
            raw_scores: Dict mapping team_id to dict of judge scores
            params: Rule parameters
            
        Returns:
            Dict mapping team_id to averaged score
        """
        min_judges = params.get('min_judges', 3)
        drop_lowest = params.get('drop_lowest', True)
        drop_highest = params.get('drop_highest', False)
        
        result = {}
        for team_id, judge_scores in raw_scores.items():
            # Skip if not enough judges
            if len(judge_scores) < min_judges:
                logger.warning(f"Team {team_id} has fewer than {min_judges} judges, using simple average")
                if judge_scores:
                    result[team_id] = sum(judge_scores.values()) / len(judge_scores)
                else:
                    result[team_id] = 0
                continue
                
            # Get all scores
            scores = list(judge_scores.values())
            
            # Apply dropping rules
            if drop_lowest and len(scores) > min_judges:
                scores.remove(min(scores))
                
            if drop_highest and len(scores) > min_judges:
                scores.remove(max(scores))
                
            # Calculate average
            if scores:
                result[team_id] = sum(scores) / len(scores)
            else:
                result[team_id] = 0
                
        return result
        
    def _apply_normalization(self, scores, params):
        """
        Apply normalization rule to scores.
        
        Args:
            scores: Dict mapping team_id to score
            params: Rule parameters
            
        Returns:
            Dict mapping team_id to normalized score
        """
        scale_factor = params.get('scale_factor', 1000)
        reference = params.get('reference', 'max')
        
        result = {}
        
        # Skip if no scores
        if not scores:
            return result
            
        # Get reference value
        if reference == 'max':
            reference_value = max(scores.values()) if scores else 1
        elif reference == 'avg':
            reference_value = sum(scores.values()) / len(scores) if scores else 1
        else:
            reference_value = 1
            
        # Avoid division by zero
        if reference_value == 0:
            reference_value = 1
            
        # Normalize scores
        for team_id, score in scores.items():
            result[team_id] = (score / reference_value) * scale_factor
            
        return result
        
    def _calculate_final_standings(self, event_id, rounds):
        """
        Calculate final standings with round dropping rule.
        
        Args:
            event_id: Event ID
            rounds: List of Round objects
            
        Returns:
            List of final standings
        """
        from app.models import CompetitionScore, Team
        
        # Get all teams that participated
        teams = {}
        for round_obj in rounds:
            for team_round in round_obj.team_rounds:
                team_id = team_round.team_id
                if team_id not in teams:
                    teams[team_id] = Team.query.get(team_id)
        
        # Get competition scores for all teams/rounds
        scores_query = CompetitionScore.query.filter_by(event_id=event_id).all()
        
        # Organize scores by team and round
        team_scores = {}
        for score in scores_query:
            team_id = score.team_id
            round_id = score.round_id
            
            if team_id not in team_scores:
                team_scores[team_id] = {}
                
            team_scores[team_id][round_id] = score.normalized_score
        
        # Apply round dropping rule
        drop_lowest_rule = self._find_rule_by_type('drop_lowest_round')
        drop_lowest = False
        min_rounds_required = 4
        
        if drop_lowest_rule:
            params = json.loads(drop_lowest_rule.parameters)
            drop_lowest = True
            min_rounds_required = params.get('min_rounds_required', 4)
        
        # Calculate final scores
        final_scores = {}
        for team_id, scores in team_scores.items():
            round_scores = list(scores.values())
            
            # Apply round dropping if enabled and enough rounds
            if drop_lowest and len(round_scores) >= min_rounds_required:
                # Mark lowest score as dropped in database
                self._mark_lowest_score_as_dropped(event_id, team_id)
                
                # Drop lowest score for final calculation
                if round_scores:
                    min_score = min(round_scores)
                    round_scores.remove(min_score)
            
            # Calculate average of remaining rounds
            if round_scores:
                final_scores[team_id] = sum(round_scores) / len(round_scores)
            else:
                final_scores[team_id] = 0
        
        # Create final standings list
        standings = []
        for team_id, score in final_scores.items():
            if team_id in teams:
                standings.append({
                    'team': teams[team_id],
                    'score': score,
                    'round_scores': list(team_scores.get(team_id, {}).values())
                })
        
        # Sort by score (descending)
        standings.sort(key=lambda x: x['score'], reverse=True)
        
        # Add rank
        for i, standing in enumerate(standings):
            standing['rank'] = i + 1
            
        return standings
        
    def _mark_lowest_score_as_dropped(self, event_id, team_id):
        """
        Mark the lowest score for a team as dropped.
        
        Args:
            event_id: Event ID
            team_id: Team ID
        """
        # Get all competition scores for this team/event
        scores = CompetitionScore.query.filter_by(
            event_id=event_id,
            team_id=team_id
        ).all()
        
        # Find the lowest score
        lowest_score = None
        for score in scores:
            if lowest_score is None or score.normalized_score < lowest_score.normalized_score:
                lowest_score = score
        
        # Mark as dropped
        if lowest_score:
            lowest_score.is_dropped = True
            db.session.commit()
            
    def _save_competition_scores(self, round_id, normalized_scores, raw_scores):
        """
        Save normalized scores to the CompetitionScore table.
        
        Args:
            round_id: Round ID
            normalized_scores: Dict mapping team_id to normalized score
            raw_scores: Dict mapping team_id to raw score
        """
        from app.models import Round, CompetitionScore
        
        # Get the round to get the event_id
        round_obj = Round.query.get(round_id)
        if not round_obj:
            logger.error(f"Round {round_id} not found")
            return
            
        event_id = round_obj.event_id
        
        # Delete existing scores for this round
        CompetitionScore.query.filter_by(round_id=round_id).delete()
        
        # Save new scores
        for team_id, normalized_score in normalized_scores.items():
            # Calculate raw total from judge scores
            raw_total = 0
            team_raw_scores = raw_scores.get(team_id, {})
            if team_raw_scores:
                raw_total = sum(team_raw_scores.values()) / len(team_raw_scores)
            
            # Create new competition score
            comp_score = CompetitionScore(
                event_id=event_id,
                round_id=round_id,
                team_id=team_id,
                raw_total=raw_total,
                normalized_score=normalized_score,
                is_dropped=False
            )
            db.session.add(comp_score)
            
        # Calculate round ranks
        self._calculate_round_ranks(round_id)
        
        db.session.commit()
        
    def _calculate_round_ranks(self, round_id):
        """
        Calculate and save ranks for a round.
        
        Args:
            round_id: Round ID
        """
        # Get all scores for this round, ordered by normalized score
        scores = CompetitionScore.query.filter_by(round_id=round_id)\
            .order_by(CompetitionScore.normalized_score.desc())\
            .all()
            
        # Assign ranks
        for i, score in enumerate(scores):
            score.round_rank = i + 1
    
    def _find_rule_by_type(self, rule_type):
        """
        Find a rule by its type.
        
        Args:
            rule_type: Rule type to find
            
        Returns:
            ScoringRule instance or None
        """
        for rule in self.rules:
            if rule.rule_type == rule_type:
                return rule
        return None
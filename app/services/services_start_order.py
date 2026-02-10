"""
File: app/services/services_start_order.py
Version: 1.0.0
Created: 2025-04-05
Description: Service for managing start orders for competition rounds
"""

from app.models import db, Event, Round, Team, TeamRound
from app.utils.utils_base_service import BaseService
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

class StartOrderService(BaseService):
    """Service for managing start orders"""
    
    def __init__(self):
        # Don't initialize with a model since we're working with multiple models
        pass
    
    def get_rounds_for_event(self, event_id):
        """
        Get all rounds for an event in order.
        
        Args:
            event_id: Event ID
            
        Returns:
            List of Round instances
        """
        return Round.query.filter_by(event_id=event_id).order_by(Round.round_number).all()
    
    def get_team_start_order_for_round(self, round_id):
        """
        Get the team start order for a specific round.
        
        Args:
            round_id: Round ID
            
        Returns:
            List of dict with team and start_order
        """
        team_rounds = TeamRound.query.filter_by(round_id=round_id)\
            .order_by(TeamRound.start_order)\
            .all()
            
        result = []
        for team_round in team_rounds:
            team = Team.query.get(team_round.team_id)
            if team:
                result.append({
                    'team': team,
                    'start_order': team_round.start_order
                })
        
        return result
    
    def generate_start_order_from_scores(self, prev_round_id, target_round_id):
        """
        Generate start order for a target round based on previous round scores.
        Teams with lower scores start first.
        
        Args:
            prev_round_id: Previous round ID to use for scores
            target_round_id: Target round ID to update start orders
            
        Returns:
            Dict with success status and message
        """
        try:
            # Get all team rounds with scores from previous round
            prev_team_rounds = TeamRound.query.filter_by(round_id=prev_round_id)\
                .filter(TeamRound.raw_score != None)\
                .order_by(TeamRound.raw_score)\
                .all()
                
            if not prev_team_rounds:
                return {
                    'success': False, 
                    'message': 'No scores found for the previous round'
                }
            
            # Get the target round
            target_round = Round.query.get(target_round_id)
            if not target_round:
                return {
                    'success': False, 
                    'message': 'Target round not found'
                }
            
            # Clear any existing team rounds for the target round
            TeamRound.query.filter_by(round_id=target_round_id).delete()
            
            # Create new team rounds with updated start order
            for start_pos, team_round in enumerate(prev_team_rounds, 1):
                # Create or update team round
                new_team_round = TeamRound(
                    round_id=target_round_id,
                    team_id=team_round.team_id,
                    start_order=start_pos,
                    status='Pending'
                )
                db.session.add(new_team_round)
            
            # Also add any active teams that weren't in the previous round
            active_teams = Team.query.filter_by(status='active').all()
            teams_added = set(tr.team_id for tr in prev_team_rounds)
            
            start_pos = len(prev_team_rounds) + 1
            for team in active_teams:
                if team.team_id not in teams_added:
                    new_team_round = TeamRound(
                        round_id=target_round_id,
                        team_id=team.team_id,
                        start_order=start_pos,
                        status='Pending'
                    )
                    db.session.add(new_team_round)
                    start_pos += 1
            
            db.session.commit()
            
            return {
                'success': True,
                'message': f'Start order for round {target_round.round_number} generated based on round scores'
            }
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error in generate_start_order: {str(e)}")
            return {
                'success': False,
                'message': f'Database error: {str(e)}'
            }
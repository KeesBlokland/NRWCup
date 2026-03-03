"""
File: app/services/services_start_order.py
Version: 1.0.0
Created: 2025-04-05
Description: Service for managing start orders for competition rounds
"""

from app.models import db, Event, Round, Team, TeamRound
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

class StartOrderService:
    """Service for managing start orders"""
    
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
    
    def generate_start_order_from_scores(self, event_id, target_round_id):
        """
        Generate start order for a target round based on cumulative overall standings
        (sum of normalized_scores from all completed rounds before this one).
        Teams with lowest cumulative score start first (worst team first).

        Args:
            event_id: Event ID
            target_round_id: Target round ID to update start orders

        Returns:
            Dict with success status and message
        """
        try:
            # Get the target round
            target_round = Round.query.get(target_round_id)
            if not target_round:
                return {
                    'success': False,
                    'message': 'Target round not found'
                }

            # Get all completed rounds before the target round
            completed_rounds = Round.query.filter(
                Round.event_id == event_id,
                Round.round_number < target_round.round_number,
                Round.status == 'Completed'
            ).all()

            if not completed_rounds:
                return {
                    'success': False,
                    'message': 'Keine abgeschlossenen Durchgänge gefunden'
                }

            # Sum normalized_scores per team across all completed rounds
            team_totals = {}  # team_id -> cumulative normalized score
            for round_obj in completed_rounds:
                team_rounds = TeamRound.query.filter_by(round_id=round_obj.round_id)\
                    .filter(TeamRound.normalized_score != None).all()
                for tr in team_rounds:
                    team_totals[tr.team_id] = team_totals.get(tr.team_id, 0.0) + tr.normalized_score

            if not team_totals:
                return {
                    'success': False,
                    'message': 'Keine Normalisierungswerte gefunden — Durchgänge müssen abgeschlossen sein'
                }

            # Sort ascending: lowest cumulative score starts first
            sorted_teams = sorted(team_totals.items(), key=lambda x: x[1])

            # Clear any existing team rounds for the target round
            TeamRound.query.filter_by(round_id=target_round_id).delete()

            # Create new team rounds with updated start order
            teams_added = set()
            for start_pos, (team_id, _) in enumerate(sorted_teams, 1):
                new_team_round = TeamRound(
                    round_id=target_round_id,
                    team_id=team_id,
                    start_order=start_pos,
                    status='Pending'
                )
                db.session.add(new_team_round)
                teams_added.add(team_id)

            # Also add any active teams not yet scored (append at end)
            active_teams = Team.query.filter_by(status='active').all()
            start_pos = len(sorted_teams) + 1
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
                'message': f'Startfolge für Durchgang {target_round.round_number} nach Gesamtwertung generiert'
            }
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error in generate_start_order: {str(e)}")
            return {
                'success': False,
                'message': f'Database error: {str(e)}'
            }
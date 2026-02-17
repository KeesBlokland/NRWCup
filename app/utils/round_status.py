# Helper function to add to app/utils/round_status.py (new file)

"""
File: app/utils/round_status.py
Version: 1.0.0
Created: 2025-05-18
Description: Utility functions for round status management
"""

from app.models import db, Round, TeamRound, Event, Team, Score, ScoreValue, TaskType
import logging

# Configure logger
logger = logging.getLogger(__name__)

def get_active_round(event_id=None):
    """
    Get the active round for an event.
    
    Args:
        event_id: Optional event ID (if not provided, uses active event)
        
    Returns:
        Active Round instance or None
    """
    try:
        if not event_id:
            # Get active event
            active_event = Event.query.filter_by(status='Active').first()
            if not active_event:
                # Get most recent event
                active_event = Event.query.order_by(Event.event_date.desc()).first()
                
            if active_event:
                event_id = active_event.event_id
            else:
                return None
                
        # Get active round for this event
        active_round = Round.query.filter_by(
            event_id=event_id,
            status='Active'
        ).first()
        
        return active_round
        
    except Exception as e:
        logger.error(f"Error getting active round: {str(e)}")
        return None

def round_completion_status(round_id):
    """
    Check the completion status of a round.
    
    Args:
        round_id: Round ID to check
        
    Returns:
        Dict with status information:
        {
            'total_teams': Total number of teams in the round,
            'scored_teams': Number of teams with scores,
            'completion_percentage': Percentage of completion,
            'can_complete': Boolean indicating if the round can be completed
        }
    """
    try:
        result = {
            'total_teams': 0,
            'scored_teams': 0,
            'completion_percentage': 0,
            'can_complete': False
        }
        
        # Get all team rounds for this round
        team_rounds = TeamRound.query.filter_by(round_id=round_id).all()
        result['total_teams'] = len(team_rounds)
        
        if result['total_teams'] == 0:
            return result
            
        # Count teams where ALL 3 judges have quality scores (not just Messwerte)
        MESSWERTUNG_CODES = {'SEGZEIT', 'LANDGM', 'LANS', 'SEILZ'}
        messwertung_type_ids = {t.type_id for t in TaskType.query.filter(
            TaskType.code.in_(MESSWERTUNG_CODES)).all()}

        for team_round in team_rounds:
            scores = Score.query.filter_by(team_round_id=team_round.team_round_id).all()
            judges_with_quality = 0
            for score in scores:
                has_quality = ScoreValue.query.filter(
                    ScoreValue.score_id == score.score_id,
                    ~ScoreValue.task_type_id.in_(messwertung_type_ids)
                ).first() is not None
                if has_quality:
                    judges_with_quality += 1
            if judges_with_quality >= 3:
                result['scored_teams'] += 1
                
        # Calculate completion percentage
        if result['total_teams'] > 0:
            result['completion_percentage'] = (result['scored_teams'] / result['total_teams']) * 100
            
        # Can complete if at least 50% of teams have scores
        result['can_complete'] = result['completion_percentage'] >= 50
        
        return result
        
    except Exception as e:
        logger.error(f"Error checking round completion status: {str(e)}")
        return {
            'total_teams': 0,
            'scored_teams': 0,
            'completion_percentage': 0,
            'can_complete': False
        }

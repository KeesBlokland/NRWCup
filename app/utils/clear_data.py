"""
File: app/utils/clear_data.py
Version: 1.0.0
Created: 2025-04-18
Description: Utility functions for clearing scoring data
"""

from app.models import db, Event, Round, TeamRound, Score, ScoreValue
import logging

# Configure logger
logger = logging.getLogger(__name__)

def clear_all_scores():
    """
    Clear all scores from the database.
    
    Returns:
        Dict with deletion statistics
    """
    try:
        result = {
            'scores_deleted': 0,
            'team_rounds_deleted': 0  # We're not deleting team rounds, just clearing scores
        }
        
        # Get all score IDs
        score_ids = [score.score_id for score in Score.query.all()]
        
        # Delete score values first
        if score_ids:
            deleted_score_values = ScoreValue.query.filter(ScoreValue.score_id.in_(score_ids)).delete(synchronize_session=False)
            # Then delete scores
            deleted_scores = Score.query.delete()
            result['scores_deleted'] = deleted_scores
        
        # Clear team round scores (set to NULL) but don't delete team rounds
        team_rounds = TeamRound.query.all()
        for team_round in team_rounds:
            team_round.raw_score = None
            team_round.normalized_score = None
            team_round.rank = None
            
        db.session.commit()
        result['team_rounds_deleted'] = len(team_rounds)
        
        return result
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in clear_all_scores: {str(e)}")
        raise

def clear_event_data(event_id, clear_scores_only=True):
    """
    Clear data for a specific event.
    
    Args:
        event_id: ID of the event to clear
        clear_scores_only: If True, just clear scores but keep rounds
                           If False, delete rounds and all related data
                           
    Returns:
        Dict with deletion statistics
    """
    try:
        result = {
            'scores_deleted': 0,
            'team_rounds_deleted': 0,
            'rounds_deleted': 0
        }
        
        # Get rounds for this event
        rounds = Round.query.filter_by(event_id=event_id).all()
        round_ids = [r.round_id for r in rounds]
        
        # Get team rounds for these rounds
        team_rounds = TeamRound.query.filter(TeamRound.round_id.in_(round_ids)).all()
        team_round_ids = [tr.team_round_id for tr in team_rounds]
        
        # Delete scores and score values
        score_ids = []
        for team_round_id in team_round_ids:
            scores = Score.query.filter_by(team_round_id=team_round_id).all()
            score_ids.extend([score.score_id for score in scores])
        
        # Delete score values first
        if score_ids:
            ScoreValue.query.filter(ScoreValue.score_id.in_(score_ids)).delete(synchronize_session=False)
            # Then delete scores
            deleted_scores = Score.query.filter(Score.score_id.in_(score_ids)).delete(synchronize_session=False)
            result['scores_deleted'] = deleted_scores
        
        if clear_scores_only:
            # Just clear team round scores but don't delete them
            for team_round in team_rounds:
                team_round.raw_score = None
                team_round.normalized_score = None
                team_round.rank = None
                team_round.status = 'Pending'
                
            result['team_rounds_deleted'] = len(team_rounds)
        else:
            # Delete team rounds
            deleted_team_rounds = TeamRound.query.filter(TeamRound.team_round_id.in_(team_round_ids)).delete(synchronize_session=False)
            result['team_rounds_deleted'] = deleted_team_rounds
            
            # Delete rounds
            deleted_rounds = Round.query.filter(Round.round_id.in_(round_ids)).delete(synchronize_session=False)
            result['rounds_deleted'] = deleted_rounds
        
        db.session.commit()
        return result
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in clear_event_data: {str(e)}")
        raise

def clear_round_data(round_id):
    """
    Clear data for a specific round.
    
    Args:
        round_id: ID of the round to clear
                           
    Returns:
        Dict with deletion statistics
    """
    try:
        result = {
            'scores_deleted': 0,
            'team_rounds_deleted': 0,
            'rounds_deleted': 0
        }
        
        # Get team rounds for this round
        team_rounds = TeamRound.query.filter_by(round_id=round_id).all()
        team_round_ids = [tr.team_round_id for tr in team_rounds]
        
        # Delete scores and score values
        score_ids = []
        for team_round_id in team_round_ids:
            scores = Score.query.filter_by(team_round_id=team_round_id).all()
            score_ids.extend([score.score_id for score in scores])
        
        # Delete score values first
        if score_ids:
            ScoreValue.query.filter(ScoreValue.score_id.in_(score_ids)).delete(synchronize_session=False)
            # Then delete scores
            deleted_scores = Score.query.filter(Score.score_id.in_(score_ids)).delete(synchronize_session=False)
            result['scores_deleted'] = deleted_scores
        
        # Delete team rounds
        deleted_team_rounds = TeamRound.query.filter(TeamRound.team_round_id.in_(team_round_ids)).delete(synchronize_session=False)
        result['team_rounds_deleted'] = deleted_team_rounds
            
        # Delete the round
        deleted = Round.query.filter_by(round_id=round_id).delete()
        result['rounds_deleted'] = deleted
        
        db.session.commit()
        return result
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in clear_round_data: {str(e)}")
        raise
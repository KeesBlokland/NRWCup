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
    Clear scores from non-completed events only.
    Completed events are NEVER touched.

    Returns:
        Dict with deletion statistics
    """
    try:
        result = {
            'scores_deleted': 0,
            'team_rounds_deleted': 0,
            'events_skipped': 0
        }

        # Only clear scores for events that are NOT Completed
        protected_events = Event.query.filter_by(status='Completed').all()
        protected_event_ids = [e.event_id for e in protected_events]
        result['events_skipped'] = len(protected_events)

        # Get rounds for non-completed events only
        clearable_rounds = Round.query.filter(
            ~Round.event_id.in_(protected_event_ids)
        ).all() if protected_event_ids else Round.query.all()
        round_ids = [r.round_id for r in clearable_rounds]

        if not round_ids:
            db.session.commit()
            return result

        # Get team rounds for these rounds
        team_rounds = TeamRound.query.filter(TeamRound.round_id.in_(round_ids)).all()
        team_round_ids = [tr.team_round_id for tr in team_rounds]

        # Delete score values and scores
        if team_round_ids:
            scores = Score.query.filter(Score.team_round_id.in_(team_round_ids)).all()
            score_ids = [s.score_id for s in scores]

            if score_ids:
                ScoreValue.query.filter(ScoreValue.score_id.in_(score_ids)).delete(synchronize_session=False)
                deleted = Score.query.filter(Score.score_id.in_(score_ids)).delete(synchronize_session=False)
                result['scores_deleted'] = deleted

        # Clear team round scores but don't delete team rounds
        for team_round in team_rounds:
            team_round.raw_score = None
            team_round.normalized_score = None
            team_round.rank = None

        db.session.commit()
        result['team_rounds_deleted'] = len(team_rounds)

        if protected_events:
            logger.info(f"Protected {len(protected_events)} completed event(s): "
                       f"{', '.join(e.name for e in protected_events)}")

        return result

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in clear_all_scores: {str(e)}")
        raise

def clear_event_data(event_id, clear_scores_only=True):
    """
    Clear data for a specific event.
    Refuses to clear completed events.

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

        # PROTECT completed events
        event = Event.query.get(event_id)
        if event and event.status == 'Completed':
            logger.warning(f"Refused to clear completed event: {event.name}")
            raise ValueError(f"Abgeschlossener Wettbewerb '{event.name}' kann nicht gelöscht werden")

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
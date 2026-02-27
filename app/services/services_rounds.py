"""
File: app/services/services_rounds.py
Version: 1.1.0
Created: 2025-03-27
Updated: 2025-04-15
Description: Service for managing rounds and related functionality with fixed data clearing
"""

from app.models import db, Round, TeamRound, Score, ScoreValue, Event
from app.utils.utils_base_service import BaseService
from app.utils.clear_data import clear_event_data, clear_round_data
import logging

logger = logging.getLogger(__name__)

class RoundService(BaseService):
    """Service for round management operations"""
    
    def __init__(self):
        super().__init__(Round)
    
    def get_rounds_for_event(self, event_id):
        """Get all rounds for an event in order"""
        return Round.query.filter_by(event_id=event_id).order_by(Round.round_number).all()
    
    def update_event_rounds(self, event_id, estimated_rounds):
        """
        Store the estimated number of rounds for an event.
        Rounds are created one at a time via generate_next_round, not pre-created.
        This value is only an indication for the contest director.

        Args:
            event_id: Event ID
            estimated_rounds: Estimated number of rounds (informational only)

        Returns:
            True if successful, False otherwise
        """
        try:
            event = Event.query.get(event_id)
            if not event:
                logger.error(f"Event {event_id} not found")
                return False

            event.estimated_rounds = estimated_rounds
            db.session.commit()
            return True

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating event rounds: {str(e)}")
            return False
    
    def get_or_create_round(self, round_number, event_id=None):
        """
        Get existing round or create a new one.
        Prevents duplicate rounds with same number.
        
        Args:
            round_number: Round number to find or create
            event_id: Optional specific event ID
            
        Returns:
            Round object or None if error
        """
        try:
            # Try to find an existing round for the specified event
            if event_id:
                round_obj = Round.query.filter_by(
                    event_id=event_id, 
                    round_number=round_number
                ).first()
                
                if round_obj:
                    logger.info(f"Found existing Round {round_obj.round_id} in event {event_id}")
                    return round_obj
            
            # First look for an active round with this number
            round_obj = Round.query.filter_by(
                round_number=round_number, 
                status='Active'
            ).first()
            
            if round_obj:
                logger.info(f"Found existing active Round: {round_obj.round_id}")
                return round_obj
                
            # Then look for ANY round with this number
            round_obj = Round.query.filter_by(round_number=round_number).first()
            
            if round_obj:
                logger.info(f"Found existing Round: {round_obj.round_id}")
                return round_obj
                
            # Round doesn't exist, create a new one
            logger.info(f"Round {round_number} not found, creating new Round")
            
            # Get target event
            event = None
            if event_id:
                event = Event.query.get(event_id)
            
            # If no explicit event or not found, use active or most recent event
            if not event:
                event = Event.query.filter_by(status='Active').first()
                if not event:
                    event = Event.query.order_by(Event.event_date.desc()).first()
                    
            if not event:
                logger.error("No event found in database, cannot create Round")
                return None
                
            round_obj = Round(
                event_id=event.event_id,
                round_number=round_number,
                status='Active'
            )
            
            db.session.add(round_obj)
            db.session.flush()  # Get ID without committing yet
            logger.info(f"Created new Round with ID {round_obj.round_id}")
            return round_obj
            
        except Exception as e:
            logger.error(f"Error in get_or_create_round: {str(e)}")
            db.session.rollback()
            return None
    
    def clear_round_scores(self, round_id):
        """
        Clear all scores for a specific round.
        
        Args:
            round_id: Round ID
            
        Returns:
            Number of scores deleted
        """
        try:
            result = clear_round_data(round_id)
            return result['scores_deleted']
        except Exception as e:
            logger.error(f"Error clearing round scores: {str(e)}")
            return 0

    
    def clear_event_data(self, event_id, clear_scores_only=True):
        """
        Clear event data using the utility function.
        
        Args:
            event_id: Event ID to clear data for
            clear_scores_only: If True, keep rounds but clear scores
                            If False, delete rounds and all related data
                            
        Returns:
            Dict with deletion statistics
        """
        try:
            return clear_event_data(event_id, clear_scores_only)
        except Exception as e:
            logger.error(f"Error in clear_event_data: {str(e)}")
            return {'rounds_deleted': 0, 'scores_deleted': 0, 'team_rounds_deleted': 0}
"""
File: app/services/services_contest.py
Version: 1.0.1
Created: 2025-03-02
Last Modified: 2025-03-24
Description: Specialized service for Contest/Event management with fixed location deletion
"""

from sqlalchemy import desc
from app.models import db, Event, Location, Round
from app.services.base_service import BaseService
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ContestService(BaseService):
    """Service for Contest/Event operations"""
    
    def __init__(self):
        super().__init__(Event)
    
    def get_all_events(self, order_by_date=True):
        """
        Get all events, optionally ordered by date.
        
        Args:
            order_by_date: Whether to order by date (default: True)
            
        Returns:
            List of Event instances
        """
        query = self.model_class.query
        
        if order_by_date:
            query = query.order_by(desc(self.model_class.event_date))
            
        return query.all()
    
    def get_event_with_location(self, event_id):
        """
        Get an event with its location.
        
        Args:
            event_id: ID of the event
            
        Returns:
            Event instance with location loaded
        """
        return self.model_class.query\
            .options(db.joinedload(Event.location))\
            .filter(Event.event_id == event_id)\
            .first()
    
    def create_event_with_location(self, event_data, location_data):
        """
        Create a new event with its location.
        
        Args:
            event_data: Dict of event data
            location_data: Dict of location data
            
        Returns:
            Created Event instance or None if error
        """
        try:
            # Create or update location
            location = Location()
            
            for key, value in location_data.items():
                if hasattr(location, key) and value is not None:
                    setattr(location, key, value)
            
            db.session.add(location)
            db.session.flush()  # Get location ID
            
            # Create event
            event = Event()
            
            for key, value in event_data.items():
                if hasattr(event, key) and value is not None:
                    setattr(event, key, value)
                    
            event.location_id = location.location_id
            
            db.session.add(event)
            db.session.commit()
            
            return event
            
        except Exception:
            db.session.rollback()
            raise
    
    def update_event_with_location(self, event_id, event_data, location_data):
        """
        Update an event and its location.
        
        Args:
            event_id: ID of the event to update
            event_data: Dict of event data
            location_data: Dict of location data
            
        Returns:
            Updated Event instance or None if not found
        """
        try:
            event = self.get_by_id(event_id)
            if not event:
                return None
                
            # Get or create location
            if event.location_id:
                location = Location.query.get(event.location_id)
                if not location:
                    location = Location()
            else:
                location = Location()
            
            # Update location
            for key, value in location_data.items():
                if hasattr(location, key) and value is not None:
                    setattr(location, key, value)
            
            db.session.add(location)
            db.session.flush()  # Get location ID
            
            # Update event
            for key, value in event_data.items():
                if hasattr(event, key) and value is not None:
                    setattr(event, key, value)
                    
            event.location_id = location.location_id
            
            db.session.commit()
            
            return event
            
        except Exception:
            db.session.rollback()
            raise
    
    def delete_event_with_location(self, event_id):
        """
        Delete an event and its location if not used by other events.
        Args: event_id: ID of the event to delete
        Returns: True if deleted, False otherwise
        """
        try:
            event = self.get_by_id(event_id)
            if not event:
                return False
            
            # Get location
            location = None
            if event.location_id:
                location = Location.query.get(event.location_id)
            
            # Delete event
            db.session.delete(event)
            
            # Delete location if not used by other events
            if location:
                # Check if location is used by other events
                other_events = Event.query.filter(
                    Event.location_id == location.location_id,
                    Event.event_id != event_id
                ).count()
                
                if other_events == 0:
                    db.session.delete(location)
                
            db.session.commit()
            
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting event: {str(e)}")
            raise
    
    def parse_event_date(self, date_str):
        """
        Parse event date string to datetime.date.
        
        Args:
            date_str: Date string in format YYYY-MM-DD
            
        Returns:
            datetime.date object or None if invalid
        """
        if not date_str:
            return None
            
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return None
    
    def get_events_by_status(self, status):
        """
        Get events by status.
        
        Args:
            status: Status to filter by (e.g., 'Active', 'Pending', 'Completed')
            
        Returns:
            List of Event instances
        """
        return self.model_class.query\
            .filter(Event.status == status)\
            .order_by(desc(Event.event_date))\
            .all()
    
    def change_event_status(self, event_id, new_status):
        """
        Change event status.
        
        Args:
            event_id: ID of the event
            new_status: New status value
            
        Returns:
            Updated Event instance or None if not found
        """
        try:
            event = self.get_by_id(event_id)
            if not event:
                return None
                
            event.status = new_status
            db.session.commit()
            
            return event
            
        except Exception:
            db.session.rollback()
            raise
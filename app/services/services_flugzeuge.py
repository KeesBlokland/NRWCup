"""
File: app/services/services_flugzeuge.py
Version: 1.1.0
Created: 2025-04-01
Description: Enhanced service for Flugzeuge (aircraft) model with improved error handling and data integrity
"""

from sqlalchemy import or_
from app.models import db, Flugzeuge, Teilnehmer
from app.utils.utils_base_service import BaseService
import logging

logger = logging.getLogger(__name__)

class FlugzeugeService(BaseService):
    """Service for Flugzeuge (aircraft) operations"""
    
    def __init__(self):
        super().__init__(Flugzeuge)
    
    def get_by_type(self, aircraft_type):
        """
        Get aircraft by type.
        
        Args:
            aircraft_type: Type to filter by ('segler', 'schlepper')
            
        Returns:
            List of Flugzeuge instances
        """
        query = self.model_class.query
        
        if aircraft_type == 'segler':
            query = query.filter(self.model_class.is_segler == True)
        elif aircraft_type == 'schlepper':
            query = query.filter(self.model_class.is_schlepper == True)
        
        return query.order_by(self.model_class.name).all()
    
    def get_pilot_aircraft(self, pilot_id, aircraft_type=None):
        """
        Get aircraft associated with a specific pilot.
        
        Args:
            pilot_id: Teilnehmer ID of the pilot
            aircraft_type: Optional type filter ('segler', 'schlepper')
            
        Returns:
            List of Flugzeuge instances
        """
        query = self.model_class.query.filter(
            or_(
                self.model_class.pilot_id == pilot_id,
                self.model_class.plane_owner_id == pilot_id
            )
        )
        
        if aircraft_type == 'segler':
            query = query.filter(self.model_class.is_segler == True)
        elif aircraft_type == 'schlepper':
            query = query.filter(self.model_class.is_schlepper == True)
        
        return query.order_by(self.model_class.name).all()
    
    def get_eligible_pilots(self):
        """
        Get all participants who are eligible to be pilots.
        
        Returns:
            List of Teilnehmer instances who are pilots
        """
        return Teilnehmer.query.filter(
            or_(
                Teilnehmer.is_segler_pilot == True,
                Teilnehmer.is_schlepper_pilot == True
            )
        ).order_by(Teilnehmer.name).all()
    
    def create(self, **kwargs):
        """
        Create a new aircraft with improved validation.
        
        Args:
            **kwargs: Aircraft attributes
            
        Returns:
            Created Flugzeuge instance or None if error
        """
        try:
            # Enhanced validation for required fields
            if not kwargs.get('name'):
                logger.error("Cannot create aircraft without a name")
                return None
                
            # Ensure at least one type is selected
            if not kwargs.get('is_segler') and not kwargs.get('is_schlepper'):
                logger.warning("Creating aircraft without type specification")
            
            # Log the creation attempt
            logger.info(f"Creating aircraft: {kwargs.get('name')}")
            
            # Create new aircraft
            aircraft = Flugzeuge(
                name=kwargs.get('name'),
                is_segler=kwargs.get('is_segler', False),
                is_schlepper=kwargs.get('is_schlepper', False),
                span=kwargs.get('span'),
                gewicht=kwargs.get('gewicht'),
                antrieb=kwargs.get('antrieb'),
                prop=kwargs.get('prop'),
                fernsteuerung=kwargs.get('fernsteuerung'),
                pilot_id=kwargs.get('pilot_id'),
                plane_owner_id=kwargs.get('plane_owner_id')
            )
            
            db.session.add(aircraft)
            db.session.commit()
            
            logger.info(f"Successfully created aircraft {aircraft.flugzeug_id}")
            return aircraft
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating aircraft: {str(e)}")
            return None
    
    def update(self, id, **kwargs):
        """
        Update an existing aircraft with improved validation.
        
        Args:
            id: Aircraft ID
            **kwargs: Aircraft attributes
            
        Returns:
            Updated Flugzeuge instance or None if error
        """
        try:
            aircraft = self.get_by_id(id)
            if not aircraft:
                logger.error(f"Cannot update - aircraft with ID {id} not found")
                return None
            
            # Enhanced validation for required fields    
            if 'name' in kwargs and not kwargs.get('name'):
                logger.error("Cannot update aircraft without a name")
                return None
            
            # Log the update attempt
            logger.info(f"Updating aircraft {id}: {kwargs}")
            
            # Update fields
            if 'name' in kwargs:
                aircraft.name = kwargs.get('name')
            if 'is_segler' in kwargs:
                aircraft.is_segler = kwargs.get('is_segler')
            if 'is_schlepper' in kwargs:
                aircraft.is_schlepper = kwargs.get('is_schlepper')
            if 'span' in kwargs:
                aircraft.span = kwargs.get('span')
            if 'gewicht' in kwargs:
                aircraft.gewicht = kwargs.get('gewicht')
            if 'antrieb' in kwargs:
                aircraft.antrieb = kwargs.get('antrieb')
            if 'prop' in kwargs:
                aircraft.prop = kwargs.get('prop')
            if 'fernsteuerung' in kwargs:
                aircraft.fernsteuerung = kwargs.get('fernsteuerung')
            if 'pilot_id' in kwargs:
                aircraft.pilot_id = kwargs.get('pilot_id')
            if 'plane_owner_id' in kwargs:
                aircraft.plane_owner_id = kwargs.get('plane_owner_id')
            
            db.session.commit()
            
            logger.info(f"Successfully updated aircraft {id}")
            return aircraft
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating aircraft {id}: {str(e)}")
            return None
    
    def can_delete(self, flugzeug_id):
        """
        Check if an aircraft can be deleted.
        
        Args:
            flugzeug_id: ID of the aircraft to check
            
        Returns:
            True if can be deleted, False otherwise
        """
        flugzeug = self.get_by_id(flugzeug_id)
        if not flugzeug:
            return False
        
        # Check for related teams
        relations = []
        if hasattr(flugzeug, 'schlepper_teams'):
            relations.extend(flugzeug.schlepper_teams)
        if hasattr(flugzeug, 'segler_teams'):
            relations.extend(flugzeug.segler_teams)
            
        return len(relations) == 0
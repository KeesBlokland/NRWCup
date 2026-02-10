"""
File: app/services/services_teilnehmer.py
Version: 1.1.0
Created: 2025-03-02
Updated: 2025-05-18
Description: Specialized service for Teilnehmer model with fixed can_delete method
"""

from sqlalchemy import or_
from app.models import db, Teilnehmer
from app.utils.utils_base_service import BaseService

class TeilnehmerService(BaseService):
    """Service for Teilnehmer operations"""
    
    def __init__(self):
        super().__init__(Teilnehmer)
    
    def get_by_role(self, role):
        """
        Get participants by role.
        
        Args:
            role: Role to filter by ('segler', 'schlepper', 'punktwerter', 'leitung')
            
        Returns:
            List of Teilnehmer instances
        """
        query = self.model_class.query
        
        if role == 'segler':
            query = query.filter(self.model_class.is_segler_pilot == True)
        elif role == 'schlepper':
            query = query.filter(self.model_class.is_schlepper_pilot == True)
        elif role == 'punktwerter':
            query = query.filter(self.model_class.is_punktwerter == True)
        elif role == 'leitung':
            query = query.filter(self.model_class.is_wettkampfleitung == True)
        
        return query.order_by(self.model_class.name).all()
    
    def get_judges(self):
        """
        Get all participants who are judges.
        
        Returns:
            List of Teilnehmer instances who are judges
        """
        return self.model_class.query\
            .filter(self.model_class.is_punktwerter == True)\
            .order_by(self.model_class.name)\
            .all()
    
    def get_pilots(self, include_segler=True, include_schlepper=True):
        """
        Get all participants who are pilots.
        
        Args:
            include_segler: Include glider pilots
            include_schlepper: Include tug pilots
            
        Returns:
            List of Teilnehmer instances who are pilots
        """
        filters = []
        
        if include_segler:
            filters.append(self.model_class.is_segler_pilot == True)
        
        if include_schlepper:
            filters.append(self.model_class.is_schlepper_pilot == True)
        
        if not filters:
            return []
        
        return self.model_class.query\
            .filter(or_(*filters))\
            .order_by(self.model_class.name)\
            .all()
    
    def get_unique_clubs(self):
        """
        Get list of unique club names.
        
        Returns:
            List of club names
        """
        clubs = db.session.query(self.model_class.verein)\
            .filter(self.model_class.verein != '')\
            .filter(self.model_class.verein != None)\
            .distinct()\
            .order_by(self.model_class.verein)\
            .all()
        
        # Extract values from result tuples
        return [club[0] for club in clubs if club[0]]
    
    def get_by_club(self, club_name):
        """
        Get participants by club name.
        
        Args:
            club_name: Club name to filter by
            
        Returns:
            List of Teilnehmer instances
        """
        return self.model_class.query\
            .filter(self.model_class.verein == club_name)\
            .order_by(self.model_class.name)\
            .all()
    
    def can_delete(self, teilnehmer_id):
        """
        Check if a participant can be deleted.
        
        Args:
            teilnehmer_id: ID of the participant to check
            
        Returns:
            True if can be deleted, False otherwise
        """
        teilnehmer = self.get_by_id(teilnehmer_id)
        if not teilnehmer:
            return False
        
        # Check for related records using the correct relationship names
        # Judged scores relationship
        has_scores = len(getattr(teilnehmer, 'judged_scores', [])) > 0
        
        # Aircraft relationships
        has_aircraft = (
            len(getattr(teilnehmer, 'owned_aircraft', [])) > 0 or 
            len(getattr(teilnehmer, 'piloted_aircraft', [])) > 0
        )
        
        # Team relationships
        has_teams = (
            len(getattr(teilnehmer, 'schlepper_teams', [])) > 0 or
            len(getattr(teilnehmer, 'segler_teams', [])) > 0
        )
        
        # If there are any related records, cannot delete
        return not (has_scores or has_aircraft or has_teams)
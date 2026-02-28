"""
File: app/services/services_teams.py
Version: 2.0.0
Created: 2025-03-02
Last Modified: 2025-04-19
Description: Specialized service for Team model with improved numbering system
"""

from sqlalchemy import or_
from app.models import db, Team, Teilnehmer, Flugzeuge
from app.services.base_service import BaseService

class TeamService(BaseService):
    """Service for Team operations"""
    
    def __init__(self):
        super().__init__(Team)
    
    def get_next_team_number(self):
        """
        Get the next available team number.
        
        Returns:
            Next available team number (integer)
        """
        # Get all active team numbers
        active_numbers = db.session.query(Team.team_nummer)\
            .filter(Team.status == 'active')\
            .order_by(Team.team_nummer)\
            .all()
        
        # Extract numbers from result tuples
        active_numbers = [n[0] for n in active_numbers]
        
        if not active_numbers:
            return 1
            
        # Find the first gap in the sequence
        for i in range(1, len(active_numbers) + 2):
            if i not in active_numbers:
                return i
                
        # Fallback to highest + 1 (shouldn't reach here but just in case)
        return max(active_numbers) + 1
        
    def get_available_team_numbers(self):
        """
        Get a list of available team numbers, including gaps in the sequence.
        
        Returns:
            List of available team numbers
        """
        # Get all active team numbers
        active_numbers = db.session.query(Team.team_nummer)\
            .filter(Team.status == 'active')\
            .order_by(Team.team_nummer)\
            .all()
            
        # Extract numbers from result tuples
        active_numbers = [n[0] for n in active_numbers]
        
        if not active_numbers:
            return [1] # Start with 1 if no teams exist
            
        # Find gaps in the sequence
        max_num = max(active_numbers)
        available = [i for i in range(1, max_num + 2) if i not in active_numbers]
        
        # Always include next number after highest current number
        if max_num + 1 not in available:
            available.append(max_num + 1)
            
        return sorted(available)
    
    def get_schlepper_pilots(self):
        """
        Get all schlepper pilots.
        
        Returns:
            List of Teilnehmer instances who are schlepper pilots
        """
        return Teilnehmer.query\
            .filter(Teilnehmer.is_schlepper_pilot == True)\
            .order_by(Teilnehmer.name)\
            .all()
    
    def get_segler_pilots(self):
        """
        Get all segler pilots.
        
        Returns:
            List of Teilnehmer instances who are segler pilots
        """
        return Teilnehmer.query\
            .filter(Teilnehmer.is_segler_pilot == True)\
            .order_by(Teilnehmer.name)\
            .all()
    
    def get_available_aircraft(self, pilot_id, aircraft_type):
        """
        Get available aircraft for a specific pilot and type.
        
        Args:
            pilot_id: ID of the pilot
            aircraft_type: Type of aircraft ('segler' or 'schlepper')
            
        Returns:
            List of Flugzeuge instances
        """
        query = Flugzeuge.query
        
        # Filter by pilot or owner
        query = query.filter(
            or_(
                Flugzeuge.pilot_id == pilot_id,
                Flugzeuge.plane_owner_id == pilot_id
            )
        )
        
        # Filter by type
        if aircraft_type == 'segler':
            query = query.filter(Flugzeuge.is_segler == True)
        elif aircraft_type == 'schlepper':
            query = query.filter(Flugzeuge.is_schlepper == True)
        
        return query.all()
    
    def can_delete(self, team_id):
        """
        Check if a team can be deleted.
        
        Args:
            team_id: ID of the team to check
            
        Returns:
            True if can be deleted, False otherwise
        """
        team = self.get_by_id(team_id)
        if not team:
            return False
        
        # Check for related TeamRound records
        return len(getattr(team, 'team_rounds', [])) == 0
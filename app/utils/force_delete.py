"""
File: app/utils/force_delete.py
Version: 1.0.0
Created: 2025-04-18
Description: Utility functions for forcing deletion of database objects with cascading
"""

from app.models import db, Teilnehmer, Team, Flugzeuge, TeamRound, Score, ScoreValue
import logging

# Configure logger
logger = logging.getLogger(__name__)

def force_delete_teilnehmer(teilnehmer_id):
    """
    Force delete a participant and all related records.
    
    Args:
        teilnehmer_id: ID of the participant to delete
        
    Returns:
        Dict with deletion statistics
    """
    try:
        result = {
            'teams_deleted': 0,
            'aircraft_deleted': 0,
            'scores_deleted': 0
        }
        
        teilnehmer = Teilnehmer.query.get(teilnehmer_id)
        if not teilnehmer:
            return {'error': 'Teilnehmer nicht gefunden'}
            
        # Handle scores where this teilnehmer is a judge
        score_ids = []
        scores = Score.query.filter_by(judge_id=teilnehmer_id).all()
        for score in scores:
            score_ids.append(score.score_id)
            
        # Delete score values first
        if score_ids:
            ScoreValue.query.filter(ScoreValue.score_id.in_(score_ids)).delete(synchronize_session=False)
            # Then delete scores
            deleted_scores = Score.query.filter(Score.score_id.in_(score_ids)).delete(synchronize_session=False)
            result['scores_deleted'] = deleted_scores
        
        # Handle teams where this teilnehmer is a pilot
        schlepper_teams = Team.query.filter_by(schlepper_pilot_id=teilnehmer_id).all()
        segler_teams = Team.query.filter_by(segler_pilot_id=teilnehmer_id).all()
        
        teams_to_delete = []
        
        # Teams where teilnehmer is the only pilot
        for team in schlepper_teams:
            if not team.segler_pilot_id:
                teams_to_delete.append(team.team_id)
            else:
                # Just clear this pilot's reference
                team.schlepper_pilot_id = None
                
        for team in segler_teams:
            if not team.schlepper_pilot_id:
                teams_to_delete.append(team.team_id)
            else:
                # Just clear this pilot's reference
                team.segler_pilot_id = None
        
        # Delete orphaned teams
        if teams_to_delete:
            # First remove team rounds for these teams
            TeamRound.query.filter(TeamRound.team_id.in_(teams_to_delete)).delete(synchronize_session=False)
            
            # Then delete teams
            deleted_teams = Team.query.filter(Team.team_id.in_(teams_to_delete)).delete(synchronize_session=False)
            result['teams_deleted'] = deleted_teams
        
        # Handle aircraft where this teilnehmer is pilot or owner
        aircraft_to_update = Flugzeuge.query.filter(
            (Flugzeuge.pilot_id == teilnehmer_id) | 
            (Flugzeuge.plane_owner_id == teilnehmer_id)
        ).all()
        
        aircraft_to_delete = []
        
        for aircraft in aircraft_to_update:
            if aircraft.pilot_id == teilnehmer_id and aircraft.plane_owner_id == teilnehmer_id:
                # If this teilnehmer is both pilot and owner, delete the aircraft
                aircraft_to_delete.append(aircraft.flugzeug_id)
            else:
                # Otherwise just clear the reference
                if aircraft.pilot_id == teilnehmer_id:
                    aircraft.pilot_id = None
                if aircraft.plane_owner_id == teilnehmer_id:
                    aircraft.plane_owner_id = None
        
        # Delete orphaned aircraft
        if aircraft_to_delete:
            deleted_aircraft = Flugzeuge.query.filter(Flugzeuge.flugzeug_id.in_(aircraft_to_delete)).delete(synchronize_session=False)
            result['aircraft_deleted'] = deleted_aircraft
        
        # Finally delete the teilnehmer
        db.session.delete(teilnehmer)
        db.session.commit()
        
        return result
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in force_delete_teilnehmer: {str(e)}")
        return {'error': str(e)}

def force_delete_flugzeug(flugzeug_id):
    """
    Force delete an aircraft and update related records.
    
    Args:
        flugzeug_id: ID of the aircraft to delete
        
    Returns:
        Dict with deletion statistics
    """
    try:
        result = {
            'teams_updated': 0
        }
        
        flugzeug = Flugzeuge.query.get(flugzeug_id)
        if not flugzeug:
            return {'error': 'Flugzeug nicht gefunden'}
            
        # Update teams where this aircraft is used
        schlepper_teams = Team.query.filter_by(schlepper_flugzeug_id=flugzeug_id).all()
        segler_teams = Team.query.filter_by(segler_flugzeug_id=flugzeug_id).all()
        
        teams_updated = 0
        
        for team in schlepper_teams:
            team.schlepper_flugzeug_id = None
            teams_updated += 1
            
        for team in segler_teams:
            team.segler_flugzeug_id = None
            teams_updated += 1
            
        result['teams_updated'] = teams_updated
        
        # Delete the aircraft
        db.session.delete(flugzeug)
        db.session.commit()
        
        return result
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in force_delete_flugzeug: {str(e)}")
        return {'error': str(e)}

def force_delete_team(team_id):
    """
    Force delete a team and cascade the deletion.
    
    Args:
        team_id: ID of the team to delete
        
    Returns:
        Dict with deletion statistics
    """
    try:
        result = {
            'team_rounds_deleted': 0,
            'scores_deleted': 0
        }
        
        team = Team.query.get(team_id)
        if not team:
            return {'error': 'Team nicht gefunden'}
            
        # Get all team rounds for this team
        team_rounds = TeamRound.query.filter_by(team_id=team_id).all()
        team_round_ids = [tr.team_round_id for tr in team_rounds]
        
        # Delete scores and score values for each team round
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
        deleted_team_rounds = TeamRound.query.filter(TeamRound.team_id == team_id).delete(synchronize_session=False)
        result['team_rounds_deleted'] = deleted_team_rounds
        
        # Delete the team
        db.session.delete(team)
        db.session.commit()
        
        return result
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in force_delete_team: {str(e)}")
        return {'error': str(e)}
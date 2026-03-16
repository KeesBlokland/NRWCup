# Helper function to add to app/utils/round_status.py (new file)

"""
File: app/utils/round_status.py
Version: 1.0.0
Created: 2025-05-18
Description: Utility functions for round status management
"""

from app.models import db, Round, TeamRound, Event, Team, Score, ScoreValue, TaskType
from app.utils.scoring_constants import get_scoring_constants
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
            
        # Build lookup maps for task types
        MESSWERTUNG_CODES, ALWAYS_MANDATORY, EXCLUSIVE_GROUPS = get_scoring_constants()
        all_types = {t.code: t.type_id for t in TaskType.query.filter_by(is_active=True).all()}
        messwertung_type_ids = {all_types[c] for c in MESSWERTUNG_CODES if c in all_types}
        always_mandatory_ids = {all_types[c] for c in ALWAYS_MANDATORY if c in all_types}
        exclusive_group_ids = [
            {all_types[c] for c in group if c in all_types}
            for group in EXCLUSIVE_GROUPS
        ]

        for team_round in team_rounds:
            scores = Score.query.filter_by(team_round_id=team_round.team_round_id).all()
            if len(scores) < 3:
                continue

            # Check 1: Messwerte present on at least one score
            has_messwerte = False
            for score in scores:
                mess_count = ScoreValue.query.filter(
                    ScoreValue.score_id == score.score_id,
                    ScoreValue.task_type_id.in_(messwertung_type_ids)
                ).count()
                if mess_count >= len(MESSWERTUNG_CODES):
                    has_messwerte = True
                    break
            if not has_messwerte:
                continue

            # Check 2: All 3 judges have all mandatory figures + one from each exclusive group
            all_judges_complete = True
            judge_exclusive_choices = []  # track per judge for consistency
            for score in scores:
                all_svs = ScoreValue.query.filter_by(score_id=score.score_id).all()
                sv_type_ids = {sv.task_type_id for sv in all_svs}

                # All always-mandatory figures present?
                if not always_mandatory_ids.issubset(sv_type_ids):
                    all_judges_complete = False
                    break

                # At least one from each exclusive group present (zero is valid — team may crash)
                sv_nonzero_type_ids = {sv.task_type_id for sv in all_svs if sv.value}
                choices = {}
                for group, group_ids in zip(EXCLUSIVE_GROUPS, exclusive_group_ids):
                    if not (group_ids & sv_type_ids):
                        all_judges_complete = False
                        break
                    # Use non-zero choice for consistency check; empty set means all-zero (crashed)
                    choices[frozenset(group)] = group_ids & sv_nonzero_type_ids
                if not all_judges_complete:
                    break
                judge_exclusive_choices.append(choices)

            if not all_judges_complete:
                continue

            # Check 3: Exclusive group choices consistent across all judges
            # Skip if all judges scored zero for this group (crashed team — no variant chosen)
            choices_consistent = True
            for group in EXCLUSIVE_GROUPS:
                key = frozenset(group)
                all_choices = [jc[key] for jc in judge_exclusive_choices]
                # If every judge has only zero-value entries, skip consistency — no variant was flown
                all_zero = all(not c for c in all_choices)
                if all_zero:
                    continue
                if len(set(map(frozenset, all_choices))) > 1:
                    choices_consistent = False
                    break

            if choices_consistent:
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

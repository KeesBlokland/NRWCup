"""
File: app/routes/bp_testdata.py
Version: 1.7.0
Created: 2025-03-26
Updated: 2025-04-15
Description: Test data generation with complete TeamRound deletion
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.models import db, Team, Round, Teilnehmer, Event, Score, ScoreValue, TaskType, TeamRound
from sqlalchemy.exc import SQLAlchemyError
from app.utils.clear_data import clear_all_scores, clear_event_data
import logging
import random
from datetime import datetime, timedelta

# Configure logger
logger = logging.getLogger(__name__)

# Create blueprint
testdata_bp = Blueprint('testdata', __name__)

def generate_gaussian_score(mean=7.0, std_dev=1.5, min_val=0, max_val=10):
    """Generate a score using Gaussian distribution, centered around 7 (±3)"""
    score = random.gauss(mean, std_dev)
    return max(min_val, min(max_val, round(score * 2) / 2))  # Round to nearest 0.5

def generate_landing_score():
    """Generate score for landing zones (0, 5, 10, 20, 30)"""
    return random.choice([0, 5, 10, 20, 30])

def handle_mutually_exclusive_figures(task_types):
    """Handle figures that are mutually exclusive (only one gets a value, others are 0)
       Returns dictionary with chosen variants that should be consistent across judges"""
    
    chosen_variants = {}
    
    # Group 1: Platzrunde variants
    platzrunde_variants = [task for task in task_types if 
                          task.name_de and 'Platzrunde' in task.name_de]
    if platzrunde_variants:
        # Choose one random variant to score
        chosen_variants['platzrunde'] = random.choice(platzrunde_variants).type_id
    
    # Group 2: Platzüberflug variants
    platzu_variants = [task for task in task_types if 
                       task.name_de and 'Platz' in task.name_de and 'berflug' in task.name_de]
    if platzu_variants:
        # Choose one random variant to score
        chosen_variants['platzu'] = random.choice(platzu_variants).type_id
    
    return chosen_variants

@testdata_bp.route('/clear', methods=['POST'])
def clear_scores():
    """Clear all test scores from the database"""
    try:
        # Call the utility function to clear all scores
        result = clear_all_scores()
        
        # Provide feedback to the user
        flash(f'Cleared all {result["scores_deleted"]} scores and removed {result["team_rounds_deleted"]} team round entries from the database', 'success')
        
        return redirect(url_for('testdata.index'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error clearing scores: {str(e)}")
        flash(f'Error clearing scores: {str(e)}', 'error')
        return redirect(url_for('testdata.index'))
    

@testdata_bp.route('/', endpoint='index')
def index():
    """Display test data generation interface"""
    try:
        # Get active task types
        task_types = TaskType.query.filter_by(is_active=True).order_by(TaskType.sort_order).all()
        
        # Get teams
        teams = Team.query.filter_by(status='active').all()
        
        # Get judges
        judges = Teilnehmer.query.filter_by(is_punktwerter=True).all()
        
        # Get events for template dropdown — exclude completed/published events
        events = Event.query.filter(
            Event.status.notin_(['Completed', 'Published'])
        ).order_by(Event.event_date.desc()).all()
        
        return render_template('testdata/testdata_main.html', 
                              task_types=task_types,
                              teams=teams,
                              judges=judges,
                              events=events)
                              
    except SQLAlchemyError as e:
        logger.error(f"Database error in testdata.index: {str(e)}")
        flash('Error loading test data page', 'error')
        return render_template('testdata/testdata_main.html')

@testdata_bp.route('/generate', methods=['POST'])
def generate():
    """Generate test scores based on selected options"""
    try:
        # Get parameters from form
        team_ids = request.form.getlist('team_ids')
        judge_ids = request.form.getlist('judge_ids')
        score_variability = int(request.form.get('score_variability', 20))  # Percentage
        clear_existing = request.form.get('clear_existing') == 'on'
        event_id = request.form.get('event_id')
        specific_round = int(request.form.get('specific_round', 0))  # New parameter
        
        # Get number of rounds
        num_rounds = int(request.form.get('num_rounds', 1))
        
        # If num_rounds is 0, redirect to contest page for clearing all scores
        if num_rounds == 0:
            return redirect(url_for('contest.index'))
        
        # Convert to integers
        team_ids = [int(id) for id in team_ids if id]
        judge_ids = [int(id) for id in judge_ids if id]
        
        # Validation
        if not team_ids:
            flash('Please select at least one team', 'error')
            return redirect(url_for('testdata.index'))
        
        if not judge_ids:
            flash('Please select at least one judge', 'error')
            return redirect(url_for('testdata.index'))
            
        if not event_id:
            flash('Please select an event', 'error')
            return redirect(url_for('testdata.index'))
        
        event_id = int(event_id)
        event = Event.query.get(event_id)
        if not event:
            flash('Selected event not found', 'error')
            return redirect(url_for('testdata.index'))

        if event.status in ('Completed', 'Published'):
            flash(f'Testdaten können nicht für abgeschlossene Wettbewerbe generiert werden ({event.name})', 'error')
            return redirect(url_for('testdata.index'))
        
        # Get existing rounds for this event
        existing_rounds = Round.query.filter_by(event_id=event_id).order_by(Round.round_number).all()
        
        # Clear existing scores if requested
        if clear_existing:
            try:
                # Clear the event data but keep the rounds
                result = clear_event_data(event_id, clear_scores_only=True)
                flash(f"Cleared existing scores for event {event.name}: {result['scores_deleted']} scores removed, {result['team_rounds_deleted']} team rounds deleted", 'success')
            except Exception as e:
                logger.error(f"Error clearing scores: {str(e)}")
                flash(f"Error clearing scores: {str(e)}", 'error')
                return redirect(url_for('testdata.index'))
        
        # Determine rounds to process
        if specific_round > 0:
            # Specific round mode - find or create the requested round
            round_obj = next((r for r in existing_rounds if r.round_number == specific_round), None)
            
            if not round_obj:
                # Create new round
                round_obj = Round(
                    event_id=event_id,
                    round_number=specific_round,
                    status='Active'
                )
                db.session.add(round_obj)
                db.session.flush()
                logger.info(f"Created new round {specific_round} for event {event_id}")
            
            # Process just this one round
            rounds_to_process = [round_obj]
        else:
            # Multiple rounds mode
            rounds_to_process = []
            
            for i in range(1, num_rounds + 1):
                # Find or create each round
                round_obj = next((r for r in existing_rounds if r.round_number == i), None)
                
                if not round_obj:
                    # Create new round
                    round_obj = Round(
                        event_id=event_id,
                        round_number=i,
                        status='Active'
                    )
                    db.session.add(round_obj)
                    db.session.flush()
                    logger.info(f"Created new round {i} for event {event_id}")
                
                rounds_to_process.append(round_obj)
        
        # Get task types
        task_types = TaskType.query.filter_by(is_active=True).order_by(TaskType.sort_order).all()
        
        # Get teams
        teams = Team.query.filter(Team.team_id.in_(team_ids)).all()
        
        # Get judges
        judges = Teilnehmer.query.filter(Teilnehmer.teilnehmer_id.in_(judge_ids)).all()
        
        # Generate scores
        rounds_created = 0
        scores_generated = 0
        
        # Process each round
        for round_obj in rounds_to_process:
            # Select a center judge for this round (consistent throughout the round)
            if judges:
                center_judge = random.choice(judges)
                logger.info(f"Selected center judge {center_judge.name} for round {round_obj.round_number}")
            else:
                center_judge = None
            
            # Generate scores for each team
            for team in teams:
                # Find or create team round
                team_round = TeamRound.query.filter_by(
                    round_id=round_obj.round_id,
                    team_id=team.team_id
                ).first()
                
                if not team_round:
                    team_round = TeamRound(
                        round_id=round_obj.round_id,
                        team_id=team.team_id,
                        status='Pending',
                        start_order=team.team_nummer
                    )
                    db.session.add(team_round)
                    db.session.flush()
                
                # Select which variant each team uses (same for all judges)
                chosen_variants = handle_mutually_exclusive_figures(task_types)
                
                # For flight time (SEGZEIT) and landing zones (LANDGM, LANS, SEILZ)
                # Generate a single value that will be used by the center judge
                segzeit_value = random.randint(170, 230)
                landing_values = {
                    'LANDGM': generate_landing_score(),
                    'LANS': generate_landing_score(),
                    'SEILZ': generate_landing_score()
                }
                
                # Generate scores for each judge
                for judge in judges:
                    # Create new score
                    score = Score(
                        team_round_id=team_round.team_round_id,
                        judge_id=judge.teilnehmer_id,
                        entered_at=datetime.now(),
                        notes="Test data generated score"
                    )
                    db.session.add(score)
                    db.session.flush()
                    
                    # Apply score variability
                    std_dev = score_variability / 100 * 3  # Convert to standard deviation
                    
                    # Generate values for each task type
                    for task_type in task_types:
                        # For landing zones and flight time, only the center judge creates entries
                        if task_type.code in ['LANDGM', 'LANS', 'SEILZ', 'SEGZEIT']:
                            # Skip creating entries for non-center judges
                            if judge.teilnehmer_id != center_judge.teilnehmer_id:
                                continue
                                
                            # Set value for center judge
                            if task_type.code == 'SEGZEIT':
                                value = segzeit_value
                            else:
                                value = landing_values[task_type.code]
                        elif 'Platzrunde' in task_type.name_de:
                            # For Platzrunde variants
                            if 'platzrunde' in chosen_variants and task_type.type_id == chosen_variants['platzrunde']:
                                value = generate_gaussian_score(std_dev=std_dev)
                            else:
                                value = 0.0
                        elif 'berflug' in task_type.name_de:
                            # For Platzüberflug variants
                            if 'platzu' in chosen_variants and task_type.type_id == chosen_variants['platzu']:
                                value = generate_gaussian_score(std_dev=std_dev)
                            else:
                                value = 0.0
                        else:
                            # Standard scores centered around 7
                            value = generate_gaussian_score(std_dev=std_dev)
                            
                        # If task has max_value set, respect it
                        if value is not None and task_type.max_value is not None:
                            value = min(value, task_type.max_value)
                        
                        # Create score value
                        score_value = ScoreValue(
                            score_id=score.score_id,
                            task_type_id=task_type.type_id,
                            value=value
                        )
                        db.session.add(score_value)
                    
                    scores_generated += 1
                    
                # Calculate team_round raw score and normalized score
                from app.services.services_scoring import ScoringService
                scoring_service = ScoringService()
                scoring_service.update_team_round_scores(team_round.team_round_id)
            
            rounds_created += 1
        
        # Commit all changes
        db.session.commit()
        
        if specific_round > 0:
            logger.info(f"Generated scores for round {specific_round}: {len(teams) * len(judges)} team-judge combinations")
            flash(f'Successfully generated {scores_generated} scores for round {specific_round}', 'success')
        else:
            logger.info(f"Generated scores for {len(teams) * len(judges) * len(rounds_to_process)} team-judge-round combinations")
            flash(f'Successfully created {rounds_created} rounds and generated {scores_generated} scores', 'success')
        
        # Direct to the event page but handle potential errors on the report page
        try:
            return redirect(url_for('reports.standings', event_id=event_id))
        except Exception as e:
            logger.error(f"Error redirecting to standings: {str(e)}")
            return redirect(url_for('reports.index'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error generating test data: {str(e)}")
        flash(f'Error generating test data: {str(e)}', 'error')
        return redirect(url_for('testdata.index'))

@testdata_bp.route('/clear_all')
def clear_all():
    """Redirect to contest clear scores page"""
    try:
        logger.info("Redirecting to contest page for clearing scores (from clear_all route)")
        return redirect(url_for('contest.index'))
    except Exception as e:
        logger.error(f"Error redirecting to contest page: {str(e)}")
        flash(f'Error redirecting to contest page: {str(e)}', 'error')
        return redirect(url_for('testdata.index'))
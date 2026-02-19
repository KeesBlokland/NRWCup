"""
File: app/routes/bp_testdata.py
Version: 1.7.0
Created: 2025-03-26
Updated: 2025-04-15
Description: Test data generation with complete TeamRound deletion
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
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
        
        # Get events for template dropdown — ONLY Pending (=Geplant) events are safe for test data
        # DB stores 'Pending', UI displays 'Geplant'
        events = Event.query.filter_by(status='Pending').order_by(Event.event_date.desc()).all()

        # Auto-select: if only one Pending event, use it as default
        active_event = None
        if len(events) == 1:
            active_event = events[0]

        return render_template('testdata/testdata_main.html',
                              task_types=task_types,
                              teams=teams,
                              judges=judges,
                              events=events,
                              active_event=active_event)
                              
    except SQLAlchemyError as e:
        logger.error(f"Database error in testdata.index: {str(e)}")
        flash('Error loading test data page', 'error')
        return render_template('testdata/testdata_main.html')

@testdata_bp.route('/generate', methods=['POST'])
def generate():
    """Generate test scores using the same code path as real data entry.

    Uses generate_scoresheets_for_round() to create rounds/team_rounds/empty scores,
    then ScoringService.create_score() to fill in values — exactly like a user would.
    """
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

        if event.status != 'Pending':
            flash(f'Testdaten nur für Wettbewerbe mit Status "Geplant" erlaubt (aktuell: {event.status})', 'error')
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
                round_obj = Round(
                    event_id=event_id,
                    round_number=specific_round,
                    status='Active'
                )
                db.session.add(round_obj)
                db.session.flush()
                logger.info(f"Created new round {specific_round} for event {event_id}")

            rounds_to_process = [round_obj]
        else:
            rounds_to_process = []
            for i in range(1, num_rounds + 1):
                round_status = 'Active' if i == num_rounds else 'Completed'
                round_obj = next((r for r in existing_rounds if r.round_number == i), None)
                if not round_obj:
                    round_obj = Round(
                        event_id=event_id,
                        round_number=i,
                        status=round_status
                    )
                    db.session.add(round_obj)
                    db.session.flush()
                    logger.info(f"Created new round {i} for event {event_id}")
                else:
                    round_obj.status = round_status
                rounds_to_process.append(round_obj)

        db.session.commit()

        # Get task types for generating values
        task_types = TaskType.query.filter_by(is_active=True).order_by(TaskType.sort_order).all()

        # Get selected judges
        judges = Teilnehmer.query.filter(Teilnehmer.teilnehmer_id.in_(judge_ids)).all()
        # Use the scoring service — same as the real entry form
        from app.services.services_scoring import ScoringService
        scoring_service = ScoringService()

        rounds_created = 0
        scores_generated = 0

        for round_obj in rounds_to_process:
            # Step 1: Ensure TeamRounds + empty Scores exist
            # Check if team_rounds already exist for this round
            existing_tr_count = TeamRound.query.filter_by(round_id=round_obj.round_id).count()
            if existing_tr_count == 0:
                # First time: create team_rounds and empty score records
                from app.routes.bp_formular import generate_scoresheets_for_round
                generate_scoresheets_for_round(round_obj.round_id)
                logger.info(f"Created scoresheets for round {round_obj.round_number} (was empty)")
            else:
                logger.info(f"Round {round_obj.round_number} already has {existing_tr_count} team_rounds — NOT wiping")

            # Step 2: For each team, generate score values and submit via create_score()
            team_rounds = TeamRound.query.filter_by(round_id=round_obj.round_id).all()

            for team_round in team_rounds:
                # Skip teams not in our selected list
                if team_round.team_id not in team_ids:
                    continue

                # Select which variant each team uses (same for all judges)
                chosen_variants = handle_mutually_exclusive_figures(task_types)

                # Messwerte: generated once by judge 1 (first in list), never regenerated
                # Check if this team_round already has Messwerte from a previous run
                messwertung_codes = ['SEGZEIT', 'LANDGM', 'LANS', 'SEILZ']
                has_messwerte = db.session.query(ScoreValue).join(Score).join(TaskType).filter(
                    Score.team_round_id == team_round.team_round_id,
                    TaskType.code.in_(messwertung_codes)
                ).first() is not None

                if not has_messwerte:
                    segzeit_value = random.randint(170, 230)
                    landing_values = {
                        'LANDGM': generate_landing_score(),
                        'LANS': generate_landing_score(),
                        'SEILZ': generate_landing_score()
                    }

                # Apply score variability
                std_dev = score_variability / 100 * 3

                for judge in judges:
                    score_values = {}

                    for task_type in task_types:
                        if task_type.code in messwertung_codes:
                            # Messwerte: only on first judge, only if not already present
                            if not has_messwerte and judge == judges[0]:
                                if task_type.code == 'SEGZEIT':
                                    score_values[task_type.code] = segzeit_value
                                else:
                                    score_values[task_type.code] = landing_values[task_type.code]
                        elif task_type.name_de and 'Platzrunde' in task_type.name_de:
                            # Only score the chosen variant — leave others absent (like a real judge)
                            if 'platzrunde' in chosen_variants and task_type.type_id == chosen_variants['platzrunde']:
                                score_values[task_type.code] = generate_gaussian_score(std_dev=std_dev)
                        elif task_type.name_de and 'berflug' in task_type.name_de:
                            # Only score the chosen variant — leave others absent (like a real judge)
                            if 'platzu' in chosen_variants and task_type.type_id == chosen_variants['platzu']:
                                score_values[task_type.code] = generate_gaussian_score(std_dev=std_dev)
                        else:
                            value = generate_gaussian_score(std_dev=std_dev)
                            if task_type.max_value is not None:
                                value = min(value, task_type.max_value)
                            score_values[task_type.code] = value

                    # Submit via create_score() — same as the real form
                    scoring_service.create_score(
                        team_round_id=team_round.team_round_id,
                        judge_id=judge.teilnehmer_id,
                        score_values=score_values,
                        notes="Test data generated score"
                    )
                    scores_generated += 1

            rounds_created += 1

        if specific_round > 0:
            logger.info(f"Generated scores for round {specific_round}: {scores_generated} scores via create_score()")
            flash(f'Successfully generated {scores_generated} scores for round {specific_round}', 'success')
        else:
            logger.info(f"Generated {scores_generated} scores across {rounds_created} rounds via create_score()")
            flash(f'Successfully created {rounds_created} rounds and generated {scores_generated} scores', 'success')

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



"""
File: app/routes/bp_testdata.py
Version: 1.7.0
Created: 2025-03-26
Updated: 2025-04-15
Description: Test data generation with complete TeamRound deletion
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session
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

STEIGFLUG_CODES = {'PLTZR', 'PLTZR-M'}
UEBERFLUG_CODES = {'PLTZU', 'PLTZU-OV'}

def handle_mutually_exclusive_figures(task_types):
    """Handle figures that are mutually exclusive (only one gets a value, others are 0)
       Returns dictionary with chosen variants that should be consistent across judges"""

    chosen_variants = {}

    # Group 1: Steigflug variants (PLTZR / PLTZR-M)
    steigflug_variants = [task for task in task_types if task.code in STEIGFLUG_CODES]
    if steigflug_variants:
        chosen_variants['platzrunde'] = random.choice(steigflug_variants).type_id

    # Group 2: Ueberflug variants (PLTZU / PLTZU-OV)
    ueberflug_variants = [task for task in task_types if task.code in UEBERFLUG_CODES]
    if ueberflug_variants:
        chosen_variants['platzu'] = random.choice(ueberflug_variants).type_id

    return chosen_variants

@testdata_bp.route('/clear', methods=['POST'])
def clear_scores():
    """Clear scores for a specific event (or all non-completed events as fallback)"""
    try:
        event_id = request.form.get('event_id', type=int)
        if event_id:
            result = clear_event_data(event_id, clear_scores_only=True)
            flash(f'{result["scores_deleted"]} Bewertungen und {result["team_rounds_deleted"]} Durchgange geloescht', 'success')
        else:
            result = clear_all_scores()
            flash(f'{result["scores_deleted"]} Bewertungen und {result["team_rounds_deleted"]} Durchgange geloescht', 'success')

        return redirect(url_for('testdata.index'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error clearing scores: {str(e)}")
        flash(f'Fehler beim Loeschen: {str(e)}', 'error')
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

        # Restore selected event from session, then fall back to single-event auto-select
        event_id = request.args.get('event_id', type=int) or session.get('testdata_event_id')
        active_event = None
        if event_id:
            active_event = next((e for e in events if e.event_id == event_id), None)
        if not active_event and len(events) == 1:
            active_event = events[0]
        if active_event:
            session['testdata_event_id'] = active_event.event_id

        return render_template('testdata/testdata_main.html',
                              task_types=task_types,
                              teams=teams,
                              judges=judges,
                              events=events,
                              active_event=active_event)
                              
    except SQLAlchemyError as e:
        logger.error(f"Database error in testdata.index: {str(e)}")
        flash('Fehler beim Laden der Testdaten-Seite', 'error')
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
        score_variability = int(request.form.get('score_variability') or 20)  # Percentage
        clear_existing = request.form.get('clear_existing') == 'on'
        event_id = request.form.get('event_id')
        if event_id:
            session['testdata_event_id'] = int(event_id)
        specific_round = int(request.form.get('specific_round') or 0)  # Empty string → 0

        # Get number of rounds
        num_rounds = int(request.form.get('num_rounds') or 1)

        # If num_rounds is 0, redirect to contest page for clearing all scores
        if num_rounds == 0:
            return redirect(url_for('contest.index'))

        # Convert to integers
        team_ids = [int(id) for id in team_ids if id]
        judge_ids = [int(id) for id in judge_ids if id]

        # Validation
        if not team_ids:
            flash('Bitte mindestens ein Team auswaehlen', 'error')
            return redirect(url_for('testdata.index'))

        if not judge_ids:
            flash('Bitte mindestens einen Wertungsrichter auswaehlen', 'error')
            return redirect(url_for('testdata.index'))

        if not event_id:
            flash('Bitte einen Wettbewerb auswaehlen', 'error')
            return redirect(url_for('testdata.index'))

        event_id = int(event_id)
        event = Event.query.get(event_id)
        if not event:
            flash('Wettbewerb nicht gefunden', 'error')
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
                flash(f"Bestehende Bewertungen geloescht ({event.name}): {result['scores_deleted']} Bewertungen, {result['team_rounds_deleted']} Durchgaenge", 'success')
            except Exception as e:
                logger.error(f"Error clearing scores: {str(e)}")
                flash(f"Fehler beim Loeschen der Bewertungen: {str(e)}", 'error')
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

        # Get task types for generating values — build lookup dict to avoid repeated queries
        task_types = TaskType.query.filter_by(is_active=True).order_by(TaskType.sort_order).all()
        task_type_by_code = {t.code: t for t in task_types}

        # Get selected judges
        judges = Teilnehmer.query.filter(Teilnehmer.teilnehmer_id.in_(judge_ids)).all()

        from app.services.services_scoring import ScoringService
        scoring_service = ScoringService()

        rounds_created = 0
        scores_generated = 0

        for round_obj in rounds_to_process:
            # Step 1: Ensure TeamRounds + empty Scores exist
            existing_tr_count = TeamRound.query.filter_by(round_id=round_obj.round_id).count()
            if existing_tr_count == 0:
                from app.routes.bp_formular import generate_scoresheets_for_round
                generate_scoresheets_for_round(round_obj.round_id)
                logger.info(f"Created scoresheets for round {round_obj.round_number} (was empty)")

            team_rounds = TeamRound.query.filter_by(round_id=round_obj.round_id).all()
            std_dev = score_variability / 100 * 3

            # Step 2: Bulk-insert ScoreValues directly — no per-score commits or recalculations
            for team_round in team_rounds:
                if team_round.team_id not in team_ids:
                    continue

                chosen_variants = handle_mutually_exclusive_figures(task_types)

                # Generate Messwerte once per team — store directly on TeamRound
                team_round.mess_segzeit = float(random.randint(170, 230))
                team_round.mess_landgm  = generate_landing_score()
                team_round.mess_lans    = generate_landing_score()
                team_round.mess_seilz   = generate_landing_score()

                # Clear existing ScoreValues for this team_round to avoid duplicates
                score_ids = [s.score_id for s in Score.query.filter_by(
                    team_round_id=team_round.team_round_id).all()]
                if score_ids:
                    ScoreValue.query.filter(ScoreValue.score_id.in_(score_ids)).delete(
                        synchronize_session='fetch')

                for judge in judges:
                    # Get or create the Score record
                    score = Score.query.filter_by(
                        team_round_id=team_round.team_round_id,
                        judge_id=judge.teilnehmer_id
                    ).first()
                    if not score:
                        score = Score(
                            team_round_id=team_round.team_round_id,
                            judge_id=judge.teilnehmer_id,
                            entered_at=datetime.utcnow(),
                            notes="Test data"
                        )
                        db.session.add(score)
                        db.session.flush()
                    else:
                        score.entered_at = datetime.utcnow()

                    # Build values for this judge (quality figures only — Messwerte on TeamRound)
                    for task_type in task_types:
                        if task_type.is_messwertung:
                            continue  # stored on TeamRound, not ScoreValue
                        code = task_type.code
                        value = None

                        if code in STEIGFLUG_CODES:
                            if 'platzrunde' in chosen_variants and task_type.type_id == chosen_variants['platzrunde']:
                                value = generate_gaussian_score(std_dev=std_dev)
                        elif code in UEBERFLUG_CODES:
                            if 'platzu' in chosen_variants and task_type.type_id == chosen_variants['platzu']:
                                value = generate_gaussian_score(std_dev=std_dev)
                        else:
                            value = generate_gaussian_score(std_dev=std_dev)
                            if task_type.max_value is not None:
                                value = min(value, task_type.max_value)

                        if value is not None:
                            db.session.add(ScoreValue(
                                score_id=score.score_id,
                                task_type_id=task_type.type_id,
                                value=float(value)
                            ))
                    scores_generated += 1

            # Single commit per round — all ScoreValues inserted at once
            db.session.commit()

            # Step 3: Calculate raw scores and normalize once per round
            team_rounds_scored = TeamRound.query.filter_by(round_id=round_obj.round_id).all()
            for tr in team_rounds_scored:
                if tr.team_id in team_ids:
                    tr.raw_score = scoring_service.aggregate_judge_scores(tr.team_round_id)

            db.session.flush()
            normalized = scoring_service.normalize_round_scores(round_obj.round_id)
            for tr in team_rounds_scored:
                if tr.team_id in normalized:
                    tr.normalized_score = normalized[tr.team_id]

            db.session.commit()
            rounds_created += 1

        if specific_round > 0:
            logger.info(f"Generated scores for round {specific_round}: {scores_generated} scores via create_score()")
            flash(f'{scores_generated} Bewertungen fuer Durchgang {specific_round} generiert', 'success')
        else:
            logger.info(f"Generated {scores_generated} scores across {rounds_created} rounds via create_score()")
            flash(f'{rounds_created} Durchgaenge und {scores_generated} Bewertungen generiert', 'success')

        try:
            return redirect(url_for('reports.standings', event_id=event_id))
        except Exception as e:
            logger.error(f"Error redirecting to standings: {str(e)}")
            return redirect(url_for('reports.index'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error generating test data: {str(e)}")
        flash(f'Fehler beim Generieren der Testdaten: {str(e)}', 'error')
        return redirect(url_for('testdata.index'))



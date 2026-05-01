# File: app/routes/bp_scoring.py

"""
File: app/routes/bp_scoring.py
Version: 2.4.0
Created: 2025-03-02
Updated: 2025-05-04
Description: Scoring blueprint with raw score calculation, next round generation, and score locking
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session
from functools import wraps
from app.models import db, Score, TaskType, TeamRound, Teilnehmer, Team, Round, Event, ScoreValue
from app.services.services_scoring import ScoringService
from app.utils.utils_base_controller import BaseController
from app.utils.audit import audit_log
from sqlalchemy.exc import SQLAlchemyError
from app.services.services_rounds import RoundService
from app.utils.scoring_constants import get_scoring_constants
from datetime import datetime
import math

import logging
import traceback

round_service = RoundService()

# Admin password in config file
from app.config import Config
ADMIN_PASSWORD = Config.ADMIN_PASSWORD

# Admin decorator (shared)
from app.utils.auth import admin_required

# Configure logger
logger = logging.getLogger(__name__)


scoring_bp = Blueprint('scoring', __name__)

# Initialize service
scoring_service = ScoringService()

@scoring_bp.route('/')
def index():
    """Redirect to unified scoring and standings view"""
    return redirect(url_for('scoring.score_list'))

@scoring_bp.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    """Simple admin login for score management"""
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['is_admin'] = True
            flash('Admin-Zugang aktiviert', 'success')
            return redirect(url_for('scoring.score_list'))
        else:
            flash('Falsches Passwort', 'error')
    return render_template('scoring/admin_login.html')

@scoring_bp.route('/admin_logout')
def admin_logout():
    """Logout admin"""
    session.pop('is_admin', None)
    flash('Admin-Zugang deaktiviert', 'success')
    return redirect(url_for('scoring.score_list'))


@scoring_bp.route('/lock/<int:score_id>', methods=['POST'])
def lock_score(score_id):
    """Lock a score after verification"""
    try:
        logger.info(f"Locking score {score_id}, headers: {request.headers}")
        # Get the score
        score = Score.query.get_or_404(score_id)
        
        # Get judge name
        judge = Teilnehmer.query.get(score.judge_id)
        judge_name = judge.name if judge else f"Judge {score.judge_id}"
        
        # Set lock fields
        score.locked = True
        score.locked_at = datetime.utcnow()
        score.locked_by = judge_name
        audit_log('scores', score_id, 'locked', None, judge_name)
        db.session.commit()

        logger.info(f"Score {score_id} locked successfully by {judge_name}")
        flash('Bewertung gesperrt', 'success')

        # Check if the request comes from AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"status": "success", "message": "Bewertung gesperrt"})

        # For form submissions, redirect to caller-specified URL or view score page
        next_url = request.form.get('next') or request.args.get('next')
        if next_url:
            return redirect(next_url)
        return redirect(url_for('scoring.view_score', score_id=score_id))
        
    except Exception as e:
        db.session.rollback()
        error_msg = f"Error locking score: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"status": "error", "message": error_msg}), 500
            
        flash(f'Fehler beim Sperren: {str(e)}', 'error')
        return redirect(url_for('scoring.score_list'))

@scoring_bp.route('/unlock/<int:score_id>', methods=['POST'])
def unlock_score(score_id):
    """Unlock a score"""
    try:
        logger.info(f"Unlocking score {score_id}, headers: {request.headers}")
        score = Score.query.get_or_404(score_id)
        score.locked = False
        score.locked_at = None
        score.locked_by = None
        db.session.commit()
        audit_log('scores', score_id, 'unlocked', None, 'user')
        logger.info(f"Score {score_id} unlocked successfully")
        flash('Bewertung entsperrt', 'success')
        
        # Check if the request comes from AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"status": "success", "message": "Bewertung entsperrt"})
            
        # For form submissions, redirect to view score page (303 forces GET)
        return redirect(url_for('scoring.view_score', score_id=score_id), 303)
        
    except Exception as e:
        db.session.rollback()
        error_msg = f"Error unlocking score: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"status": "error", "message": error_msg}), 500
            
        flash(f'Fehler beim Entsperren: {str(e)}', 'error')
        return redirect(request.referrer or url_for('scoring.score_list'))

@scoring_bp.route('/scoresheet')
def scoresheet():
    """Display scoring form pre-populated with selected parameters"""
    logger.info("Accessing scoresheet form")
    try:
        active_figures = scoring_service.get_active_figures()
        active_event = Event.query.filter_by(status='Active').first()
        num_judges = active_event.num_judges if active_event and active_event.num_judges else 3
        judges = scoring_service.get_judges(limit=num_judges)

        # Get parameters from request
        team_round_id = request.args.get('team_round_id')
        round_id = request.args.get('round_id', type=int)
        team_id = request.args.get('team_id', type=int)
        judge_id = request.args.get('judge_id', type=int)
        
        # Variables for template
        pre_selected_judge = None
        pre_selected_round = None
        pre_selected_team = None
        selected_round = None
        selected_team = None
        selected_judge = None
        event = None
        active_event = None
        
        # Get active event
        active_event = Event.query.filter_by(status='Active').first()
        
        # If round_id is provided, get the associated event
        if round_id:
            round_obj = Round.query.get(round_id)
            if round_obj and round_obj.event_id:
                event = Event.query.get(round_obj.event_id)
                selected_round = round_obj  # Store the full round object
                
                if team_id:
                    team = Team.query.get(team_id)
                    if team:
                        selected_team = team  # Store the full team object
        
        # If no specific event found, use active event
        if not event and active_event:
            event = active_event
            
        # Set up other variables
        if not team_round_id and round_id and team_id:
            team_round = TeamRound.query.filter_by(
                round_id=round_id,
                team_id=team_id
            ).first()
            
            if team_round:
                team_round_id = team_round.team_round_id
            else:
                # If there's no team round, but we have round and team
                if round_id:
                    round_obj = Round.query.get(round_id)
                    if round_obj:
                        pre_selected_round = round_obj.round_number
                        
                if team_id:
                    team = Team.query.get(team_id)
                    if team:
                        pre_selected_team = team.team_nummer
        
        if judge_id:
            pre_selected_judge = judge_id
            judge = Teilnehmer.query.get(judge_id)
            if judge:
                selected_judge = judge  # Store the full judge object
        
        rounds = Round.query.all()
        teams = Team.query.filter_by(status='active').all()
        
        logger.info(f"Scoresheet parameters: round_id={round_id}, team_id={team_id}, judge_id={judge_id}")
        
        return render_template('scoring/score_form.html',
                             figures=active_figures,
                             judges=judges,
                             score=None,
                             team_round_id=team_round_id,
                             pre_selected_round=pre_selected_round,
                             pre_selected_team=pre_selected_team,
                             pre_selected_judge=pre_selected_judge,
                             selected_round=selected_round,
                             selected_team=selected_team,
                             selected_judge=selected_judge,
                             rounds=rounds,
                             teams=teams,
                             event=event,
                             active_event=active_event)
    except SQLAlchemyError as e:
        logger.error(f"Database error in scoresheet: {str(e)}")
        flash('Fehler beim Laden der Wertungsdaten', 'error')
        return redirect(url_for('scoring.score_list'))

@scoring_bp.route('/list')
def score_list():
    """Display unified scoring and standings view"""
    logger.info("Accessing unified scoring and standings view")
    try:
        # Get filter parameters
        event_id = request.args.get('event_id', type=int)
        round_id = request.args.get('round_id', type=int)
        judge_id = request.args.get('judge_id', type=int)
        
        # Get all visible events
        events = Event.query.filter_by(is_hidden=False).order_by(Event.event_date.desc()).all()

        # Get active event if not specified
        if not event_id:
            # Restore from session if user previously selected one
            event_id = session.get('scoring_event_id')
        if not event_id:
            active_event = Event.query.filter_by(status='Active', is_hidden=False).first()
            if active_event:
                event_id = active_event.event_id
            elif events:
                event_id = events[0].event_id

        # Remember the selection for this browser session (shared with Startliste)
        if event_id:
            session['scoring_event_id'] = event_id
            session['formular_event_id'] = event_id
                
        event = Event.query.get(event_id) if event_id else None
        
        # Get rounds for this event
        rounds = Round.query.filter_by(event_id=event_id).order_by(Round.round_number).all() if event_id else []
        
        # Check round completion status
        can_generate_next_round = False
        round_status_info = None
        any_round_has_scores = False
        selected_round_obj = None
        next_round_number = None

        if event_id and rounds:
            from app.utils.round_status import round_completion_status
            latest_round = rounds[-1]
            selected_round_obj = latest_round
            round_status_info = round_completion_status(latest_round.round_id)
            any_round_has_scores = round_status_info['scored_teams'] > 0

            if event.status not in ('Completed', 'Published'):
                latest_complete = (
                    round_status_info['total_teams'] > 0 and
                    round_status_info['scored_teams'] == round_status_info['total_teams']
                )
                if latest_complete:
                    # Latest round fully scored — show button, next round may or may not exist yet
                    can_generate_next_round = True
                    next_round_number = latest_round.round_number + 1
                elif len(rounds) >= 2:
                    # Latest round has some scores but is not yet complete — in progress, no button
                    # OR latest round has no scores at all — D(n) already created, D(n-1) was complete
                    prev_round = rounds[-2]
                    prev_status = round_completion_status(prev_round.round_id)
                    if (prev_status['total_teams'] > 0 and
                            prev_status['scored_teams'] == prev_status['total_teams'] and
                            round_status_info['scored_teams'] == 0):
                        # Previous round complete, current round empty (just created) — no create button,
                        # but show prev round status so badge is informative
                        selected_round_obj = prev_round
                        round_status_info = prev_status
        
        # Validate round_id belongs to this event; reset if not
        valid_round_ids = [r.round_id for r in rounds]
        if round_id and round_id not in valid_round_ids:
            round_id = None

        # If round_id is not specified but there are rounds, use the latest one
        if not round_id and rounds:
            round_id = rounds[-1].round_id
            
        # Get judges limited to event's num_judges setting
        num_judges = event.num_judges if event and event.num_judges else 3
        judges = scoring_service.get_judges(limit=num_judges)

        # Get all teams
        # teams = Team.query.filter_by(status='active').order_by(Team.team_nummer).all()
        if round_id:
            # Get all active teams, ordered by start_order for this round where available.
            # outerjoin so teams added after round creation still appear (no TeamRound yet).
            teams = Team.query.outerjoin(
                TeamRound,
                db.and_(Team.team_id == TeamRound.team_id, TeamRound.round_id == round_id)
            ).filter(Team.status == 'active')\
                .order_by(db.nullslast(TeamRound.start_order), Team.team_nummer)\
                .all()
        else:
            # Fall back to team number order if no round is selected
            teams = Team.query.filter_by(status='active').order_by(Team.team_nummer).all()

        # Get completed scoresheets with eager loading
        query = Score.query.options(
            db.joinedload(Score.values).joinedload(ScoreValue.task_type),
            db.joinedload(Score.team_round)
        )
        
        if round_id:
            query = query.join(TeamRound).filter(TeamRound.round_id == round_id)
        
        if judge_id:
            query = query.filter(Score.judge_id == judge_id)
            
        completed_scores = query.all()
        
        # Convert to a dictionary for easier lookup
        ALWAYS_MANDATORY, EXCLUSIVE_GROUPS = get_scoring_constants()
        completed_dict = {}
        has_quality_set = set()   # at least one quality figure entered
        fully_complete_set = set()  # all mandatory figures + one per exclusive group
        for score in completed_scores:
            team_round = score.team_round
            if team_round:
                key = f"{team_round.round_id}_{team_round.team_id}_{score.judge_id}"
                completed_dict[key] = score
                sv_codes = {sv.task_type.code for sv in score.values if sv.task_type
                            and not sv.task_type.is_messwertung}
                has_quality = bool({sv.task_type.code for sv in score.values
                                    if sv.task_type and not sv.task_type.is_messwertung
                                    and sv.value is not None})
                if has_quality:
                    has_quality_set.add(key)
                # Fully complete: all mandatory figures present (zero is valid) +
                # one from each exclusive group present (zero is valid — team may have crashed)
                if (ALWAYS_MANDATORY.issubset(sv_codes) and
                        all(group & sv_codes for group in EXCLUSIVE_GROUPS)):
                    fully_complete_set.add(key)
        
        # Create mapping for team rounds
        team_rounds = {}
        for round_obj in rounds:
            for team in teams:
                key = f"{round_obj.round_id}_{team.team_id}"
                team_round = TeamRound.query.filter_by(
                    round_id=round_obj.round_id,
                    team_id=team.team_id
                ).first()
                if team_round:
                    team_rounds[key] = team_round
        
        # Calculate standings
        standings = None
        standings_rounds = []
        if event_id:
            standings, standings_rounds = scoring_service.calculate_final_standings(event_id)
            
        # Quality-only per-judge raw score for display purposes
        def get_raw_score(score):
            """Sum quality (non-Messwertung) score values for a single judge."""
            if not score:
                return None
            if not hasattr(score, 'values') or not score.values:
                score = Score.query.options(
                    db.joinedload(Score.values).joinedload(ScoreValue.task_type)
                ).get(score.score_id)
                if not score or not score.values:
                    return None
            raw_score = 0
            for sv in score.values:
                if not sv.task_type or sv.value is None:
                    continue
                if sv.task_type.is_messwertung:
                    continue
                raw_score += sv.value * (sv.task_type.k_factor or 1)
            return raw_score
            
        return render_template('scoring/unified_scoring.html',
                             events=events,
                             event=event,
                             rounds=rounds,
                             judges=judges,
                             teams=teams,
                             team_rounds=team_rounds,
                             completed_scores=completed_dict,
                             has_quality_scores=has_quality_set,
                             fully_complete_scores=fully_complete_set,
                             selected_round=round_id,
                             selected_judge=judge_id,
                             standings=standings,
                             standings_rounds=standings_rounds,
                             getRawScore=get_raw_score,
                             can_generate_next_round=can_generate_next_round,
                             any_round_has_scores=any_round_has_scores,
                             round_status_info=round_status_info,
                             status_round=selected_round_obj,
                             next_round_number=next_round_number,
                             latest_round_id=rounds[-1].round_id if rounds else None,
                             estimated_rounds=event.estimated_rounds if event else 4)
    except SQLAlchemyError as e:
        logger.error(f"Database error in list: {str(e)}")
        flash('Fehler beim Laden der Wertungsdaten', 'error')
        return render_template('scoring/unified_scoring.html')
    
@scoring_bp.route('/api/score/<int:score_id>')
def api_score(score_id):
    """API endpoint to get score data for the modal view"""
    logger.info(f"API request for score {score_id}")
    try:
        # Get score details with eager loading of related objects
        score = Score.query.options(
            db.joinedload(Score.values).joinedload(ScoreValue.task_type)
        ).get_or_404(score_id)
        
        team_round = TeamRound.query.get_or_404(score.team_round_id)
        round_obj = Round.query.get_or_404(team_round.round_id)
        team = Team.query.get_or_404(team_round.team_id)
        judge = Teilnehmer.query.get_or_404(score.judge_id)
        
        # Build response with detailed figure information
        figures_data = []
        total_points = 0
        
        for score_value in score.values:
            if not score_value.task_type:
                continue
                
            value = score_value.value
            k_factor = score_value.task_type.k_factor or 1
            points = value * k_factor if value is not None else None
            
            if points is not None:
                total_points += points
                
            figures_data.append({
                'name': score_value.task_type.name_de,
                'value': value,
                'k_factor': k_factor,
                'points': points
            })
        
        # Sort by task sort_order if available
        active_figures = scoring_service.get_active_figures()
        sort_order_map = {fig.code: i for i, fig in enumerate(active_figures)}
        
        # Sort figures_data by the same order as active_figures
        name_order_map = {fig.name_de: i for i, fig in enumerate(active_figures)}
        figures_data.sort(key=lambda x: name_order_map.get(x.get('name'), 999))
        
        return jsonify({
            'score_id': score.score_id,
            'round_id': round_obj.round_id,
            'round_number': round_obj.round_number,
            'team_id': team.team_id,
            'team_number': team.team_nummer,
            'judge_id': judge.teilnehmer_id,
            'judge_name': judge.name,
            'entered_at': score.entered_at.isoformat() if score.entered_at else None,
            'figures': figures_data,
            'total_points': total_points
        })
        
    except Exception as e:
        logger.error(f"Error generating API response for score {score_id}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500
    

@scoring_bp.route('/enter_score', methods=['POST'])
def enter_score():
    logger.info("=== SCORE SUBMISSION STARTED ===")
    logger.info(f"Form data: {request.form}")

    try:
        # Check event status via team_round_id or round
        _team_round_id = request.form.get('team_round_id', type=int)
        _round_number = request.form.get('round_number', type=int)
        if _team_round_id:
            _tr = TeamRound.query.get(_team_round_id)
            if _tr:
                _round_obj = Round.query.get(_tr.round_id)
                if _round_obj:
                    _event = Event.query.get(_round_obj.event_id)
                    if _event and _event.status in ('Completed', 'Published'):
                        flash('Abgeschlossene Wettbewerbe können nicht geändert werden', 'error')
                        return redirect(url_for('scoring.score_list'))

        # Get team_round_id or find/create it
        team_round_id = request.form.get('team_round_id', type=int)
        round_id = None
        
        if not team_round_id:
            # Find or create the round and team round
            round_number = request.form.get('round_number', type=int)
            team_number = request.form.get('start_number', type=int)
            
            if not round_number or not team_number:
                flash('Durchgang und Start-Nr. sind erforderlich', 'error')
                return redirect(url_for('scoring.scoresheet'))
            
            # Get or create round
            round_obj = round_service.get_or_create_round(round_number)
            if not round_obj:
                flash(f'Fehler beim Erstellen von Durchgang {round_number}', 'error')
                return redirect(url_for('scoring.scoresheet'))
                
            round_id = round_obj.round_id
            
            # Find the team with this number
            team = Team.query.filter_by(team_nummer=team_number).first()
            if not team:
                flash(f'Team {team_number} nicht gefunden', 'error')
                return redirect(url_for('scoring.scoresheet'))
                
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
                    start_order=team_number
                )
                db.session.add(team_round)
                db.session.flush()
                
            team_round_id = team_round.team_round_id
        else:
            # Get the round_id from team_round
            team_round = TeamRound.query.get(team_round_id)
            if team_round:
                round_id = team_round.round_id
        
        # Get judge ID
        judge_id = request.form.get('judge_id', type=int)
        
        if not team_round_id or not judge_id:
            flash('Fehler: Team-Runde oder Punktrichter fehlt', 'error')
            return redirect(url_for('scoring.scoresheet'))
        
        # Extract score values from form
        score_values = {}
        for field_name, value in request.form.items():
            if field_name.startswith('score_'):
                # Include empty values as 0 or leave them as empty string
                # This allows zero scores to be properly submitted
                code = field_name[6:]  # Remove 'score_' prefix
                score_values[code] = value
        
        # Create or update score
        score = scoring_service.create_score(
            team_round_id=team_round_id,
            judge_id=judge_id,
            score_values=score_values,
            notes=request.form.get('notes', '')
        )
        
        flash('Bewertung erfolgreich gespeichert', 'success')
        logger.info(f"=== SCORE SUBMISSION COMPLETED SUCCESSFULLY ===")
        
        # Find active round for redirect
        active_round = None
        event_id = None
        
        if round_id:
            round_obj = Round.query.get(round_id)
            if round_obj:
                event_id = round_obj.event_id
                
                # Find active round in this event
                active_round = Round.query.filter_by(
                    event_id=event_id,
                    status='Active'
                ).first()
        
        # Redirect to scoresheet list with appropriate parameters
        if active_round:
            return redirect(url_for('scoring.score_list', event_id=event_id, round_id=active_round.round_id))
        else:
            return redirect(url_for('scoring.score_list'))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving score: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        flash(f'Fehler beim Speichern der Bewertung: {str(e)}', 'error')
        logger.error("=== SCORE SUBMISSION FAILED ===")
        
    # Fallback redirect
    return redirect(url_for('scoring.score_list'))

@scoring_bp.route('/update/<int:score_id>', methods=['POST'])
def update_score(score_id):
    """Update an existing score"""
    logger.info(f"Updating score with ID {score_id}")
    try:
        # Get the score to update
        score = scoring_service.get_by_id(score_id)
        if not score:
            flash('Bewertung nicht gefunden', 'error')
            return redirect(url_for('scoring.score_list'))
        
        # Check if event is completed/published
        team_round = TeamRound.query.get(score.team_round_id)
        if team_round:
            round_obj = Round.query.get(team_round.round_id)
            if round_obj:
                event = Event.query.get(round_obj.event_id)
                if event and event.status in ('Completed', 'Published'):
                    flash('Abgeschlossene Wettbewerbe können nicht geändert werden', 'error')
                    return redirect(url_for('scoring.score_list'))

        # Check if score is locked and user is not admin
        if score.locked and not session.get('is_admin'):
            flash('Diese Bewertung ist gesperrt und kann nicht bearbeitet werden', 'error')
            return redirect(url_for('scoring.view_score', score_id=score_id))
        
        # Extract score values from form
        score_values = {}
        for field_name, value in request.form.items():
            if field_name.startswith('score_') and value:
                code = field_name[6:]  # Remove 'score_' prefix
                score_values[code] = value

        # Preserve locked status before update
        was_locked = score.locked
        locked_at = score.locked_at
        locked_by = score.locked_by

        # Update score (create_score uses upsert logic)
        updated_score = scoring_service.create_score(
            team_round_id=score.team_round_id,
            judge_id=score.judge_id,
            score_values=score_values,
            notes=request.form.get('notes', '')
        )

        # Restore locked status if it was locked
        if was_locked and updated_score:
            updated_score.locked = was_locked
            updated_score.locked_at = locked_at
            updated_score.locked_by = locked_by
            db.session.commit()
        
        audit_log('scores', score_id, 'updated', None, str(score_values))
        db.session.commit()
        flash('Bewertung erfolgreich aktualisiert', 'success')
        logger.info(f"Score {score_id} updated successfully")

        next_url = request.form.get('next')
        if next_url:
            return redirect(next_url)
        return redirect(url_for('scoring.score_list'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating score: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        flash(f'Fehler beim Aktualisieren der Bewertung: {str(e)}', 'error')

    return redirect(url_for('scoring.score_list'))


@scoring_bp.route('/view/<int:score_id>')
def view_score(score_id):
    """View and edit score details using the unified scoresheet template"""
    logger.info(f"Viewing score with ID {score_id}")
    try:
        # Get the score with eager loading of values and task types
        score = Score.query.options(
            db.joinedload(Score.values).joinedload(ScoreValue.task_type)
        ).get_or_404(score_id)
        
        # Explicitly fetch related objects
        team_round = TeamRound.query.get_or_404(score.team_round_id)
        round_obj = Round.query.get_or_404(team_round.round_id)
        team = Team.query.get_or_404(team_round.team_id)
        
        # Get event related to round
        event = None
        active_event = None
        
        if round_obj and round_obj.event_id:
            event = Event.query.get(round_obj.event_id)
            
        # If no specific event found, use active event
        if not event:
            active_event = Event.query.filter_by(status='Active').first()
            event = active_event
        
        # Get active figures — exclude Messwerte (those are on TeamRound, not per-judge)
        active_figures = [f for f in scoring_service.get_active_figures() if not f.is_messwertung]

        # Create a mapping of original values by task_type code
        value_map = {}
        for value in score.values:
            if value.task_type and not value.task_type.is_messwertung:
                value_map[value.task_type.code] = value.value
                logger.debug(f"Mapped {value.task_type.code} -> {value.value}")

        # Determine Kür choices for visual guidance
        # First score (by score_id) with a non-zero Kür value sets the variant
        KUER_GROUPS = {
            'platzrunde': ['PLTZR', 'PLTZR-M'],
            'platzueberflug': ['PLTZU', 'PLTZU-OV'],
        }
        kuer_choices = {}  # group -> chosen code (or None if not yet chosen)
        all_scores_for_tr = Score.query.filter_by(team_round_id=team_round.team_round_id)\
            .order_by(Score.score_id).all()
        for group, codes in KUER_GROUPS.items():
            chosen = None
            for s in all_scores_for_tr:
                for sv in s.values:
                    if sv.task_type and sv.task_type.code in codes and sv.value and sv.value > 0:
                        chosen = sv.task_type.code
                        break
                if chosen:
                    break
            kuer_choices[group] = chosen

        # Build prev/next judge navigation for the same team_round
        sibling_scores = []
        current_index = None
        for idx, s in enumerate(all_scores_for_tr):
            sibling_scores.append({'score_id': s.score_id, 'judge_name': s.judge.name if s.judge else f'R{idx+1}'})
            if s.score_id == score.score_id:
                current_index = idx
        prev_score_id = sibling_scores[current_index - 1]['score_id'] if current_index and current_index > 0 else None
        next_score_id = sibling_scores[current_index + 1]['score_id'] if current_index is not None and current_index < len(sibling_scores) - 1 else None

        # Get referer parameters for the back button
        referer_params = {}
        if request.referrer:
            try:
                from urllib.parse import urlparse, parse_qs
                parsed_url = urlparse(request.referrer)
                query_params = parse_qs(parsed_url.query)

                if 'event_id' in query_params:
                    referer_params['event_id'] = query_params['event_id'][0]
                if 'round_id' in query_params:
                    referer_params['round_id'] = query_params['round_id'][0]
                if 'judge_id' in query_params:
                    referer_params['judge_id'] = query_params['judge_id'][0]
            except Exception:
                logger.warning("Failed to parse referrer URL parameters")

        # Pass all objects to the unified template
        return render_template('scoring/score_form.html',
                              score=score,
                              figures=active_figures,
                              score_team_round=team_round,
                              team_round_round=round_obj,
                              team_round_team=team,
                              value_map=value_map,
                              kuer_choices=kuer_choices,
                              referer_params=referer_params,
                              judges=scoring_service.get_judges(),
                              event=event,
                              active_event=active_event,
                              prev_score_id=prev_score_id,
                              next_score_id=next_score_id,
                              sibling_scores=sibling_scores,
                              current_score_index=current_index)
    except Exception as e:
        logger.error(f"Error viewing score: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        flash('Fehler beim Laden der Bewertung', 'error')
        return redirect(url_for('scoring.score_list'))

@scoring_bp.route('/combined/<int:round_id>/<int:team_id>')
def combined_view(round_id, team_id):
    """Show all judge score columns for one team/round on a single page."""
    try:
        round_obj = Round.query.get_or_404(round_id)
        team = Team.query.get_or_404(team_id)
        event = Event.query.get(round_obj.event_id) if round_obj.event_id else None
        if not event:
            event = Event.query.filter_by(status='Active').first()

        team_round = TeamRound.query.filter_by(
            round_id=round_id, team_id=team_id
        ).first()

        all_figures = scoring_service.get_active_figures()
        active_figures = [f for f in all_figures if not f.is_messwertung]
        num_judges = event.num_judges if event and event.num_judges else 3
        judges = scoring_service.get_judges(limit=num_judges)

        KUER_GROUPS = {
            'platzrunde': ['PLTZR', 'PLTZR-M'],
            'platzueberflug': ['PLTZU', 'PLTZU-OV'],
        }

        # Build per-judge data: value_map (quality figures only), locked, score_id
        all_scores = []
        if team_round:
            all_scores = Score.query.options(
                db.joinedload(Score.values).joinedload(ScoreValue.task_type)
            ).filter_by(team_round_id=team_round.team_round_id)\
             .order_by(Score.score_id).all()

            # Auto-create Score records for any judges not yet in this team_round
            existing_judge_ids = {s.judge_id for s in all_scores}
            new_scores_created = False
            for judge in judges:
                if judge.teilnehmer_id not in existing_judge_ids:
                    new_score = Score(
                        team_round_id=team_round.team_round_id,
                        judge_id=judge.teilnehmer_id,
                        entered_at=datetime.utcnow()
                    )
                    db.session.add(new_score)
                    new_scores_created = True
            if new_scores_created:
                db.session.commit()
                all_scores = Score.query.options(
                    db.joinedload(Score.values).joinedload(ScoreValue.task_type)
                ).filter_by(team_round_id=team_round.team_round_id)\
                 .order_by(Score.score_id).all()

        # Kuer choices: first non-zero value across all scores wins
        kuer_choices = {}
        for group, codes in KUER_GROUPS.items():
            chosen = None
            for s in all_scores:
                for sv in s.values:
                    if sv.task_type and sv.task_type.code in codes and sv.value and sv.value > 0:
                        chosen = sv.task_type.code
                        break
                if chosen:
                    break
            kuer_choices[group] = chosen

        judge_data = []
        for idx, score in enumerate(all_scores):
            value_map = {}
            for sv in score.values:
                if sv.task_type and not sv.task_type.is_messwertung:
                    value_map[sv.task_type.code] = sv.value
            judge_data.append({
                'score': score,
                'value_map': value_map,
            })

        # Pad to num_judges slots (empty dict for judges without a score record yet)
        while len(judge_data) < len(judges):
            judge_data.append({'score': None, 'value_map': {}})

        return render_template(
            'scoring/combined_score_form.html',
            round_obj=round_obj,
            team=team,
            event=event,
            figures=active_figures,
            judges=judges,
            judge_data=judge_data,
            team_round=team_round,
            kuer_choices=kuer_choices,
        )
    except Exception as e:
        logger.error(f"Error in combined_view: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        flash('Fehler beim Laden der kombinierten Ansicht', 'error')
        return redirect(url_for('scoring.score_list'))


@scoring_bp.route('/reset_kuer/<int:team_round_id>/<group>', methods=['POST'])
def reset_kuer(team_round_id, group):
    """Zero out all ScoreValues for both variants in a Kur group, releasing the mutex lock."""
    KUER_GROUPS = {
        'platzrunde': ['PLTZR', 'PLTZR-M'],
        'platzueberflug': ['PLTZU', 'PLTZU-OV'],
    }
    if group not in KUER_GROUPS:
        flash('Unbekannte Kur-Gruppe', 'error')
        return redirect(request.referrer or url_for('scoring.score_list'))
    codes = KUER_GROUPS[group]
    team_round = TeamRound.query.get_or_404(team_round_id)
    scores = Score.query.filter_by(team_round_id=team_round_id).all()
    for score in scores:
        for sv in score.values:
            if sv.task_type and sv.task_type.code in codes:
                sv.value = None
    db.session.commit()
    flash(f'Kur-Variante zuruckgesetzt', 'success')
    return redirect(url_for('scoring.combined_view',
                            round_id=team_round.round_id,
                            team_id=team_round.team_id))


@scoring_bp.route('/messwerte/<int:team_round_id>', methods=['POST'])
def save_messwerte(team_round_id):
    """Save Messwerte (objective measurements) directly on TeamRound."""
    team_round = TeamRound.query.get_or_404(team_round_id)
    try:
        segzeit_raw = request.form.get('mess_segzeit', '').strip()
        if segzeit_raw != '':
            team_round.mess_segzeit = float(segzeit_raw)

        for col in ['mess_seilz', 'mess_landgm', 'mess_lans']:
            val = request.form.get(col, '').strip()
            if val != '':
                setattr(team_round, col, int(val))

        db.session.commit()
        scoring_service.update_team_round_scores(team_round_id)
    except (ValueError, TypeError) as e:
        db.session.rollback()
        logger.error(f"Error saving Messwerte for team_round {team_round_id}: {e}")
        flash('Fehler beim Speichern der Messwerte', 'error')

    next_url = request.form.get('next')
    return redirect(next_url or url_for('scoring.score_list'))


@scoring_bp.route('/generate_next_round', methods=['POST'])
def generate_next_round():
    """Generate the next round with scoresheets based on previous round results"""
    try:
        event_id = request.form.get('event_id', type=int)

        if not event_id:
            flash('Keine Veranstaltung ausgewählt', 'error')
            return redirect(url_for('scoring.score_list'))

        # Check if event is completed/published
        event = Event.query.get(event_id)
        if event and event.status in ('Completed', 'Published'):
            flash('Abgeschlossene Wettbewerbe können nicht geändert werden', 'error')
            return redirect(url_for('scoring.score_list'))

        # Get rounds for this event
        rounds = Round.query.filter_by(event_id=event_id).order_by(Round.round_number).all()
        
        if not rounds:
            flash('Keine Durchgänge für diese Veranstaltung gefunden', 'error')
            return redirect(url_for('scoring.score_list'))
        
        # Find the highest round number with scores (the "source" round)
        highest_round_number = max(r.round_number for r in rounds)
        last_round = next((r for r in rounds if r.round_number == highest_round_number), None)

        if not last_round:
            flash('Letzter Durchgang nicht gefunden', 'error')
            return redirect(url_for('scoring.score_list'))

        # If the latest round has no scores, the source is the previous round
        source_round = last_round
        tr_count = TeamRound.query.filter_by(round_id=last_round.round_id).filter(TeamRound.raw_score != None).count()
        if tr_count == 0 and len(rounds) >= 2:
            source_round = rounds[-2]

        # Check if next round after source already exists
        next_round_number = source_round.round_number + 1
        existing_next = next((r for r in rounds if r.round_number == next_round_number), None)

        if existing_next:
            # Next round already exists — idempotent, just go to it
            return redirect(url_for('scoring.score_list', event_id=event_id, round_id=existing_next.round_id))

        # Guard: refuse to create next round if source round is not fully scored
        from app.utils.round_status import round_completion_status
        src_status = round_completion_status(source_round.round_id)
        if src_status['scored_teams'] < src_status['total_teams']:
            flash(
                f'Durchgang {source_round.round_number} ist noch nicht vollständig bewertet '
                f'({src_status["scored_teams"]}/{src_status["total_teams"]} Teams). '
                f'Bitte alle Bewertungen abschliessen bevor der nächste Durchgang erstellt wird.',
                'error'
            )
            return redirect(url_for('scoring.score_list', event_id=event_id))

        # Calculate raw and normalized scores for the source round
        team_rounds = TeamRound.query.filter_by(round_id=source_round.round_id).all()
        for team_round in team_rounds:
            raw_score = scoring_service.aggregate_judge_scores(team_round.team_round_id)
            team_round.raw_score = raw_score

        db.session.flush()
        normalized_scores = scoring_service.normalize_round_scores(source_round.round_id)

        team_rounds_with_scores = []
        for team_round in team_rounds:
            if team_round.team_id in normalized_scores:
                team_round.normalized_score = normalized_scores[team_round.team_id]
                if team_round.raw_score is not None:
                    team_rounds_with_scores.append(team_round)

        team_rounds_with_scores.sort(key=lambda tr: tr.raw_score)
        for rank, team_round in enumerate(team_rounds_with_scores, 1):
            team_round.rank = rank

        db.session.commit()

        # Mark source round as Completed
        source_round.status = 'Completed'
        db.session.flush()

        # Start order — BeMod-F-Schlepp H.II:
        # Last two planned rounds: standings-based, worst first (reverse of ranking).
        # All earlier rounds: random — user must use Startliste / Zufallige Reihenfolge.
        # estimated_rounds is set on the Event (Wettbewerb card).
        # A round is "one of the last two" when next_round_number >= estimated_rounds - 1.
        estimated = event.estimated_rounds or 4
        use_standings = next_round_number >= estimated - 1

        if use_standings:
            completed_rounds = Round.query.filter(
                Round.event_id == event_id,
                Round.status == 'Completed'
            ).all()
            team_totals = {}
            for r in completed_rounds:
                for tr in TeamRound.query.filter_by(round_id=r.round_id).all():
                    if tr.normalized_score is not None:
                        team_totals[tr.team_id] = team_totals.get(tr.team_id, 0.0) + tr.normalized_score
            # Sort ascending: lowest cumulative score starts first
            sorted_team_ids = [tid for tid, _ in sorted(team_totals.items(), key=lambda x: x[1])]
            # Add any active teams not yet in standings
            all_active_ids = {t.team_id for t in Team.query.filter_by(status='active').all()}
            for tid in all_active_ids:
                if tid not in team_totals:
                    sorted_team_ids.append(tid)
            team_order = []
            for tid in sorted_team_ids:
                team = Team.query.get(tid)
                if team:
                    team_order.append(team.team_nummer)
        else:
            # Random round: neutral placeholder order, user randomizes via Startliste
            team_order = None

        # Create new round
        new_round = Round(
            event_id=event_id,
            round_number=next_round_number,
            status='Active'
        )
        db.session.add(new_round)
        db.session.flush()

        from app.routes.bp_formular import generate_scoresheets_for_round

        if generate_scoresheets_for_round(new_round.round_id, team_order):
            db.session.commit()
            session['formular_event_id'] = event_id
            if use_standings:
                flash(f'Durchgang {next_round_number} erstellt — Startfolge nach Gesamtwertung (schlechtestes Team zuerst) — bitte drucken', 'success')
            else:
                flash(f'Durchgang {next_round_number} erstellt — bitte Startfolge unter Zufallige Reihenfolge generieren und drucken', 'success')
            return redirect(url_for('formular.index', event_id=event_id))
        else:
            db.session.rollback()
            flash('Fehler beim Erstellen der Bewertungsbögen', 'error')

        return redirect(url_for('scoring.score_list', event_id=event_id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error generating next round: {str(e)}")
        flash(f'Fehler beim Erstellen des nächsten Durchgangs: {str(e)}', 'error')
        return redirect(url_for('scoring.score_list'))
    
@scoring_bp.route('/generate_scoresheets', methods=['POST'])
def generate_scoresheets():
    """Generate blank scoresheets for the next round only if current round has scores"""
    try:
        # Use event_id from form; fall back to active event if not provided
        event_id = request.form.get('event_id', type=int)
        if event_id:
            active_event = Event.query.get(event_id)
        else:
            active_event = Event.query.filter_by(status='Active', is_hidden=False).first()
            if not active_event:
                active_event = Event.query.filter_by(is_hidden=False).order_by(Event.event_date.desc()).first()

        if not active_event:
            flash('Keine Veranstaltung gefunden', 'error')
            return redirect(url_for('scoring.score_list'))

        # Check if event is completed/published
        if active_event.status in ('Completed', 'Published'):
            flash('Abgeschlossene Wettbewerbe können nicht geändert werden', 'error')
            return redirect(url_for('scoring.score_list'))
            
        # Find all rounds for this event
        all_rounds = Round.query.filter_by(event_id=active_event.event_id)\
            .order_by(Round.round_number).all()
            
        if not all_rounds:
            # If no rounds exist, create round 1
            next_round_number = 1
            current_active_round = None
        else:
            # Check the highest round number
            highest_round = Round.query.filter_by(event_id=active_event.event_id)\
                .order_by(Round.round_number.desc()).first()
                
            # Find current active round (should only be one)
            current_active_round = Round.query.filter_by(
                event_id=active_event.event_id, 
                status='Active'
            ).first()
            
            # If there's no active round, use the highest round
            if not current_active_round:
                current_active_round = highest_round
                
            next_round_number = current_active_round.round_number + 1
        
        # Check if current round has scores
        can_create_next_round = True
        if current_active_round:
            # Get all team rounds for the active round
            team_rounds = TeamRound.query.filter_by(round_id=current_active_round.round_id).all()
            
            if not team_rounds:
                flash('Aktueller Durchgang hat noch keine Teams. Bitte zuerst Teams zum Durchgang hinzufügen.', 'warning')
                return redirect(url_for('scoring.score_list'))
                
            # Check if at least 50% of team rounds have scores.
            # A team counts as scored if it has ScoreValues — raw_score alone is
            # unreliable because pre-created blank scoresheets start at 0.0.
            scored_count = 0
            for team_round in team_rounds:
                has_values = db.session.query(
                    ScoreValue.query
                    .join(Score)
                    .filter(Score.team_round_id == team_round.team_round_id)
                    .exists()
                ).scalar()
                if has_values:
                    scored_count += 1
            
            if scored_count < len(team_rounds) / 2:
                # Less than 50% of teams have scores
                flash(f'Mindestens 50% der Teams im aktuellen Durchgang {current_active_round.round_number} müssen bewertet sein, bevor ein neuer Durchgang erstellt werden kann. Bisher: {scored_count}/{len(team_rounds)}', 'warning')
                can_create_next_round = False
        
        if not can_create_next_round:
            return redirect(url_for('scoring.score_list'))
            
        # Create next round
        next_round = Round(
            event_id=active_event.event_id,
            round_number=next_round_number,
            status='Active'
        )
        db.session.add(next_round)
        
        # Mark previous active round as Completed
        if current_active_round:
            current_active_round.status = 'Completed'
        
        db.session.flush()  # Get next_round.round_id without committing yet
        
        # Get team order based on previous round results (if available)
        team_order = []
        if current_active_round:
            # Get all teams in the previous round with scores
            team_rounds = TeamRound.query.filter_by(round_id=current_active_round.round_id)\
                .filter(TeamRound.raw_score != None)\
                .order_by(TeamRound.raw_score)\
                .all()
                
            # Teams with lower scores start first
            for team_round in team_rounds:
                team = Team.query.get(team_round.team_id)
                if team and team.status == 'active':
                    team_order.append(team.team_nummer)
                    
            # Also add active teams without scores in the previous round
            scored_team_ids = [tr.team_id for tr in team_rounds]
            unscored_active_teams = Team.query.filter_by(status='active')\
                .filter(~Team.team_id.in_(scored_team_ids))\
                .all()
                
            for team in unscored_active_teams:
                team_order.append(team.team_nummer)
        else:
            # If no previous round, use all active teams
            teams = Team.query.filter_by(status='active').order_by(Team.team_nummer).all()
            team_order = [team.team_nummer for team in teams]
            
        # Generate scoresheets
        from app.routes.bp_formular import generate_scoresheets_for_round
        if generate_scoresheets_for_round(next_round.round_id, team_order):
            db.session.commit()
            session['formular_event_id'] = active_event.event_id
            flash(f'Durchgang {next_round_number} erstellt — bitte Startfolge generieren und drucken', 'success')
            return redirect(url_for('formular.index', event_id=active_event.event_id))
        else:
            db.session.rollback()
            flash(f'Fehler beim Erstellen der Bewertungsbögen für Durchgang {next_round_number}', 'warning')

        return redirect(url_for('scoring.score_list', round_id=next_round.round_id))
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error generating scoresheets: {str(e)}")
        flash(f'Fehler beim Erstellen der Bewertungsbögen: {str(e)}', 'error')
        return redirect(url_for('scoring.score_list'))

# Results, email and PDF routes are in bp_scoring_results.py
# (imported below to register them onto this blueprint)

# Intentional late import — must come after scoring_bp and scoring_service are defined
import app.routes.bp_scoring_results  # noqa: F401, E402

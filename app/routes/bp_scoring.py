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
from datetime import datetime

import logging
import traceback
import sys

round_service = RoundService()

# Admin password in config file
from app.config import Config
ADMIN_PASSWORD = Config.ADMIN_PASSWORD

# Admin decorator (shared)
from app.utils.auth import admin_required

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

logger.info("Score model columns: " + str([c.name for c in Score.__table__.columns]))


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
        
        # For form submissions, redirect to view score page
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
@admin_required
def unlock_score(score_id):
    """Unlock a score (admin only)"""
    try:
        logger.info(f"Unlocking score {score_id}, headers: {request.headers}")
        score = Score.query.get_or_404(score_id)
        score.locked = False
        score.locked_at = None
        score.locked_by = None
        db.session.commit()
        
        logger.info(f"Score {score_id} unlocked successfully")
        flash('Bewertung entsperrt', 'success')
        
        # Check if the request comes from AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"status": "success", "message": "Bewertung entsperrt"})
            
        # For form submissions, redirect to view score page
        return redirect(url_for('scoring.view_score', score_id=score_id))
        
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
        judges = scoring_service.get_judges()
        
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
        
        # Get all events
        events = Event.query.order_by(Event.event_date.desc()).all()
        
        # Get active event if not specified
        if not event_id:
            active_event = Event.query.filter_by(status='Active').first()
            if active_event:
                event_id = active_event.event_id
            elif events:
                event_id = events[0].event_id
                
        event = Event.query.get(event_id) if event_id else None
        
        # Get rounds for this event
        rounds = Round.query.filter_by(event_id=event_id).order_by(Round.round_number).all() if event_id else []
        
        # Check round completion status for the latest round
        can_generate_next_round = False
        round_status_info = None
        any_round_has_scores = False

        if event_id and rounds:
            from app.utils.round_status import round_completion_status
            latest_round = rounds[-1]
            round_status_info = round_completion_status(latest_round.round_id)
            any_round_has_scores = round_status_info['scored_teams'] > 0
            # Can only generate next round when ALL teams in the latest round have scores
            can_generate_next_round = (
                round_status_info['total_teams'] > 0 and
                round_status_info['scored_teams'] == round_status_info['total_teams'] and
                event.status not in ('Completed', 'Published')
            )
        
        # Validate round_id belongs to this event; reset if not
        valid_round_ids = [r.round_id for r in rounds]
        if round_id and round_id not in valid_round_ids:
            round_id = None

        # If round_id is not specified but there are rounds, use the latest one
        if not round_id and rounds:
            round_id = rounds[-1].round_id
            
        # Get all judges
        judges = scoring_service.get_judges()
        
        # Get all teams
        # teams = Team.query.filter_by(status='active').order_by(Team.team_nummer).all()
        if round_id:
            # Get teams ordered by start_order for this round
            teams = Team.query.join(TeamRound, Team.team_id == TeamRound.team_id)\
                .filter(Team.status == 'active')\
                .filter(TeamRound.round_id == round_id)\
                .order_by(TeamRound.start_order)\
                .all()
        else:
            # Fall back to team number order if no round is selected
            teams = Team.query.filter_by(status='active').order_by(Team.team_nummer).all()

        # Get completed scoresheets with eager loading
        query = Score.query.options(
            db.joinedload(Score.values).joinedload(ScoreValue.task_type)
        )
        
        if round_id:
            query = query.join(TeamRound).filter(TeamRound.round_id == round_id)
        
        if judge_id:
            query = query.filter(Score.judge_id == judge_id)
            
        completed_scores = query.all()
        
        # Convert to a dictionary for easier lookup
        MESSWERTUNG_CODES = {'SEGZEIT', 'LANDGM', 'LANS', 'SEILZ'}
        completed_dict = {}
        has_quality_set = set()  # Track which scores have quality data entered
        for score in completed_scores:
            team_round = TeamRound.query.get(score.team_round_id)
            if team_round:
                key = f"{team_round.round_id}_{team_round.team_id}_{score.judge_id}"
                completed_dict[key] = score
                codes = [sv.task_type.code for sv in score.values if sv.task_type]
                has_quality = any(c not in MESSWERTUNG_CODES for c in codes)
                logger.debug(f"Score {score.score_id} judge {score.judge_id}: codes={codes} has_quality={has_quality}")
                if has_quality:
                    has_quality_set.add(key)
        
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
            
        # Define the getRawScore function directly in this scope
        # Messwertung is included only for the "owner" judge (lowest score_id
        # per team_round).  Other judges show Messwertung as blue/informational.
        MESSWERTUNG_CODES = {'SEGZEIT', 'LANDGM', 'LANS', 'SEILZ'}

        # Cache: team_round_id -> owner score_id
        _messwertung_owners = {}

        def _is_messwertung_owner(score):
            tr_id = score.team_round_id
            if tr_id not in _messwertung_owners:
                first = Score.query.filter_by(team_round_id=tr_id)\
                    .order_by(Score.score_id).first()
                _messwertung_owners[tr_id] = first.score_id if first else None
            return _messwertung_owners[tr_id] == score.score_id

        def get_raw_score(score):
            """Calculate raw score matching the scoresheet Gesamtpunktzahl.
            Messwertung is included only for the owner judge."""
            if not score:
                return None

            raw_score = 0
            is_owner = _is_messwertung_owner(score)

            # Check if we have eagerly loaded the values
            if not hasattr(score, 'values') or not score.values:
                score = Score.query.options(
                    db.joinedload(Score.values).joinedload(ScoreValue.task_type)
                ).get(score.score_id)

                if not score or not score.values:
                    return None

            for score_value in score.values:
                if not score_value.task_type:
                    continue

                value = score_value.value
                if value is None:
                    continue

                code = score_value.task_type.code

                # Messwertung only counted for the owner judge
                if code in MESSWERTUNG_CODES:
                    if not is_owner:
                        continue
                    # SEGZEIT uses special formula
                    if code == 'SEGZEIT':
                        points = max(0, 300 - (abs(200 - value) * 3))
                        raw_score += points
                        continue

                k_factor = score_value.task_type.k_factor or 1
                raw_score += value * k_factor

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
                             selected_round=round_id,
                             selected_judge=judge_id,
                             standings=standings,
                             standings_rounds=standings_rounds,
                             getRawScore=get_raw_score,
                             can_generate_next_round=can_generate_next_round,
                             any_round_has_scores=any_round_has_scores,
                             round_status_info=round_status_info)
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
        
        # Get active figures
        active_figures = scoring_service.get_active_figures()
        
        # Create a mapping of original values by task_type code
        value_map = {}
        for value in score.values:
            if value.task_type:
                value_map[value.task_type.code] = value.value
                logger.debug(f"Mapped {value.task_type.code} -> {value.value}")
        
        # Determine if this score is the Messwertung owner (visual only)
        # Owner shows Messwertung values normally; others show them in blue
        # All sheets remain editable — blue is just informational
        first_score = Score.query.filter_by(team_round_id=team_round.team_round_id)\
            .order_by(Score.score_id).first()
        is_messwertung_owner = (first_score and first_score.score_id == score.score_id)

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
                              is_messwertung_owner=is_messwertung_owner,
                              referer_params=referer_params,
                              judges=scoring_service.get_judges(),
                              event=event,
                              active_event=active_event)
    except Exception as e:
        logger.error(f"Error viewing score: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        flash('Fehler beim Laden der Bewertung', 'error')
        return redirect(url_for('scoring.score_list'))

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
        
        # Find the highest round number
        highest_round_number = max(r.round_number for r in rounds)
        last_round = next((r for r in rounds if r.round_number == highest_round_number), None)
        
        if not last_round:
            flash('Letzter Durchgang nicht gefunden', 'error')
            return redirect(url_for('scoring.score_list'))
        
        # Calculate raw and normalized scores for all team rounds in the last round
        team_rounds = TeamRound.query.filter_by(round_id=last_round.round_id).all()
        for team_round in team_rounds:
            raw_score = scoring_service.aggregate_judge_scores(team_round.team_round_id)
            team_round.raw_score = raw_score
        
        # Calculate normalized scores
        db.session.flush()
        normalized_scores = scoring_service.normalize_round_scores(last_round.round_id)
        
        # Update team rounds with normalized scores and ranks
        team_rounds_with_scores = []
        for team_round in team_rounds:
            if team_round.team_id in normalized_scores:
                team_round.normalized_score = normalized_scores[team_round.team_id]
                if team_round.raw_score is not None:
                    team_rounds_with_scores.append(team_round)
        
        # Sort by raw score (lowest first) and assign ranks
        team_rounds_with_scores.sort(key=lambda tr: tr.raw_score)
        for rank, team_round in enumerate(team_rounds_with_scores, 1):
            team_round.rank = rank
        
        db.session.commit()
        
        # Get team rounds sorted by score (lowest score starts first)
        scored_team_rounds = TeamRound.query.filter_by(round_id=last_round.round_id)\
            .filter(TeamRound.raw_score != None)\
            .order_by(TeamRound.raw_score.asc())\
            .all()

        if not scored_team_rounds:
            flash('Keine Bewertungen im letzten Durchgang gefunden', 'error')
            return redirect(url_for('scoring.score_list'))

        # Teams without scores (missed the round) — start last
        scored_team_ids = {tr.team_id for tr in scored_team_rounds}
        unscored_team_rounds = TeamRound.query.filter_by(round_id=last_round.round_id)\
            .filter(TeamRound.team_id.notin_(scored_team_ids))\
            .all()

        # Mark previous round as Completed
        last_round.status = 'Completed'

        # Create new round
        new_round_number = highest_round_number + 1
        new_round = Round(
            event_id=event_id,
            round_number=new_round_number,
            status='Active'
        )
        db.session.add(new_round)
        db.session.flush()

        # Create team order: scored teams first (lowest first), then unscored teams last
        team_order = []
        for team_round in scored_team_rounds:
            team = Team.query.get(team_round.team_id)
            if team:
                team_order.append(team.team_nummer)
        for team_round in unscored_team_rounds:
            team = Team.query.get(team_round.team_id)
            if team:
                team_order.append(team.team_nummer)
        
        # Generate scoresheets for the new round using the formular function
        from app.routes.bp_formular import generate_scoresheets_for_round
        
        if generate_scoresheets_for_round(new_round.round_id, team_order):
            db.session.commit()
            flash(f'Durchgang {new_round_number} erfolgreich erstellt mit Startfolge basierend auf Durchgang {highest_round_number}', 'success')
        else:
            db.session.rollback()
            flash('Fehler beim Erstellen der Bewertungsbögen', 'error')
        
        return redirect(url_for('scoring.score_list', event_id=event_id, round_id=new_round.round_id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error generating next round: {str(e)}")
        flash(f'Fehler beim Erstellen des nächsten Durchgangs: {str(e)}', 'error')
        return redirect(url_for('scoring.score_list'))
    
@scoring_bp.route('/generate_scoresheets', methods=['POST'])
def generate_scoresheets():
    """Generate blank scoresheets for the next round only if current round has scores"""
    try:
        # Get active event
        active_event = Event.query.filter_by(status='Active').first()
        if not active_event:
            active_event = Event.query.order_by(Event.event_date.desc()).first()

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
                
            # Check if at least 50% of team rounds have scores
            scored_count = 0
            for team_round in team_rounds:
                if team_round.raw_score is not None:
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
            flash(f'Bewertungsbögen für Durchgang {next_round_number} erfolgreich erstellt', 'success')
        else:
            db.session.rollback()
            flash(f'Fehler beim Erstellen der Bewertungsbögen für Durchgang {next_round_number}', 'warning')
            
        return redirect(url_for('scoring.score_list', round_id=next_round.round_id))
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error generating scoresheets: {str(e)}")
        flash(f'Fehler beim Erstellen der Bewertungsbögen: {str(e)}', 'error')
        return redirect(url_for('scoring.score_list'))

@scoring_bp.route('/team_results')
def team_results():
    """Display team results - simple version using existing logic"""
    try:
        # Get parameters
        event_id = request.args.get('event_id', type=int)
        round_id = request.args.get('round_id', type=int)
        team_id = request.args.get('team_id', type=int)
        
        # Get events
        events = Event.query.order_by(Event.event_date.desc()).all()
        
        # Default to first event
        if not event_id and events:
            event_id = events[0].event_id
        event = Event.query.get(event_id) if event_id else None
        
        # Get rounds
        rounds = Round.query.filter_by(event_id=event_id).order_by(Round.round_number).all() if event_id else []
        
        # Default to first round
        if not round_id and rounds:
            round_id = rounds[0].round_id
            
        # Get teams with scores
        teams = []
        if round_id:
            team_ids_with_scores = db.session.query(TeamRound.team_id)\
                .join(Score, TeamRound.team_round_id == Score.team_round_id)\
                .filter(TeamRound.round_id == round_id)\
                .distinct().all()
            
            if team_ids_with_scores:
                team_ids = [t[0] for t in team_ids_with_scores]
                teams = Team.query.filter(Team.team_id.in_(team_ids))\
                    .filter(Team.status == 'active')\
                    .order_by(Team.team_nummer).all()
        
        # Get team data if selected
        team_data = None
        if team_id and round_id:
            team = Team.query.get(team_id)
            if team:
                figures = TaskType.query.filter_by(is_active=True).order_by(TaskType.sort_order).all()
                team_round = TeamRound.query.filter_by(team_id=team_id, round_id=round_id).first()
                if team_round:
                    scores = Score.query.options(
                        db.joinedload(Score.values).joinedload(ScoreValue.task_type),
                        db.joinedload(Score.judge)
                    ).filter_by(team_round_id=team_round.team_round_id).all()
                    
                    team_data = {
                        'team': team,
                        'figures': figures,
                        'scores': scores
                    }
        
        return render_template('scoring/team_results.html',
                             events=events,
                             event=event,
                             rounds=rounds,
                             teams=teams,
                             team_data=team_data,
                             selected_event_id=event_id,
                             selected_round_id=round_id,
                             selected_team_id=team_id)
                             
    except Exception as e:
        logger.error(f"Error in team_results: {str(e)}")
        return render_template('scoring/team_results.html')

@scoring_bp.route('/email_team_results', methods=['POST'])
def email_team_results():
    """Email team results to recipients"""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        data = request.get_json()
        team_id = data.get('team_id')
        round_id = data.get('round_id')
        event_id = data.get('event_id')
        
        # Get team data
        team = Team.query.get(team_id)
        if not team:
            return jsonify({'success': False, 'message': 'Team not found'})
        
        # Get figures and scores
        figures = TaskType.query.filter_by(is_active=True).order_by(TaskType.sort_order).all()
        team_round = TeamRound.query.filter_by(team_id=team_id, round_id=round_id).first()
        
        if not team_round:
            return jsonify({'success': False, 'message': 'No scores found'})
            
        scores = Score.query.options(
            db.joinedload(Score.values).joinedload(ScoreValue.task_type),
            db.joinedload(Score.judge)
        ).filter_by(team_round_id=team_round.team_round_id).all()
        
        team_data = {
            'team': team,
            'figures': figures,
            'scores': scores
        }
        
        # Get event for subject line
        event = Event.query.get(event_id)
        round_obj = Round.query.get(round_id)
        
        # Create HTML email content
        html_content = render_template('scoring/team_results_email.html', 
                                     team_data=team_data,
                                     event=event,
                                     round_obj=round_obj)
        
        # Email configuration from config
        from app.config import Config
        smtp_server = Config.MAIL_SERVER
        smtp_port = Config.MAIL_PORT
        email_user = Config.MAIL_USERNAME
        email_password = Config.MAIL_PASSWORD

        
        # Recipients
        recipients = []
        if team.schlepper_pilot and team.schlepper_pilot.email:
            recipients.append(team.schlepper_pilot.email)
        if team.segler_pilot and team.segler_pilot.email:
            recipients.append(team.segler_pilot.email)
        
        if not recipients:
            return jsonify({'success': False, 'message': 'Keine Email-Adressen für dieses Team gefunden'})
        
        # Create email
        msg = MIMEMultipart()
        msg['From'] = email_user
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = f"Team {team.team_nummer} Ergebnisse - {event.name if event else 'NRW Cup'}"
        
        msg.attach(MIMEText(html_content, 'html'))
        
        # Send email
        import ssl 

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(email_user, email_password)
            server.send_message(msg)
        
        return jsonify({'success': True, 'message': f'Email gesendet an: {", ".join(recipients)}'})
        
    except Exception as e:
        logger.error(f"Email error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@scoring_bp.route('/admin/recalculate_scores', methods=['GET', 'POST'])
@admin_required
def recalculate_scores():
    """Admin route to recalculate all scores with fixed aggregation logic"""
    
    if request.method == 'POST':
        try:
            # Get all team rounds that have scores
            team_rounds = TeamRound.query.all()
            
            updated_count = 0
            significant_changes = []
            
            for team_round in team_rounds:
                try:
                    # Store old score for comparison
                    old_raw_score = team_round.raw_score
                    
                    # Recalculate raw score using fixed aggregation
                    new_raw_score = scoring_service.aggregate_judge_scores(team_round.team_round_id)
                    
                    if new_raw_score is not None:
                        team_round.raw_score = new_raw_score
                        updated_count += 1
                        
                        # Track significant changes
                        if old_raw_score and abs(new_raw_score - old_raw_score) > 50:
                            team = Team.query.get(team_round.team_id)
                            round_obj = Round.query.get(team_round.round_id)
                            significant_changes.append({
                                'team_number': team.team_nummer if team else 'Unknown',
                                'round_number': round_obj.round_number if round_obj else 'Unknown',
                                'old_score': old_raw_score,
                                'new_score': new_raw_score,
                                'difference': new_raw_score - old_raw_score
                            })
                            
                except Exception as e:
                    logger.error(f"Error recalculating team round {team_round.team_round_id}: {e}")
            
            # Recalculate normalized scores for all rounds
            rounds_processed = set()
            for team_round in team_rounds:
                if team_round.round_id not in rounds_processed:
                    try:
                        # Recalculate normalized scores for this round
                        normalized_scores = scoring_service.normalize_round_scores(team_round.round_id)
                        
                        # Update team rounds with new normalized scores
                        round_team_rounds = TeamRound.query.filter_by(round_id=team_round.round_id).all()
                        for tr in round_team_rounds:
                            if tr.team_id in normalized_scores:
                                tr.normalized_score = normalized_scores[tr.team_id]
                        
                        rounds_processed.add(team_round.round_id)
                        
                    except Exception as e:
                        logger.error(f"Error normalizing round {team_round.round_id}: {e}")
            
            # Commit all changes
            db.session.commit()
            
            flash(f'Recalculated {updated_count} team scores across {len(rounds_processed)} rounds', 'success')
            
            return render_template('scoring/recalculate_results.html',
                                 updated_count=updated_count,
                                 rounds_processed=len(rounds_processed),
                                 significant_changes=significant_changes)
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in recalculation: {str(e)}")
            flash(f'Error during recalculation: {str(e)}', 'error')
    
    return render_template('scoring/recalculate_confirm.html')
    

@scoring_bp.route('/team_scoresheet_pdf/<int:team_id>/<int:round_id>')
def team_scoresheet_pdf(team_id, round_id):
    """Generate detailed PDF scoresheet for a team in a specific round"""
    try:
        # Get basic objects
        team = Team.query.get_or_404(team_id)
        round_obj = Round.query.get_or_404(round_id)
        event = Event.query.get_or_404(round_obj.event_id)

        # Get team round
        team_round = TeamRound.query.filter_by(team_id=team_id, round_id=round_id).first()
        
        if not team_round:
            flash('Keine Wertungen für dieses Team in diesem Durchgang gefunden', 'error')
            return redirect(url_for('scoring.team_results'))
            
        # Get all scores for this team round
        scores = Score.query.options(
            db.joinedload(Score.values).joinedload(ScoreValue.task_type),
            db.joinedload(Score.judge)
        ).filter_by(team_round_id=team_round.team_round_id).all()
        
        # CHANGE: Get ALL active figures instead of only scored ones
        figures = TaskType.query.filter_by(is_active=True).order_by(TaskType.sort_order).all()
        
        # Define Messwertung codes
        messwertung_codes = {'LANDGM', 'LANS', 'SEILZ', 'SEGZEIT'}
        
        # Separate figures
        qualitaet_figures = [f for f in figures if f.code not in messwertung_codes]
        messwertung_figures = [f for f in figures if f.code in messwertung_codes]
        
        # Build judge scores matrix for Qualitätswertung - SHOW ALL FIGURES
        qualitaet_data = []
        for figure in qualitaet_figures:
            judge_scores = []
            for score in scores:
                for score_value in score.values:
                    if score_value.task_type and score_value.task_type.code == figure.code:
                        if score_value.value is not None:
                            judge_scores.append(score_value.value)
                        break
            
            # Calculate even if no scores exist
            if judge_scores:
                total_sum = sum(judge_scores)
                average = total_sum / len(judge_scores)
                k_factor = figure.k_factor or 1
                points = average * k_factor
            else:
                total_sum = 0
                average = 0
                k_factor = figure.k_factor or 1
                points = 0
                
            qualitaet_data.append({
                'figure': figure,
                'judge_scores': judge_scores,
                'sum': total_sum,
                'average': average,
                'k_factor': k_factor,
                'points': points
            })
        
        # Build Messwertung data - SHOW ALL FIGURES
        messwertung_data = []
        messwertung_total = 0
        
        for figure in messwertung_figures:
            value = None
            points = 0

            for score in scores:
                for score_value in score.values:
                    if score_value.task_type and score_value.task_type.code == figure.code:
                        if score_value.value is not None:
                            value = score_value.value

                            # Calculate points based on figure type
                            if figure.code == 'SEGZEIT':
                                # Special Seglerzeit calculation
                                target_time = 200
                                max_points = 300
                                penalty_factor = 3
                                time_diff = abs(target_time - value)
                                points = max(0, max_points - (time_diff * penalty_factor))
                            else:
                                # Standard Messwertung (direct points)
                                points = value
                            break
                if value is not None:
                    break
            
            # Add ALL figures, even without scores
            messwertung_data.append({
                'figure': figure,
                'value': value,
                'points': points
            })
            
            if points:
                messwertung_total += points
        
        # Calculate totals
        qualitaet_total = sum(item['points'] for item in qualitaet_data)
        grand_total = qualitaet_total + messwertung_total
        
        # Render HTML template - KEEP YOUR EXACT TEMPLATE
        html = render_template('scoring/team_scoresheet_pdf.html',
                              team=team,
                              round_obj=round_obj,
                              event=event,
                              qualitaet_data=qualitaet_data,
                              messwertung_data=messwertung_data,
                              qualitaet_total=qualitaet_total,
                              messwertung_total=messwertung_total,
                              grand_total=grand_total,
                              judge_count=len(scores))
        
        # Convert to PDF using reportlab or return HTML for now
        from flask import make_response
        response = make_response(html)
        response.headers['Content-Type'] = 'text/html'
        return response
        
    except Exception as e:
        logger.error(f"Error generating scoresheet PDF: {str(e)}")
        flash(f'Fehler beim Erstellen des Bewertungsbogens: {str(e)}', 'error')
        return redirect(url_for('scoring.team_results'))



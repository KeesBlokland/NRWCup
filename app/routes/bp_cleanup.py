"""
File: app/routes/bp_cleanup.py
Version: 1.1.0
Created: 2025-04-01
Updated: 2026-02-10
Description: Blueprint for data cleanup operations - all routes require admin access
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.models import db, Teilnehmer, Team, Flugzeuge, Event, Round, TeamRound, Score, ScoreValue
from app.utils.force_delete import force_delete_teilnehmer, force_delete_flugzeug, force_delete_team
from app.utils.clear_data import clear_event_data
from app.utils.auth import admin_required
from app.utils.audit import audit_log
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

cleanup_bp = Blueprint('cleanup', __name__)

@cleanup_bp.route('/')
@admin_required
def index():
    """Display cleanup options"""
    events = Event.query.order_by(Event.event_date.desc()).all()
    teilnehmers = Teilnehmer.query.order_by(Teilnehmer.name).all()
    flugzeuge = Flugzeuge.query.order_by(Flugzeuge.name).all()
    teams = Team.query.order_by(Team.team_nummer).all()
    return render_template('cleanup/cleanup_main.html',
                         events=events,
                         teilnehmers=teilnehmers,
                         flugzeuge=flugzeuge,
                         teams=teams)

@cleanup_bp.route('/event/<int:event_id>', methods=['POST'])
@admin_required
def cleanup_event(event_id):
    """Clean up an event completely by removing all associated data"""
    try:
        event = Event.query.get_or_404(event_id)
        event_name = event.name

        result = clear_event_data(event_id, clear_scores_only=False)

        logger.info(f"Cleaned up event {event_id}: {result['rounds_deleted']} rounds, "
                   f"{result['team_rounds_deleted']} team rounds, {result['scores_deleted']} scores")

        flash(f'Event "{event_name}" komplett bereinigt: {result["rounds_deleted"]} Durchgänge, '
              f'{result["team_rounds_deleted"]} Team-Rundenzuordnungen und '
              f'{result["scores_deleted"]} Bewertungen gelöscht', 'success')

        return redirect(url_for('contest.index'))

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in cleanup_event: {str(e)}")
        flash(f'Fehler beim Bereinigen des Events: {str(e)}', 'error')
        return redirect(url_for('cleanup.index'))

@cleanup_bp.route('/teilnehmer/<int:id>', methods=['POST'])
@admin_required
def delete_teilnehmer(id):
    """Force delete a participant and cascade the deletion"""
    try:
        teilnehmer = Teilnehmer.query.get(id)
        name = teilnehmer.name if teilnehmer else f"ID {id}"

        result = force_delete_teilnehmer(id)

        if 'error' in result:
            flash(f'Fehler beim Löschen von {name}: {result["error"]}', 'error')
        else:
            audit_log('teilnehmer', id, 'deleted', name, None)
            db.session.commit()
            message = f'{name} erfolgreich gelöscht'
            if result['teams_deleted']:
                message += f', {result["teams_deleted"]} Teams'
            if result['aircraft_deleted']:
                message += f', {result["aircraft_deleted"]} Flugzeuge'
            if result['scores_deleted']:
                message += f', {result["scores_deleted"]} Bewertungen'
            flash(message, 'success')

    except Exception as e:
        logger.error(f"Error force deleting teilnehmer {id}: {str(e)}")
        flash(f'Fehler beim Löschen des Teilnehmers: {str(e)}', 'error')

    return redirect(url_for('cleanup.index'))

@cleanup_bp.route('/flugzeug/<int:id>', methods=['POST'])
@admin_required
def delete_flugzeug(id):
    """Force delete an aircraft and update related records"""
    try:
        flugzeug = Flugzeuge.query.get(id)
        name = flugzeug.name if flugzeug else f"ID {id}"

        result = force_delete_flugzeug(id)

        if 'error' in result:
            flash(f'Fehler beim Löschen von {name}: {result["error"]}', 'error')
        else:
            audit_log('flugzeuge', id, 'deleted', name, None)
            db.session.commit()
            message = f'{name} erfolgreich gelöscht'
            if result['teams_updated']:
                message += f', {result["teams_updated"]} Teams aktualisiert'
            flash(message, 'success')

    except Exception as e:
        logger.error(f"Error force deleting flugzeug {id}: {str(e)}")
        flash(f'Fehler beim Löschen des Flugzeugs: {str(e)}', 'error')

    return redirect(url_for('cleanup.index'))

@cleanup_bp.route('/team/<int:id>', methods=['POST'])
@admin_required
def delete_team(id):
    """Force delete a team and cascade the deletion"""
    try:
        team = Team.query.get(id)
        name = f"Team {team.team_nummer}" if team else f"ID {id}"

        result = force_delete_team(id)

        if 'error' in result:
            flash(f'Fehler beim Löschen von {name}: {result["error"]}', 'error')
        else:
            audit_log('teams', id, 'deleted', name, None)
            db.session.commit()
            message = f'{name} erfolgreich gelöscht'
            if result['scores_deleted']:
                message += f', {result["scores_deleted"]} Bewertungen'
            if result['team_rounds_deleted']:
                message += f', {result["team_rounds_deleted"]} Rundenzuordnungen'
            flash(message, 'success')

    except Exception as e:
        logger.error(f"Error force deleting team {id}: {str(e)}")
        flash(f'Fehler beim Löschen des Teams: {str(e)}', 'error')

    return redirect(url_for('cleanup.index'))

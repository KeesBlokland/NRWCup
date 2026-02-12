"""
File: app/routes/bp_contest.py
Version: 2.2.0
Created: 2025-03-02
Updated: 2025-03-27
Description: Refactored blueprint for contest/event management with improved round handling
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from app.models import db, Event, Location, Round, TeamRound, Score, ScoreValue
from app.services.services_contest import ContestService
from app.services.services_rounds import RoundService  # Import the new service
from app.utils.utils_base_controller import BaseController
from sqlalchemy.exc import SQLAlchemyError
from app.utils.clear_data import clear_all_scores, clear_event_data
from app.utils.audit import audit_log
import logging
import os
from datetime import datetime

# Configure logger
logger = logging.getLogger(__name__)

# Create blueprint
contest_bp = Blueprint('contest', __name__)

# Initialize services
contest_service = ContestService()
round_service = RoundService()  # Initialize the round service
contest_controller = BaseController(
    model_class=Event,
    template_prefix='contest',
    route_prefix='contest',
    display_name='Wettbewerb'
)

def process_event_data(form):
    """Process form data for Event model"""
    event_data = {
        'name': form.get('name', '').strip(),
        'verein': form.get('verein', '').strip(),
        'status': form.get('status', 'Pending'),
        'event_date': contest_service.parse_event_date(form.get('event_date')),
    }
    
    # Handle estimated_rounds
    try:
        estimated_rounds = form.get('estimated_rounds', type=int)
        if estimated_rounds:
            event_data['estimated_rounds'] = estimated_rounds
    except (ValueError, TypeError):
        pass
    
    return event_data

def process_location_data(form):
    """Process form data for Location model"""
    location_data = {
        'city': form.get('city', '').strip(),
        'street': form.get('street', '').strip(),
        'postal_code': form.get('postal_code', '').strip(),
        'notes': form.get('notes', '').strip(),
    }
    
    # Handle coordinates
    try:
        lat = form.get('lat', '')
        lon = form.get('lon', '')
        if lat:
            location_data['lat'] = float(lat)
        if lon:
            location_data['lon'] = float(lon)
    except (ValueError, TypeError):
        pass
    
    return location_data

@contest_bp.route('/')
def index():
    """Display contest overview"""
    try:
        events = contest_service.get_all_events(order_by_date=True)
        return render_template('contest/contest_main.html', events=events)
    except SQLAlchemyError as e:
        logger.error(f"Database error in contest.index: {str(e)}")
        flash('Fehler beim Laden der Wettbewerbe', 'error')
        return render_template('contest/contest_main.html', events=[])

@contest_bp.route('/get/<int:event_id>')
def get_event(event_id):
    """Get event details for editing"""
    try:
        event = contest_service.get_event_with_location(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
            
        location = event.location
        data = {
            'event_id': event.event_id,
            'name': event.name,
            'verein': event.verein,
            'status': event.status,
            'city': location.city if location else '',
            'street': location.street if location else '',
            'postal_code': location.postal_code if location else '',
            'event_date': event.event_date.strftime('%Y-%m-%d') if event.event_date else '',
            'lat': location.lat if location else '',
            'lon': location.lon if location else '',
            'notes': location.notes if location else '',
            'estimated_rounds': event.estimated_rounds
        }
        return jsonify(data)
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_event: {str(e)}")
        return jsonify({'error': 'Fehler beim Laden des Wettbewerbs'}), 500

@contest_bp.route('/', methods=['POST'])
def save_event():
    """Save or update event details"""
    try:
        event_id = request.form.get('event_id')
        
        # Process form data
        event_data = process_event_data(request.form)
        location_data = process_location_data(request.form)
        
        if event_id:  # Update existing
            # Convert to int
            event_id = int(event_id)
            
            # Update the event and location
            contest_service.update_event_with_location(
                event_id,
                event_data,
                location_data
            )
            
            # Update rounds if estimated_rounds changed
            if 'estimated_rounds' in event_data:
                # Update rounds for this event
                round_service.update_event_rounds(event_id, event_data['estimated_rounds'])
                
        else:  # Create new
            # Create the event and location
            new_event = contest_service.create_event_with_location(
                event_data,
                location_data
            )
            
            # Create initial rounds if specified
            if new_event and 'estimated_rounds' in event_data:
                round_service.update_event_rounds(new_event.event_id, event_data['estimated_rounds'])
        
        flash('Wettbewerb erfolgreich gespeichert', 'success')
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in save_event: {str(e)}")
        flash('Fehler beim Speichern des Wettbewerbs', 'error')
        
    return redirect(url_for('contest.index'))

@contest_bp.route('/delete/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    """Delete an event and its location"""
    try:
        # Check if event can be deleted
        event = contest_service.get_by_id(event_id)
        if not event:
            flash('Wettbewerb nicht gefunden', 'error')
            return redirect(url_for('contest.index'))
            
        # Check for related rounds
        if event.rounds:
            flash('Wettbewerb kann nicht gelöscht werden - es existieren zugehörige Durchgänge', 'error')
            return redirect(url_for('contest.index'))
            
        # Delete using service
        audit_log('events', event_id, 'deleted', event.name, None)
        success = contest_service.delete_event_with_location(event_id)
        if success:
            db.session.commit()
            flash('Wettbewerb erfolgreich gelöscht', 'success')
        else:
            flash('Fehler beim Löschen des Wettbewerbs', 'error')
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in delete_event: {str(e)}")
        flash('Fehler beim Löschen des Wettbewerbs', 'error')
        
    return redirect(url_for('contest.index'))

@contest_bp.route('/clear_scores', methods=['POST'])
def clear_scores():
    """Clear scores based on selection (by event status or specific event)"""
    try:
        selection = request.form.get('event_id')
        clear_rounds_too = request.form.get('clear_rounds_too') == 'true'
        
        if selection == 'all':
            # Clear all scores using the utility function
            audit_log('scores', None, 'clear_all', None, None)
            result = clear_all_scores()
            
            if clear_rounds_too:
                # If clearing rounds too, we need to delete the rounds manually
                # since clear_all_scores only clears scoring data
                rounds_deleted = Round.query.delete()
                
                flash(f'Alle Bewertungen und Durchgänge erfolgreich gelöscht ({result["scores_deleted"]} Bewertungen, {rounds_deleted} Durchgänge)', 'success')
            else:
                flash(f'Alle Bewertungen erfolgreich gelöscht ({result["scores_deleted"]} Bewertungen, {result["team_rounds_deleted"]} Team-Rundenzuordnungen entfernt)', 'success')
            
        elif selection == 'pending' or selection == 'active':
            # Clear scores for events with specific status
            status = 'Pending' if selection == 'pending' else 'Active'
            affected_events = Event.query.filter_by(status=status).all()
            events_affected = len(affected_events)
            
            if events_affected == 0:
                flash(f'Keine Wettbewerbe mit Status "{status}" gefunden', 'warning')
                return redirect(url_for('contest.index'))
            
            total_scores_deleted = 0
            total_rounds_deleted = 0
            total_team_rounds_deleted = 0
            
            for event in affected_events:
                # Use the utility function
                result = clear_event_data(event.event_id, clear_scores_only=not clear_rounds_too)
                total_scores_deleted += result['scores_deleted']
                total_rounds_deleted += result['rounds_deleted']
                total_team_rounds_deleted += result['team_rounds_deleted']
            
            status_display = 'Geplant' if selection == 'pending' else 'Aktiv'
            
            if clear_rounds_too:
                flash(f'Alle Bewertungen und Durchgänge für Wettbewerbe mit Status "{status_display}" erfolgreich gelöscht ({total_scores_deleted} Bewertungen, {total_rounds_deleted} Durchgänge)', 'success')
            else:
                flash(f'Alle Bewertungen für Wettbewerbe mit Status "{status_display}" erfolgreich gelöscht ({total_scores_deleted} Bewertungen, {total_team_rounds_deleted} Team-Rundenzuordnungen entfernt)', 'success')
            
        elif selection and selection.isdigit():
            # Clear scores for a specific event
            event_id = int(selection)
            event = Event.query.get(event_id)
            
            if not event:
                flash('Wettbewerb nicht gefunden', 'error')
                return redirect(url_for('contest.index'))
            
            # Use the utility function
            result = clear_event_data(event_id, clear_scores_only=not clear_rounds_too)
            
            if clear_rounds_too:
                flash(f'Alle Bewertungen und Durchgänge für Wettbewerb "{event.name}" erfolgreich gelöscht ({result["scores_deleted"]} Bewertungen, {result["rounds_deleted"]} Durchgänge)', 'success')
            else:
                flash(f'Alle Bewertungen für Wettbewerb "{event.name}" erfolgreich gelöscht ({result["scores_deleted"]} Bewertungen, {result["team_rounds_deleted"]} Team-Rundenzuordnungen entfernt)', 'success')
        
        else:
            flash('Ungültige Auswahl', 'error')
            
        logger.info(f"Scores cleared via contest blueprint")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Database error in clear_scores: {str(e)}")
        flash(f'Fehler beim Löschen der Bewertungen: {str(e)}', 'error')
        
    return redirect(url_for('contest.index'))

@contest_bp.route('/publish/<int:event_id>', methods=['POST'])
def publish_event(event_id):
    """Publish event results to public view"""
    try:
        # Update event status
        event = contest_service.change_event_status(event_id, 'Published')
        if not event:
            flash('Wettbewerb nicht gefunden', 'error')
            return redirect(url_for('contest.index'))
        
        # Additional publication logic would go here
        # For example, generating static files or notifying participants
        
        flash('Event published successfully', 'success')
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error publishing event: {str(e)}")
        flash(f'Error publishing event: {str(e)}', 'error')
        
    return redirect(url_for('contest.index'))

@contest_bp.route('/unpublish/<int:event_id>', methods=['POST'])
def unpublish_event(event_id):
    """Unpublish event results"""
    try:
        # Update event status
        event = contest_service.change_event_status(event_id, 'Completed')
        if not event:
            flash('Wettbewerb nicht gefunden', 'error')
            return redirect(url_for('contest.index'))
        
        # Additional unpublication logic would go here
        # For example, removing static files
        
        flash('Event unpublished successfully', 'success')
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error unpublishing event: {str(e)}")
        flash(f'Error unpublishing event: {str(e)}', 'error')
        
    return redirect(url_for('contest.index'))
@contest_bp.route('/cleanup/<int:event_id>', methods=['POST'])
def cleanup_event(event_id):
    """Remove all rounds for an event to make it deletable"""
    try:
        # Get the event
        event = contest_service.get_by_id(event_id)
        if not event:
            flash('Wettbewerb nicht gefunden', 'error')
            return redirect(url_for('contest.index'))
            
        # Delete all rounds for this event
        rounds_deleted = 0
        for round_obj in event.rounds:
            # Delete team rounds and scores first
            for team_round in round_obj.team_rounds:
                # Delete scores for this team round
                Score.query.filter_by(team_round_id=team_round.team_round_id).delete()
                # Delete the team round
                db.session.delete(team_round)
            
            # Delete the round
            db.session.delete(round_obj)
            rounds_deleted += 1
        
        db.session.commit()
        
        flash(f'Alle {rounds_deleted} Durchgänge für Wettbewerb "{event.name}" wurden gelöscht. Der Wettbewerb kann jetzt gelöscht werden.', 'success')
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in cleanup_event: {str(e)}")
        flash(f'Fehler beim Bereinigen des Wettbewerbs: {str(e)}', 'error')
        
    return redirect(url_for('contest.index'))

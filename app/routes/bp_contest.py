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
from app.utils.clear_data import clear_event_data
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

            # Protect completed/published events from editing
            existing_event = contest_service.get_by_id(event_id)
            if existing_event and existing_event.status in ('Completed', 'Published'):
                flash('Abgeschlossene Wettbewerbe können nicht bearbeitet werden', 'error')
                return redirect(url_for('contest.index'))
            
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
            
        # Protect completed/published events from deletion
        if event.status in ('Completed', 'Published'):
            flash('Abgeschlossene Wettbewerbe können nicht gelöscht werden', 'error')
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
    """Clear all data (scores, team_rounds, rounds) for a specific Pending event"""
    try:
        selection = request.form.get('event_id')

        if not selection or not selection.isdigit():
            flash('Ungültige Auswahl', 'error')
            return redirect(url_for('contest.index'))

        event_id = int(selection)
        event = Event.query.get(event_id)

        if not event:
            flash('Wettbewerb nicht gefunden', 'error')
            return redirect(url_for('contest.index'))

        # Only Pending events can be cleared
        if event.status != 'Pending':
            flash(f'Nur geplante Wettbewerbe können gelöscht werden. "{event.name}" hat Status: {event.status}', 'error')
            return redirect(url_for('contest.index'))

        # Clear everything: scores, team_rounds, rounds
        result = clear_event_data(event_id, clear_scores_only=False)
        audit_log('scores', event_id, 'clear_all', None, None)

        flash(f'Alle Daten für "{event.name}" gelöscht ({result["scores_deleted"]} Bewertungen, {result["rounds_deleted"]} Durchgänge)', 'success')
            
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

        # Protect completed/published events
        if event.status in ('Completed', 'Published'):
            flash('Abgeschlossene Wettbewerbe können nicht bereinigt werden', 'error')
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

@contest_bp.route('/toggle_lock/<int:event_id>', methods=['POST'])
def toggle_lock(event_id):
    """Toggle event between Completed and Active status"""
    try:
        event = contest_service.get_by_id(event_id)
        if not event:
            flash('Wettbewerb nicht gefunden', 'error')
            return redirect(url_for('contest.index'))

        if event.status in ('Completed', 'Published'):
            # Unlock: set back to Active
            contest_service.change_event_status(event_id, 'Active')
            flash(f'Wettbewerb "{event.name}" entsperrt (Aktiv)', 'success')
        else:
            # Lock: set to Completed
            contest_service.change_event_status(event_id, 'Completed')
            flash(f'Wettbewerb "{event.name}" abgeschlossen (Gesperrt)', 'success')

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling event lock: {str(e)}")
        flash(f'Fehler: {str(e)}', 'error')

    return redirect(url_for('contest.index'))

"""
File: app/routes/bp_start_order.py
Version: 1.0.0
Created: 2025-04-02
Description: Blueprint for managing round-specific start orders
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, send_file, session
from app.models import db, Event, Round, Team, TeamRound, Score
from app.services.services_start_order import StartOrderService
from app.services.pdf_service import PdfService
import logging

# Configure logger
logger = logging.getLogger(__name__)

# Create blueprint
start_order_bp = Blueprint('start_order', __name__)

# Initialize services
start_order_service = StartOrderService()
pdf_service = PdfService()

@start_order_bp.route('/')
def index():
    """Display start order management interface"""
    try:
        # Get event ID from query parameters, session, or fall back to active event
        event_id = request.args.get('event_id', type=int)

        if not event_id:
            event_id = session.get('start_order_event_id')
        if not event_id:
            active_event = Event.query.filter_by(status='Active').first()
            if active_event:
                event_id = active_event.event_id
            else:
                # Get most recent visible event
                event = Event.query.filter_by(is_hidden=False).order_by(Event.event_date.desc()).first()
                if event:
                    event_id = event.event_id

        if event_id:
            session['start_order_event_id'] = event_id

        if not event_id:
            flash('No event selected', 'warning')
            return render_template('start_order/start_order_main.html',
                                  events=Event.query.filter_by(is_hidden=False).order_by(Event.event_date.desc()).all())

        # Get event
        event = Event.query.get_or_404(event_id)

        # Get all visible events for the selector
        events = Event.query.filter_by(is_hidden=False).order_by(Event.event_date.desc()).all()
        
        # Get rounds for this event
        rounds = start_order_service.get_rounds_for_event(event_id)
        
        # Get start orders for each round
        round_start_orders = {}
        for round_obj in rounds:
            round_start_orders[round_obj.round_id] = start_order_service.get_team_start_order_for_round(round_obj.round_id)
        
        return render_template('start_order/start_order_main.html',
                              event=event,
                              events=events,
                              rounds=rounds,
                              round_start_orders=round_start_orders)
        
    except Exception as e:
        logger.error(f"Error in start_order index: {str(e)}")
        flash(f'Error loading start orders: {str(e)}', 'error')
        return render_template('start_order/start_order_main.html',
                              events=Event.query.filter_by(is_hidden=False).order_by(Event.event_date.desc()).all())

@start_order_bp.route('/generate', methods=['POST'])
def generate():
    """Generate start order for a target round based on previous round results"""
    try:
        # Get parameters
        event_id = request.form.get('event_id', type=int)
        target_round_id = request.form.get('target_round_id', type=int)
        
        if not event_id or not target_round_id:
            flash('Event and target round are required', 'error')
            return redirect(url_for('start_order.index', event_id=event_id))

        # Check if event is completed/published
        event = Event.query.get(event_id)
        if event and event.status in ('Completed', 'Published'):
            flash('Abgeschlossene Wettbewerbe können nicht geändert werden', 'error')
            return redirect(url_for('start_order.index', event_id=event_id))

        # Get target round
        target_round = Round.query.get(target_round_id)
        if not target_round:
            flash('Target round not found', 'error')
            return redirect(url_for('start_order.index', event_id=event_id))
            
        # Generate start order based on cumulative overall standings
        result = start_order_service.generate_start_order_from_scores(event_id, target_round.round_id)
        
        if result['success']:
            flash(result['message'], 'success')
        else:
            flash(result['message'], 'error')
            
        return redirect(url_for('start_order.index', event_id=event_id))
        
    except Exception as e:
        logger.error(f"Error generating start order: {str(e)}")
        flash(f'Error generating start order: {str(e)}', 'error')
        return redirect(url_for('start_order.index'))

@start_order_bp.route('/update/<int:round_id>', methods=['POST'])
def update(round_id):
    """Manually update start order for a round"""
    try:
        # Get data from request
        team_orders = request.json.get('team_orders', [])
        
        if not team_orders:
            return jsonify({'success': False, 'message': 'No team orders provided'})
        
        # Get the round
        round_obj = Round.query.get(round_id)
        if not round_obj:
            return jsonify({'success': False, 'message': 'Round not found'})

        # Check if event is completed/published
        event = Event.query.get(round_obj.event_id)
        if event and event.status in ('Completed', 'Published'):
            return jsonify({'success': False, 'message': 'Abgeschlossene Wettbewerbe können nicht geändert werden'})

        # Update each team round's start order
        for order_data in team_orders:
            team_id = order_data.get('team_id')
            start_order = order_data.get('start_order')
            
            if not team_id or start_order is None:
                continue
                
            # Find or create team round
            team_round = TeamRound.query.filter_by(
                round_id=round_id,
                team_id=team_id
            ).first()
            
            if team_round:
                # Update existing
                team_round.start_order = start_order
            else:
                # Create new
                team_round = TeamRound(
                    round_id=round_id,
                    team_id=team_id,
                    start_order=start_order,
                    status='Pending'
                )
                db.session.add(team_round)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Start order for round {round_obj.round_number} updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating start order: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@start_order_bp.route('/randomize/<int:round_id>', methods=['POST'])
def randomize(round_id):
    """Randomize the start order for a round"""
    try:
        # Get the round
        round_obj = Round.query.get(round_id)
        if not round_obj:
            flash('Round not found', 'error')
            return redirect(url_for('start_order.index'))

        # Check if event is completed/published
        event = Event.query.get(round_obj.event_id)
        if event and event.status in ('Completed', 'Published'):
            flash('Abgeschlossene Wettbewerbe können nicht geändert werden', 'error')
            return redirect(url_for('start_order.index', event_id=round_obj.event_id))

        # Get all active teams
        teams = Team.query.filter_by(status='active').all()
        if not teams:
            flash('No active teams found', 'error')
            return redirect(url_for('start_order.index'))
        
        # Shuffle teams
        import random
        shuffled_teams = list(teams)
        random.shuffle(shuffled_teams)
        
        # Update team rounds
        for i, team in enumerate(shuffled_teams, 1):
            # Find or create team round
            team_round = TeamRound.query.filter_by(
                round_id=round_id,
                team_id=team.team_id
            ).first()
            
            if team_round:
                # Update existing
                team_round.start_order = i
            else:
                # Create new
                team_round = TeamRound(
                    round_id=round_id,
                    team_id=team.team_id,
                    start_order=i,
                    status='Pending'
                )
                db.session.add(team_round)
        
        db.session.commit()
        
        flash(f'Start order for round {round_obj.round_number} randomized successfully', 'success')
        return redirect(url_for('start_order.index', event_id=round_obj.event_id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error randomizing start order: {str(e)}")
        flash(f'Error randomizing start order: {str(e)}', 'error')
        return redirect(url_for('start_order.index'))

@start_order_bp.route('/print/<int:round_id>')
def print_start_order(round_id):
    """Print start order for a round"""
    try:
        round_obj = Round.query.get(round_id)
        if round_obj and round_obj.round_number > 1:
            prev_round = Round.query.filter_by(
                event_id=round_obj.event_id,
                round_number=round_obj.round_number - 1
            ).first()
            if prev_round and prev_round.status != 'Completed':
                flash(f'Startfolge Durchgang {round_obj.round_number} kann erst gedruckt werden, '
                      f'wenn Durchgang {prev_round.round_number} abgeschlossen ist.', 'warning')
                return redirect(url_for('start_order.index', event_id=round_obj.event_id))

        pdf_service = PdfService()
        buffer = pdf_service.generate_start_order_pdf(round_id)

        if not buffer:
            flash('Error generating start order PDF', 'error')
            return redirect(url_for('start_order.index'))
            
        round_obj = Round.query.get(round_id)
        event = Event.query.get(round_obj.event_id) if round_obj else None
        
        filename = f"start_order_round_{round_obj.round_number}"
        if event:
            filename = f"{event.name}_round_{round_obj.round_number}_start_order".replace(' ', '_')
                
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"{filename}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Error printing start order: {str(e)}")
        flash(f'Error printing start order: {str(e)}', 'error')
        return redirect(url_for('start_order.index'))
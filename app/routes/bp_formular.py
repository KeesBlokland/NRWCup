"""File: app/routes/bp_formular.py
Version: 3.1.0
Created: 2025-01-22
Updated: 2025-05-04
Description: Blueprint with persistent start lists and automatic scoresheet generation
"""

from flask import Blueprint, render_template, send_file, session, request, jsonify, flash, redirect, url_for, make_response
from app.models import db, Team, Event, SystemConfig, Round, TeamRound, Score, ScoreValue, Teilnehmer, TaskType
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import io
import json
import random
import logging
import pandas as pd

from datetime import datetime


logger = logging.getLogger(__name__)
formular_bp = Blueprint('formular', __name__)

def generate_scoresheets_for_round(round_id, team_order=None):
    """
    Generate scoresheets for a round with specific team order.
    
    Args:
        round_id: Round ID to generate scoresheets for
        team_order: List of team numbers in desired order (optional)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get the round
        round_obj = Round.query.get(round_id)
        if not round_obj:
            logger.error(f"Round {round_id} not found")
            return False
        
        # Get event
        event = Event.query.get(round_obj.event_id)
        if not event:
            logger.error(f"Event for round {round_id} not found")
            return False
        
        # Get teams based on provided order or default order
        teams = []
        
        if team_order:
            # Use the provided team order
            for team_number in team_order:
                team = Team.query.filter_by(team_nummer=team_number, status='active').first()
                if team:
                    teams.append(team)
        else:
            # Use all active teams ordered by team number
            teams = Team.query.filter_by(status='active').order_by(Team.team_nummer).all()
        
        # Clear existing team rounds for this round
        # First, get all team rounds
        existing_team_rounds = TeamRound.query.filter_by(round_id=round_id).all()
        
        # Delete related scores
        for team_round in existing_team_rounds:
            # Get all scores for this team round
            scores = Score.query.filter_by(team_round_id=team_round.team_round_id).all()
            
            # Delete score values
            for score in scores:
                ScoreValue.query.filter_by(score_id=score.score_id).delete()
            
            # Delete scores
            Score.query.filter_by(team_round_id=team_round.team_round_id).delete()
        
        # Now delete team rounds
        TeamRound.query.filter_by(round_id=round_id).delete()
        
        # Get judges limited to event's num_judges setting
        num_judges = event.num_judges if event.num_judges else 3
        judges = Teilnehmer.query.filter_by(is_punktwerter=True).order_by(Teilnehmer.name).limit(num_judges).all()

        # Create new team rounds with specified order, plus Score records for each judge
        for index, team in enumerate(teams, start=1):
            team_round = TeamRound(
                round_id=round_id,
                team_id=team.team_id,
                start_order=index,
                status='Pending'
            )
            db.session.add(team_round)
            db.session.flush()  # Get team_round_id

            # Create empty Score record for each judge
            for judge in judges:
                score = Score(
                    team_round_id=team_round.team_round_id,
                    judge_id=judge.teilnehmer_id,
                    entered_at=datetime.utcnow()
                )
                db.session.add(score)

        db.session.commit()
        logger.info(f"Successfully generated scoresheets for round {round_id} with {len(teams)} teams and {len(teams) * len(judges)} score records")
        return True
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error generating scoresheets for round {round_id}: {str(e)}")
        return False

def extract_last_name(full_name):
    """Extract last name from full name"""
    if not full_name:
        return "N/A"
    parts = full_name.strip().split()
    return parts[-1] if parts else "N/A"


@formular_bp.route('/')
def index():
    """Display active teams for start list generation and all round start lists"""
    # Get events
    events = Event.query.filter_by(is_hidden=False).order_by(Event.event_date.desc()).all()
    active_teams = Team.query.filter_by(status='active').all()
    
    # Get lock status
    lock_config = SystemConfig.query.filter_by(config_key='startlist_locked').first()
    is_locked = lock_config.config_value == 'true' if lock_config else False
    
    # Get saved order from session for initial round
    saved_order = session.get('team_order', [])
    
    # Get selected or active event — remember selection in session
    event_id = request.args.get('event_id', type=int)
    if not event_id:
        event_id = session.get('formular_event_id')
    if event_id:
        active_event = Event.query.get(event_id)
    else:
        active_event = Event.query.filter_by(status='Active').first()
    if not active_event and events:
        active_event = events[0]
    if active_event:
        session['formular_event_id'] = active_event.event_id
    
    # Get all rounds for this event with their start orders
    all_rounds = []
    round_orders = {}
    all_round_objects = []
    all_teams_by_id = {team.team_id: team for team in active_teams}

    if active_event:
        # Get all rounds from the database with actual TeamRound entries
        all_round_objects = Round.query.filter_by(event_id=active_event.event_id).order_by(Round.round_number).all()
        
        # Filter for rounds that have actual TeamRound entries and exclude Round 1
        for round_obj in all_round_objects:
            # Skip Round 1 - it's already displayed at the top
            if round_obj.round_number == 1:
                continue
                
            # Check if this round has any TeamRound entries
            team_rounds = TeamRound.query.filter_by(round_id=round_obj.round_id).all()
            if not team_rounds:
                continue  # Skip rounds with no TeamRound entries
                
            # Add round to our filtered list
            all_rounds.append(round_obj)
            
            # Create list of teams with start order information
            round_teams = []
            for team_round in team_rounds:
                team = all_teams_by_id.get(team_round.team_id)
                if team:
                    # Get the actual pilot names for this team
                    schlepper_pilot_name = team.schlepper_pilot.name if team.schlepper_pilot else "-"
                    segler_pilot_name = team.segler_pilot.name if team.segler_pilot else "-"
                    
                    # Include scores if available
                    round_teams.append({
                        'team_id': team.team_id,
                        'team_nummer': team.team_nummer,
                        'start_order': team_round.start_order or 0,
                        'raw_score': team_round.raw_score,
                        'normalized_score': team_round.normalized_score,
                        'rank': team_round.rank,
                        'schlepper_pilot': schlepper_pilot_name,
                        'segler_pilot': segler_pilot_name
                    })
            
            # Sort by start order
            round_teams.sort(key=lambda x: x['start_order'] or float('inf'))
            round_orders[round_obj.round_id] = round_teams
    
    # Calculate if we need to show the "Generate Next Round" button
    show_generate_button = False
    next_round_number = 1
    
    if all_round_objects:
        # Find the highest round number with scores
        highest_scored_round = None
        highest_round_number = 0
        
        for round_obj in all_round_objects:
            team_rounds = TeamRound.query.filter_by(round_id=round_obj.round_id).all()
            has_scores = any(tr.raw_score is not None for tr in team_rounds)
            
            if has_scores and round_obj.round_number > highest_round_number:
                highest_scored_round = round_obj
                highest_round_number = round_obj.round_number
        
        # Next round would be one after the highest scored round
        if highest_scored_round:
            next_round_number = highest_round_number + 1
            show_generate_button = True
            
            # Check if the next round already exists with scores
            next_round = Round.query.filter_by(
                event_id=active_event.event_id, 
                round_number=next_round_number
            ).first()
            
            if next_round:
                team_rounds = TeamRound.query.filter_by(round_id=next_round.round_id).all()
                has_scores = any(tr.raw_score is not None for tr in team_rounds)
                
                # If the next round already has scores, don't show the generate button
                if has_scores:
                    show_generate_button = False
    
    return render_template('formular/formular_main.html', 
                          teams=active_teams, 
                          events=events,
                          is_locked=is_locked,
                          saved_order=saved_order,
                          all_rounds=all_rounds,
                          round_orders=round_orders,
                          active_event=active_event,
                          show_generate_button=show_generate_button,
                          next_round_number=next_round_number)

@formular_bp.route('/save-order', methods=['POST'])
def save_order():
    """Save the current team order"""
    try:
        order = request.json.get('order', [])
        
        # Save in session
        session['team_order'] = order
        
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error saving team order: {str(e)}")
        return jsonify({'status': 'error'}), 500

@formular_bp.route('/toggle-lock', methods=['POST'])
def toggle_lock():
    """Toggle the lock state of the startlist and generate scoresheets if locking"""
    try:
        # Check if active event is completed/published
        active_event = Event.query.filter_by(status='Active', is_hidden=False).first()
        if not active_event:
            active_event = Event.query.filter_by(is_hidden=False).order_by(Event.event_date.desc()).first()
        if active_event and active_event.status in ('Completed', 'Published'):
            return jsonify({'status': 'error', 'message': 'Abgeschlossene Wettbewerbe können nicht geändert werden'}), 403

        # Get current lock state
        lock_config = SystemConfig.query.filter_by(config_key='startlist_locked').first()
        
        if not lock_config:
            # Create if it doesn't exist
            lock_config = SystemConfig(config_key='startlist_locked', config_value='false')
            db.session.add(lock_config)
        
        # Toggle the value with proper sanitization
        current_state = lock_config.config_value.strip().lower()
        new_state = 'false' if current_state == 'true' else 'true'
        lock_config.config_value = new_state
        
        # If we're locking the start list, generate scoresheets
        if new_state == 'true':
            # Get the current order from the session
            team_order = session.get('team_order', [])

            if team_order:
                # Use event_id from request body
                data = request.get_json(silent=True) or {}
                event_id_from_request = data.get('event_id')
                if event_id_from_request:
                    active_event = Event.query.get(event_id_from_request)
                else:
                    active_event = Event.query.filter_by(status='Active').first()
                if not active_event:
                    active_event = Event.query.order_by(Event.event_date.desc()).first()
                
                if active_event:
                    # Find or create round 1
                    round_1 = Round.query.filter_by(
                        event_id=active_event.event_id,
                        round_number=1
                    ).first()
                    
                    if not round_1:
                        round_1 = Round(
                            event_id=active_event.event_id,
                            round_number=1,
                            status='Active'
                        )
                        db.session.add(round_1)
                        db.session.flush()
                    
                    # Generate scoresheets
                    if generate_scoresheets_for_round(round_1.round_id, team_order):
                        flash('Startliste gesperrt und Bewertungsbögen erstellt', 'success')
                    else:
                        flash('Startliste gesperrt, aber Fehler beim Erstellen der Bewertungsbögen', 'warning')
                else:
                    flash('Startliste gesperrt, aber kein Wettbewerb gefunden', 'warning')
            else:
                flash('Startliste gesperrt, aber keine Teamreihenfolge gefunden', 'warning')
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'locked': new_state == 'true'
        })
    except Exception as e:
        logger.error(f"Error toggling lock state: {str(e)}")
        db.session.rollback()
        return jsonify({'status': 'error'}), 500

@formular_bp.route('/print/<int:event_id>')
def print_list(event_id):
    """Generate printer-friendly PDF starting list using exact table order"""
    try:
        event = Event.query.get_or_404(event_id)
        
        # Get order from session
        order = session.get('team_order', [])
        
        all_teams = {team.team_nummer: team for team in Team.query.filter_by(status='active').all()}
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []
        
        styles = getSampleStyleSheet()
        title_style = styles['Title']
        
        # Header
        elements.append(Paragraph(event.name, title_style))
        elements.append(Paragraph(
            f"Datum: {event.event_date.strftime('%d.%m.%Y') if event.event_date else 'N/A'} - 1. Durchgang",
            styles['Normal']
        ))
        elements.append(Spacer(1, 12))  # Add 12 points (equivalent to 1 line) of space
        
        # Use exact same order as displayed table
        data = [['Start Nr.', 'Team', 'Schlepper', 'Segler']]
        for i, team_num in enumerate(order, 1):
            team = all_teams[team_num]
            data.append([
                str(i),
                f"Team {team.team_nummer}",
                team.schlepper_pilot.name if team.schlepper_pilot else '-',
                team.segler_pilot.name if team.segler_pilot else '-'
            ])
            
        table = Table(data)
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6)
        ]))
        
        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        
        return send_file(
            buffer,
            download_name=f'startliste.pdf',
            mimetype='application/pdf',
            as_attachment=True
        )
        
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        flash('Fehler beim Erstellen der PDF', 'error')
        return redirect(url_for('formular.index'))

@formular_bp.route('/api/next-round-order', methods=['POST'])
def api_next_round_order():
    """API endpoint to display the next round order based on existing scores - PURELY INFORMATIONAL"""
    try:
        # Get active event
        active_event = Event.query.filter_by(status='Active', is_hidden=False).first()
        if not active_event:
            active_event = Event.query.filter_by(is_hidden=False).order_by(Event.event_date.desc()).first()

        if not active_event:
            return jsonify({
                'status': 'error',
                'message': 'No active event found'
            }), 404
        
        # Get all rounds for this event
        all_rounds = Round.query.filter_by(event_id=active_event.event_id).order_by(Round.round_number).all()
        
        # Find the latest round that has scores
        latest_scored_round = None
        
        for round_obj in all_rounds:
            # Check if this round has any scores
            team_rounds = TeamRound.query.filter_by(round_id=round_obj.round_id).all()
            
            if any(tr.raw_score is not None for tr in team_rounds):
                # Keep updating to find the latest round with scores
                latest_scored_round = round_obj
        
        if not latest_scored_round:
            return jsonify({
                'status': 'error',
                'message': 'No rounds with scores found'
            }), 404
        
        # Get all team rounds with scores for the latest scored round
        team_rounds_with_scores = TeamRound.query.filter_by(round_id=latest_scored_round.round_id)\
            .filter(TeamRound.raw_score != None)\
            .all()
            
        # Prepare team data with scores
        round_data = []
        teams_with_scores = set()
        
        for team_round in team_rounds_with_scores:
            team = Team.query.get(team_round.team_id)
            if team and team.status == 'active':
                teams_with_scores.add(team.team_id)
                round_data.append({
                    'team_id': team.team_id,
                    'team_nummer': team.team_nummer,
                    'normalized_score': team_round.normalized_score,
                    'raw_score': team_round.raw_score,
                    'rank': team_round.rank,
                    'schlepper_pilot': team.schlepper_pilot.name if team.schlepper_pilot else '-',
                    'segler_pilot': team.segler_pilot.name if team.segler_pilot else '-'
                })
        
        # Sort by raw score (ascending - lowest score first)
        round_data.sort(key=lambda x: x['raw_score'] if x['raw_score'] is not None else float('inf'))
        
        # Get teams without scores
        teams_without_scores = []
        all_active_teams = Team.query.filter_by(status='active').all()
        
        for team in all_active_teams:
            if team.team_id not in teams_with_scores:
                teams_without_scores.append({
                    'team_id': team.team_id,
                    'team_nummer': team.team_nummer,
                    'schlepper_pilot': team.schlepper_pilot.name if team.schlepper_pilot else '-',
                    'segler_pilot': team.segler_pilot.name if team.segler_pilot else '-'
                })
        
        # Calculate hypothetical next round number
        next_round_number = latest_scored_round.round_number + 1
        
        # Assign positions for display only
        position = 1
        for team_data in round_data:
            team_data['start_order'] = position
            position += 1
            
        # Add positions for teams without scores
        for team_data in teams_without_scores:
            team_data['start_order'] = position
            position += 1
        
        # Create combined data for the response
        combined_data = round_data + teams_without_scores
        next_order = [team['team_nummer'] for team in combined_data]
        
        logger.info(f"Displaying next round order based on round {latest_scored_round.round_number}")
        
        return jsonify({
            'status': 'success',
            'message': f'Next round order based on round {latest_scored_round.round_number}',
            'next_round_number': next_round_number,
            'next_round_order': next_order,
            'source_round': latest_scored_round.round_number,
            'round_data': round_data,
            'teams_without_scores': teams_without_scores
        })
        
    except Exception as e:
        logger.error(f"Error displaying next round order: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error displaying next round order: {str(e)}'
        }), 500

@formular_bp.route('/update_start_order/<int:round_id>', methods=['POST'])
def update_start_order(round_id):
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

@formular_bp.route('/print-round/<int:round_id>')
def print_round_list(round_id):
    """Generate printer-friendly PDF for a specific round's start order"""
    try:
        round_obj = Round.query.get_or_404(round_id)
        event = Event.query.get_or_404(round_obj.event_id)
        
        # Get team rounds for this round, ordered by start_order
        team_rounds = TeamRound.query.filter_by(round_id=round_id).order_by(TeamRound.start_order).all()
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []
        
        styles = getSampleStyleSheet()
        title_style = styles['Title']
        
        # Header
        elements.append(Paragraph(event.name, title_style))
        elements.append(Paragraph(
            f"Datum: {event.event_date.strftime('%d.%m.%Y') if event.event_date else 'N/A'} - Durchgang {round_obj.round_number}",
            styles['Normal']
        ))
        elements.append(Spacer(1, 12))
        
        # Create table data
        data = [['Start Nr.', 'Team', 'Schlepper', 'Segler']]
        
        for team_round in team_rounds:
            team = Team.query.get(team_round.team_id)
            if team:
                data.append([
                    str(team_round.start_order or '-'),
                    f"Team {team.team_nummer}",
                    team.schlepper_pilot.name if team.schlepper_pilot else '-',
                    team.segler_pilot.name if team.segler_pilot else '-'
                ])
            
        table = Table(data)
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6)
        ]))
        
        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        
        return send_file(
            buffer,
            download_name=f'startliste_durchgang_{round_obj.round_number}.pdf',
            mimetype='application/pdf',
            as_attachment=True
        )
        
    except Exception as e:
        logger.error(f"Error generating round PDF: {str(e)}")
        flash('Fehler beim Erstellen der PDF', 'error')
        return redirect(url_for('formular.index'))

@formular_bp.route('/print_scoresheets')
def print_scoresheets():
    """Generate printer-friendly blank scoresheets"""
    try:
        # Get active figures for the scoresheets
        figures = TaskType.query.filter_by(is_active=True).order_by(TaskType.sort_order).all()
        
        # Just create a few blank scoresheets for printing
        # The actual number of physical copies will be determined by the printer
        scoresheets = list(range(2))  # Just generate 42 scoresheets (1 pages)
        
        return render_template('formular/print_scoresheets.html', 
                              figures=figures,
                              scoresheets=scoresheets)
                              
    except Exception as e:
        logger.error(f"Error generating scoresheets: {str(e)}")
        flash('Fehler beim Erstellen der Bewertungsbögen', 'error')
        return redirect(url_for('formular.index'))

@formular_bp.route('/export-labels')
# Export labels works, but the niimh app only reads sheets sent to whatssapp.
# Send label to yourself, then open.

def export_labels():
    """Export team labels for Niimbot D11 in Excel format"""
    try:
        # Get parameters
        event_id = request.args.get('event_id', type=int)
        max_rounds = request.args.get('max_rounds', 2, type=int)
        
        if not event_id:
            flash('Keine Veranstaltung ausgewählt', 'error')
            return redirect(url_for('formular.index'))
        
        # Get event
        event = Event.query.get_or_404(event_id)
        
        # Get team order from session (same as used for PDF)
        team_order = session.get('team_order', [])
        
        if not team_order:
            # Fallback to all active teams in team number order
            active_teams = Team.query.filter_by(status='active').order_by(Team.team_nummer).all()
            team_order = [team.team_nummer for team in active_teams]
        
        # Get team objects in the correct order
        all_teams = {team.team_nummer: team for team in Team.query.filter_by(status='active').all()}
        ordered_teams = []
        
        for team_num in team_order:
            if team_num in all_teams:
                ordered_teams.append(all_teams[team_num])
        
        if not ordered_teams:
            flash('Keine Teams in der Startliste gefunden', 'error')
            return redirect(url_for('formular.index'))
        
        # Prepare label data
        label_data = []
        
        # Generate labels for each round
        for round_num in range(1, max_rounds + 1):
            for team in ordered_teams:
                # Extract last names
                schlepper_last = extract_last_name(team.schlepper_pilot.name if team.schlepper_pilot else None)
                segler_last = extract_last_name(team.segler_pilot.name if team.segler_pilot else None)
                
                # Format names for second line
                if schlepper_last != "N/A" and segler_last != "N/A":
                    names_line = f"{schlepper_last} / {segler_last}"
                elif schlepper_last != "N/A":
                    names_line = schlepper_last
                elif segler_last != "N/A":
                    names_line = segler_last
                else:
                    names_line = "Nicht zugewiesen"
                
                # Create label entry
                label_entry = {
                    'Line1': f"Team {team.team_nummer}: Durchgang: {round_num}",
                    'Line2': names_line
                    
                }
                
                label_data.append(label_entry)
        
        # Create DataFrame
        df = pd.DataFrame(label_data)
        
        # Create Excel file using openpyxl engine only
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Team_Labels')
        output.seek(0)
        
        # Generate filename
        event_name = event.name.replace(' ', '_').replace('/', '-')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        filename = f"Team_Labels_{event_name}_{timestamp}.xlsx"
        
        logger.info(f"Generated {len(label_data)} labels for {len(ordered_teams)} teams across {max_rounds} rounds")
        
        return send_file(
            output,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True
        )
        
    except Exception as e:
        logger.error(f"Error generating label export: {str(e)}")
        flash(f'Fehler beim Erstellen der Label-Datei: {str(e)}', 'error')
        return redirect(url_for('formular.index'))

@formular_bp.route('/email-startlist-recipients', methods=['POST'])
def email_startlist_recipients():
    """Return list of potential recipients for start list email"""
    try:
        recipients = []

        # Active team pilots
        for team in Team.query.filter_by(status='active').all():
            if team.schlepper_pilot and team.schlepper_pilot.email:
                recipients.append({
                    'email': team.schlepper_pilot.email,
                    'name': team.schlepper_pilot.name,
                    'role': f'Pilot Team {team.team_nummer}'
                })
            if team.segler_pilot and team.segler_pilot.email:
                recipients.append({
                    'email': team.segler_pilot.email,
                    'name': team.segler_pilot.name,
                    'role': f'Pilot Team {team.team_nummer}'
                })

        # Judges and Wettkampfleitung
        from app.models import Teilnehmer
        officials = Teilnehmer.query.filter(
            (Teilnehmer.is_punktwerter == True) | (Teilnehmer.is_wettkampfleitung == True),
            Teilnehmer.email.isnot(None),
            Teilnehmer.email != ''
        ).all()

        for official in officials:
            role = []
            if official.is_punktwerter:
                role.append('Punktwerter')
            if official.is_wettkampfleitung:
                role.append('Wettkampfleitung')
            recipients.append({
                'email': official.email,
                'name': official.name,
                'role': ', '.join(role)
            })

        # Deduplicate by email
        seen = set()
        unique = []
        for r in recipients:
            if r['email'] not in seen:
                seen.add(r['email'])
                unique.append(r)

        return jsonify({'success': True, 'recipients': unique})

    except Exception as e:
        logger.error(f"Error getting recipients: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@formular_bp.route('/email-startlist', methods=['POST'])
def email_startlist():
    """Email start list to selected recipients only"""
    try:
        data = request.get_json()
        event_id = data.get('event_id')
        team_order = data.get('team_order', [])
        selected_emails = data.get('recipients', [])

        if not selected_emails:
            return jsonify({'success': False, 'message': 'Keine Empfänger ausgewählt'})

        event = Event.query.get_or_404(event_id)
        all_teams = {team.team_nummer: team for team in Team.query.filter_by(status='active').all()}

        recipients = selected_emails
        
        # Create email content
        html_content = f"""
        <p> 1. Durchgang</p>
        
        <table border="1" style="border-collapse: collapse; width: 100%;">
            <tr style="background-color: #f0f0f0;">
                <th style="padding: 8px;">Start Nr.</th>
                <th style="padding: 8px;">Team</th>
                <th style="padding: 8px;">Schlepper</th>
                <th style="padding: 8px;">Segler</th>
            </tr>
        """
        
        for i, team_num in enumerate(team_order, 1):
            team = all_teams[team_num]
            html_content += f"""
            <tr>
                <td style="padding: 8px; text-align: center;">{i}</td>
                <td style="padding: 8px;">Team {team.team_nummer}</td>
                <td style="padding: 8px;">{team.schlepper_pilot.name if team.schlepper_pilot else '-'}</td>
                <td style="padding: 8px;">{team.segler_pilot.name if team.segler_pilot else '-'}</td>
            </tr>
            """
        
        html_content += """
        </table>
        <br><br>
        <p style="color: #666; font-size: 12px;">
            Gesendet von der NRW-Cup Wettkampfleitung.<br>
            Fragen? Mail uns: <a href="mailto:wettkampf@nrw-cup.de">wettkampf@nrw-cup.de</a>
        </p>
        """
        
        # Send email
        import smtplib, ssl
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from app.config import Config
        
        msg = MIMEMultipart()
        msg['From'] = Config.MAIL_USERNAME
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = f"Startliste - {event.name}"
        msg.attach(MIMEText(html_content, 'html'))
        
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(Config.MAIL_SERVER, Config.MAIL_PORT, context=context) as server:
            server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            server.send_message(msg)
        
        return jsonify({'success': True, 'message': f'Startliste an {len(recipients)} Teilnehmer versendet'})
        
    except Exception as e:
        logger.error(f"Error emailing start list: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})
"""
File: app/routes/bp_teams.py
Version: 3.0.0
Created: 2025-03-02
Updated: 2025-04-19
Description: Fixed team management with proper status toggle and numbering system
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, send_file
from app.models import db, Team, Teilnehmer, Flugzeuge, TeamRound
from app.services.services_teams import TeamService
from app.utils.utils_base_controller import BaseController
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_
import logging
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# Configure logger
logger = logging.getLogger(__name__)

# Create blueprint
teams_bp = Blueprint('teams', __name__)

# Initialize service and controller
team_service = TeamService()
team_controller = BaseController(
    model_class=Team,
    template_prefix='teams',
    route_prefix='teams',
    display_name='Team'
)

def process_form_data(form):
    """Process form data for Team model"""
    form_data = form.to_dict()
    
    # Convert numeric fields
    for field in ['team_nummer', 'schlepper_pilot_id', 'segler_pilot_id', 
                  'schlepper_flugzeug_id', 'segler_flugzeug_id']:
        if field in form_data and form_data[field]:
            try:
                form_data[field] = int(form_data[field]) or None
            except (ValueError, TypeError):
                form_data[field] = None
        else:
            form_data[field] = None
    
    # Set default status if not provided
    if 'status' not in form_data:
        form_data['status'] = 'active'
    
    return form_data

def renumber_teams():
    """
    Renumber all active teams to maintain sequential numbering without gaps.
    This function is now optional and only used when explicitly requested.
    """
    try:
        # Get all active teams ordered by current number
        active_teams = Team.query.filter_by(status='active').order_by(Team.team_nummer).all()
        
        # Renumber from 1
        for i, team in enumerate(active_teams, 1):
            team.team_nummer = i
        
        db.session.commit()
        return True
    except Exception as e:
        logger.error(f"Error renumbering teams: {str(e)}")
        db.session.rollback()
        return False

@teams_bp.route('/')
def index():
    """Display list of all teams with related pilot and aircraft info"""
    try:
        # Get all teams with eager loading of relationships - include inactive teams
        teams = db.session.query(Team)\
            .options(
                db.joinedload(Team.schlepper_pilot),
                db.joinedload(Team.segler_pilot),
                db.joinedload(Team.schlepper_flugzeug),
                db.joinedload(Team.segler_flugzeug)
            )\
            .order_by(Team.status, Team.team_nummer)\
            .all()
            
        return render_template('teams/teams_main.html', teams=teams)
        
    except SQLAlchemyError as e:
        logger.error(f"Database error in teams.index: {str(e)}")
        flash('Fehler beim Laden der Teams', 'error')
        return render_template('teams/teams_main.html', teams=[])

@teams_bp.route('/get_aircraft/<int:pilot_id>/<aircraft_type>')
def get_aircraft(pilot_id, aircraft_type):
    """Get available aircraft for a specific pilot and type"""
    try:
        # Get aircraft using service
        aircraft = team_service.get_available_aircraft(pilot_id, aircraft_type)
        
        # Format for JSON response
        return jsonify([{
            'flugzeug_id': a.flugzeug_id,
            'name': a.name
        } for a in aircraft])
        
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_aircraft: {str(e)}")
        return jsonify([])

@teams_bp.route('/create', methods=['GET', 'POST'])
def create():
    """Create a new team"""
    try:
        if request.method == 'POST':
            # Process form data
            form_data = process_form_data(request.form)
            
            # Check if a specific team number was provided
            requested_team_num = form_data.get('team_nummer')
            
            # If a specific team number was requested, check if it's available
            if requested_team_num:
                existing = Team.query.filter_by(team_nummer=requested_team_num, status='active').first()
                if existing:
                    flash(f'Team Nummer {requested_team_num} ist bereits vergeben', 'error')
                    
                    # Get available pilots for dropdowns
                    schlepper_pilots = team_service.get_schlepper_pilots()
                    segler_pilots = team_service.get_segler_pilots()
                    
                    # Get available team numbers (including gaps)
                    available_nums = team_service.get_available_team_numbers()
                    
                    return render_template('teams/teams_create.html',
                                        schlepper_pilots=schlepper_pilots,
                                        segler_pilots=segler_pilots,
                                        available_nums=available_nums,
                                        form_data=form_data)
            
            # Get next available team number if none requested 
            team_nummer = requested_team_num or team_service.get_next_team_number()
            
            # Create new team directly
            new_team = Team(
                team_nummer=team_nummer,
                schlepper_pilot_id=form_data.get('schlepper_pilot_id'),
                segler_pilot_id=form_data.get('segler_pilot_id'),
                schlepper_flugzeug_id=form_data.get('schlepper_flugzeug_id'),
                segler_flugzeug_id=form_data.get('segler_flugzeug_id'),
                status='active'  # Always create as active
            )
            
            db.session.add(new_team)
            db.session.commit()
            
            flash('Team erfolgreich erstellt', 'success')
            return redirect(url_for('teams.index'))
            
        # Get available pilots for dropdowns
        schlepper_pilots = team_service.get_schlepper_pilots()
        segler_pilots = team_service.get_segler_pilots()
        
        # Get available team numbers (including gaps)
        available_nums = team_service.get_available_team_numbers()
            
        return render_template('teams/teams_create.html',
                             schlepper_pilots=schlepper_pilots,
                             segler_pilots=segler_pilots,
                             available_nums=available_nums)
                             
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in teams.create: {str(e)}")
        flash('Fehler beim Erstellen des Teams', 'error')
        return redirect(url_for('teams.index'))

@teams_bp.route('/edit/<int:team_id>', methods=['GET', 'POST'])
def edit(team_id):
    """Edit an existing team"""
    try:
        team = Team.query.get(team_id)
        if not team:
            flash('Team nicht gefunden', 'error')
            return redirect(url_for('teams.index'))
        
        if request.method == 'POST':
            # Process form data
            form_data = process_form_data(request.form)
            
            # Get the requested team number
            new_team_num = form_data.get('team_nummer')
            
            # Check if team number is already taken by another team
            if new_team_num and new_team_num != team.team_nummer:
                existing = Team.query.filter(
                    Team.team_id != team_id, 
                    Team.team_nummer == new_team_num,
                    Team.status == 'active'  # Only check active teams
                ).first()
                
                if existing:
                    flash('Diese Teamnummer existiert bereits', 'error')
                    return redirect(url_for('teams.edit', team_id=team_id))
            
            # Store old number for logging
            old_number = team.team_nummer
            
            # Update fields directly
            team.team_nummer = new_team_num or team.team_nummer
            team.schlepper_pilot_id = form_data.get('schlepper_pilot_id')
            team.segler_pilot_id = form_data.get('segler_pilot_id')
            team.schlepper_flugzeug_id = form_data.get('schlepper_flugzeug_id')
            team.segler_flugzeug_id = form_data.get('segler_flugzeug_id')
            
            # Save changes
            db.session.commit()
            
            # Don't automatically renumber teams anymore
            # Let the user explicitly request renumbering if needed
            
            # Show appropriate success message
            if old_number != team.team_nummer:
                flash(f'Team {old_number} erfolgreich zu Team {team.team_nummer} aktualisiert', 'success')
            else:
                flash('Team erfolgreich aktualisiert', 'success')
                
            return redirect(url_for('teams.index'))
        
        # Get available pilots for dropdowns
        schlepper_pilots = team_service.get_schlepper_pilots()
        segler_pilots = team_service.get_segler_pilots()
        
        # Get available aircraft for pilots
        schlepper_aircraft = []
        segler_aircraft = []
        
        # Get specific pilot's aircraft if pilot is assigned
        if team.schlepper_pilot_id:
            schlepper_aircraft = Flugzeuge.query.filter(
                Flugzeuge.is_schlepper == True,
                or_(
                    Flugzeuge.pilot_id == team.schlepper_pilot_id,
                    Flugzeuge.plane_owner_id == team.schlepper_pilot_id
                )
            ).all()
        else:
            # Otherwise get all schlepper aircraft
            schlepper_aircraft = Flugzeuge.query.filter_by(is_schlepper=True).all()
            
        if team.segler_pilot_id:
            segler_aircraft = Flugzeuge.query.filter(
                Flugzeuge.is_segler == True,
                or_(
                    Flugzeuge.pilot_id == team.segler_pilot_id,
                    Flugzeuge.plane_owner_id == team.segler_pilot_id
                )
            ).all()
        else:
            # Otherwise get all segler aircraft
            segler_aircraft = Flugzeuge.query.filter_by(is_segler=True).all()
            
        return render_template('teams/teams_edit.html',
                             team=team,
                             schlepper_pilots=schlepper_pilots,
                             segler_pilots=segler_pilots,
                             schlepper_aircraft=schlepper_aircraft,
                             segler_aircraft=segler_aircraft)
                             
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in teams.edit: {str(e)}")
        flash('Fehler beim Bearbeiten des Teams', 'error')
        return redirect(url_for('teams.index'))

@teams_bp.route('/delete/<int:team_id>', methods=['POST'])
def delete(team_id):
    """Delete a team if it has no dependent data"""
    try:
        # Get the team
        team = Team.query.get(team_id)
        if not team:
            flash('Team nicht gefunden', 'error')
            return redirect(url_for('teams.index'))
        
        # Check if the team has TeamRound entries
        team_rounds = TeamRound.query.filter_by(team_id=team_id).first()
        if team_rounds:
            flash('Team kann nicht gelöscht werden - es existieren abhängige Wettkampfdaten. Nutze Deaktivieren stattdessen.', 'error')
            return redirect(url_for('teams.index'))
        
        # Store team number for reference
        team_nummer = team.team_nummer
        
        # Delete the team
        db.session.delete(team)
        db.session.commit()
        
        flash(f'Team {team_nummer} erfolgreich gelöscht', 'success')
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in teams.delete: {str(e)}")
        flash('Fehler beim Löschen des Teams', 'error')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in teams.delete: {str(e)}")
        flash('Unerwarteter Fehler beim Löschen des Teams', 'error')
        
    return redirect(url_for('teams.index'))

@teams_bp.route('/toggle_status/<int:team_id>', methods=['POST'])
def toggle_status(team_id):
    """Toggle team status between active and disabled"""
    try:
        # Get the team directly
        team = Team.query.get(team_id)
        if not team:
            flash('Team nicht gefunden', 'error')
            return redirect(url_for('teams.index'))
        
        # Toggle status - just update the status field, don't delete
        new_status = 'disabled' if team.status == 'active' else 'active'
        old_number = team.team_nummer
        
        # If activating a team, check for number conflicts
        if new_status == 'active':
            # Check if this team number is already in use by another active team
            existing = Team.query.filter(
                Team.team_id != team_id,
                Team.team_nummer == old_number,
                Team.status == 'active'
            ).first()
            
            if existing:
                # If number is taken, assign next available number
                team.team_nummer = team_service.get_next_team_number()
                
        team.status = new_status
        db.session.commit()
        
        # Don't automatically renumber teams anymore to preserve team numbers
        # Only renumber if explicitly requested
        
        status_text = "deaktiviert" if new_status == 'disabled' else "aktiviert"
        
        if new_status == 'active' and old_number != team.team_nummer:
            flash(f'Team {old_number} erfolgreich {status_text} mit neuer Nummer {team.team_nummer} (alte Nummer war bereits vergeben)', 'success')
        else:
            flash(f'Team {team.team_nummer} erfolgreich {status_text}', 'success')
        
        # Redirect to team list
        return redirect(url_for('teams.index'))
            
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error toggling team status: {str(e)}")
        flash('Fehler beim Ändern des Team-Status', 'error')
        return redirect(url_for('teams.index'))

@teams_bp.route('/renumber', methods=['POST'])
def renumber():
    """Manually renumber all active teams to eliminate gaps"""
    try:
        success = renumber_teams()
        if success:
            flash('Teams erfolgreich neu nummeriert', 'success')
        else:
            flash('Fehler bei der Neunummerierung der Teams', 'error')
    except Exception as e:
        logger.error(f"Error in renumber: {str(e)}")
        flash('Unerwarteter Fehler bei der Neunummerierung', 'error')
        
    return redirect(url_for('teams.index'))

@teams_bp.route('/print')
def print_list():
    """Generate printer-friendly PDF team list"""
    try:
        # Get active teams with eager loading of relationships
        teams = db.session.query(Team)\
            .filter_by(status='active')\
            .options(
                db.joinedload(Team.schlepper_pilot),
                db.joinedload(Team.segler_pilot),
                db.joinedload(Team.schlepper_flugzeug),
                db.joinedload(Team.segler_flugzeug)
            )\
            .order_by(Team.team_nummer)\
            .all()
            
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []
        
        styles = getSampleStyleSheet()
        title_style = styles['Title']
        
        # Header
        elements.append(Paragraph(f"NRW Cup {datetime.now().year}", title_style))
        elements.append(Paragraph(
            f"Datum: {datetime.now().strftime('%d.%m.%Y')} - Teamliste",
            styles['Normal']
        ))
        elements.append(Spacer(1, 12))  # Add 12 points (equivalent to 1 line) of space
        
        # Team table
        data = [['Team Nr.', 'Schlepper Pilot', 'Segler Pilot', 'Schlepper', 'Segler']]
        for team in teams:
            data.append([
                str(team.team_nummer),
                team.schlepper_pilot.name if team.schlepper_pilot else '-',
                team.segler_pilot.name if team.segler_pilot else '-',
                team.schlepper_flugzeug.name if team.schlepper_flugzeug else '-',
                team.segler_flugzeug.name if team.segler_flugzeug else '-'
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
            download_name=f'teamliste.pdf',
            mimetype='application/pdf',
            as_attachment=True
        )
        
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        flash('Fehler beim Erstellen der PDF', 'error')
        return redirect(url_for('teams.index'))
"""
File: app/routes/bp_flugzeuge.py
Version: 2.1.0
Created: 2025-04-01
Description: Fixed blueprint for aircraft management with working data storage
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from app.models import db, Flugzeuge, Teilnehmer
from app.services.services_flugzeuge import FlugzeugeService
from sqlalchemy.exc import SQLAlchemyError
import logging

# Configure logger
logger = logging.getLogger(__name__)

# Create blueprint
flugzeuge_bp = Blueprint('flugzeuge', __name__)

# Initialize service
flugzeuge_service = FlugzeugeService()

# In the process_form_data function
def process_form_data(form):
    """Process form data for Flugzeuge model"""
    form_data = {}
    
    # Extract standard text fields with empty string fallback
    for field in ['name', 'antrieb', 'prop', 'fernsteuerung']:
        form_data[field] = form.get(field, '').strip() or None
    
    # Handle boolean fields
    form_data['is_segler'] = 'is_segler' in form
    form_data['is_schlepper'] = 'is_schlepper' in form
    
    # Convert optional numeric fields (allow None)
    for field in ['span', 'gewicht']:
        value = form.get(field, '').strip()
        if value:
            try:
                form_data[field] = float(value)
            except ValueError:
                form_data[field] = None
        else:
            form_data[field] = None
    
    # Convert ID fields (allow None)
    for field in ['pilot_id', 'plane_owner_id']:
        value = form.get(field, '').strip()
        if value:
            try:
                form_data[field] = int(value)
            except ValueError:
                form_data[field] = None
        else:
            form_data[field] = None
    
    return form_data

@flugzeuge_bp.route('/')
def index():
    """Display list of all aircraft with filters"""
    try:
        # Get filter parameters
        aircraft_type = request.args.get('type', '')
        
        # Get data based on filter
        if aircraft_type:
            aircraft = flugzeuge_service.get_by_type(aircraft_type)
        else:
            aircraft = flugzeuge_service.get_all(order_by='name')
        
        # Load relationships for display
        for plane in aircraft:
            if plane.pilot_id:
                plane.pilot = Teilnehmer.query.get(plane.pilot_id)
            if plane.plane_owner_id:
                plane.owner = Teilnehmer.query.get(plane.plane_owner_id)
        
        return render_template(
            'flugzeuge/flugzeuge_main.html', 
            aircraft=aircraft,
            selected_type=aircraft_type
        )
                             
    except SQLAlchemyError as e:
        logger.error(f"Database error in index: {str(e)}")
        flash('Fehler beim Laden der Flugzeuge', 'error')
        return render_template(
            'flugzeuge/flugzeuge_main.html', 
            aircraft=[]
        )

@flugzeuge_bp.route('/add', methods=['GET', 'POST'])
def add():
    """Add a new aircraft - FIXED"""
    try:
        if request.method == 'POST':
            # Log the raw form data for debugging
            logger.debug(f"Raw form data: {request.form}")
            
            # Validation
            if not request.form.get('name'):
                flash('Name ist erforderlich', 'error')
                return render_template(
                    'flugzeuge/flugzeuge_add.html',
                    pilots=flugzeuge_service.get_eligible_pilots()
                )
            
            # Process form data with the fixed function
            form_data = process_form_data(request.form)
            
            # Create aircraft using service
            aircraft = flugzeuge_service.create(**form_data)
            
            if aircraft:
                flash('Flugzeug erfolgreich angelegt', 'success')
                return redirect(url_for('flugzeuge.index'))
            else:
                flash('Fehler beim Anlegen des Flugzeugs', 'error')
                return render_template(
                    'flugzeuge/flugzeuge_add.html',
                    pilots=flugzeuge_service.get_eligible_pilots()
                )
            
        # Get lists of pilots for dropdowns
        pilots = flugzeuge_service.get_eligible_pilots()
        
        return render_template(
            'flugzeuge/flugzeuge_add.html',
            pilots=pilots
        )
                             
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in add: {str(e)}")
        flash('Fehler beim Anlegen des Flugzeugs', 'error')
        return redirect(url_for('flugzeuge.index'))

@flugzeuge_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    """Edit an existing aircraft - FIXED"""
    try:
        aircraft = flugzeuge_service.get_by_id(id)
        if not aircraft:
            flash('Flugzeug nicht gefunden', 'error')
            return redirect(url_for('flugzeuge.index'))
        
        if request.method == 'POST':
            # Log the raw form data for debugging
            logger.debug(f"Edit form data: {request.form}")
            
            # Validation
            if not request.form.get('name'):
                flash('Name ist erforderlich', 'error')
                return render_template(
                    'flugzeuge/flugzeuge_edit.html', 
                    aircraft=aircraft,
                    pilots=flugzeuge_service.get_eligible_pilots()
                )
            
            # Process form data with the fixed function
            form_data = process_form_data(request.form)
            
            # Update using service
            result = flugzeuge_service.update(id, **form_data)
            
            if result:
                flash('Flugzeug erfolgreich aktualisiert', 'success')
                return redirect(url_for('flugzeuge.index'))
            else:
                flash('Fehler beim Aktualisieren des Flugzeugs', 'error')
                return render_template(
                    'flugzeuge/flugzeuge_edit.html', 
                    aircraft=aircraft,
                    pilots=flugzeuge_service.get_eligible_pilots()
                )
            
        # Get lists for dropdowns
        pilots = flugzeuge_service.get_eligible_pilots()
        
        return render_template(
            'flugzeuge/flugzeuge_edit.html',
            aircraft=aircraft,
            pilots=pilots
        )
                             
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in edit: {str(e)}")
        flash('Fehler beim Bearbeiten des Flugzeugs', 'error')
        return redirect(url_for('flugzeuge.index'))

@flugzeuge_bp.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    """Delete an aircraft if it's not referenced elsewhere"""
    try:
        # Check if aircraft can be deleted
        if not flugzeuge_service.can_delete(id):
            flash('Flugzeug kann nicht gelöscht werden - es wird von Teams verwendet', 'error')
            return redirect(url_for('flugzeuge.index'))
            
        # Delete using service
        success = flugzeuge_service.delete(id)
        if success:
            flash('Flugzeug erfolgreich gelöscht', 'success')
        else:
            flash('Fehler beim Löschen des Flugzeugs', 'error')
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in delete: {str(e)}")
        flash('Fehler beim Löschen des Flugzeugs', 'error')
        
    return redirect(url_for('flugzeuge.index'))
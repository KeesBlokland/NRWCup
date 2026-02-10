"""
File: app/routes/bp_teilnehmer_full.py
Version: 3.0.0
Created: 2025-03-02
Description: Fully refactored teilnehmer blueprint using BaseController and TeilnehmerService
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.models import db, Teilnehmer
from app.utils.utils_base_controller import BaseController
from app.services.services_teilnehmer import TeilnehmerService
from sqlalchemy.exc import SQLAlchemyError
import logging

# Configure logger
logger = logging.getLogger(__name__)

# Create blueprint
teilnehmer_bp = Blueprint('teilnehmer', __name__)

# Initialize service and controller
teilnehmer_service = TeilnehmerService()
teilnehmer_controller = BaseController(
    model_class=Teilnehmer,
    template_prefix='teilnehmer',
    route_prefix='teilnehmer',
    display_name='Teilnehmer'
)

def process_form_data(form):
    """Process form data for Teilnehmer model"""
    form_data = form.to_dict()
    
    # Handle boolean fields - set to True if present in form
    for field in ['laermpass', 'is_segler_pilot', 'is_schlepper_pilot', 'is_punktwerter', 'is_wettkampfleitung']:
        form_data[field] = field in form_data
    
    return form_data

@teilnehmer_bp.route('/')
def index():
    """Display list of all participants with filters"""
    try:
        # Get filter parameters
        role = request.args.get('role', '')
        verein = request.args.get('verein', '')
        
        # Get data based on filters
        if role:
            teilnehmers = teilnehmer_service.get_by_role(role)
        elif verein:
            teilnehmers = teilnehmer_service.get_by_club(verein)
        else:
            teilnehmers = teilnehmer_service.get_all(order_by='name')
        
        # Get clubs for filter dropdown
        vereine = teilnehmer_service.get_unique_clubs()
        
        return render_template(
            'teilnehmer/teilnehmer_main.html', 
            teilnehmers=teilnehmers,
            vereine=vereine,
            selected_role=role,
            selected_verein=verein
        )
                             
    except SQLAlchemyError as e:
        logger.error(f"Database error in index: {str(e)}")
        flash('Fehler beim Laden der Teilnehmer', 'error')
        return render_template(
            'teilnehmer/teilnehmer_main.html', 
            teilnehmers=[],
            vereine=[]
        )

@teilnehmer_bp.route('/add', methods=['GET', 'POST'])
def add():
    """Add a new participant"""
    if request.method == 'POST':
        try:
            # Validation
            if not request.form.get('name'):
                flash('Name ist erforderlich', 'error')
                return render_template('teilnehmer/teilnehmer_add.html')
            
            # Process form data
            form_data = process_form_data(request.form)
            
            # Create using service
            teilnehmer_service.create(**form_data)
            flash('Teilnehmer erfolgreich angelegt', 'success')
            return redirect(url_for('teilnehmer.index'))
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error in add: {str(e)}")
            flash('Fehler beim Anlegen des Teilnehmers', 'error')
            return render_template('teilnehmer/teilnehmer_add.html')
            
    return render_template('teilnehmer/teilnehmer_add.html')

@teilnehmer_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    """Edit an existing participant"""
    try:
        teilnehmer = teilnehmer_service.get_by_id(id)
        if not teilnehmer:
            flash('Teilnehmer nicht gefunden', 'error')
            return redirect(url_for('teilnehmer.index'))
        
        if request.method == 'POST':
            # Validation
            if not request.form.get('name'):
                flash('Name ist erforderlich', 'error')
                return render_template('teilnehmer/teilnehmer_edit.html', teilnehmer=teilnehmer)

            # Process form data
            form_data = process_form_data(request.form)
            
            # Update record using service
            teilnehmer_service.update(id, **form_data)
            flash('Teilnehmer erfolgreich aktualisiert', 'success')
            return redirect(url_for('teilnehmer.index'))
                
        return render_template('teilnehmer/teilnehmer_edit.html', teilnehmer=teilnehmer)
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in edit: {str(e)}")
        flash('Fehler beim Laden des Teilnehmers', 'error')
        return redirect(url_for('teilnehmer.index'))

@teilnehmer_bp.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    """Delete a participant"""
    try:
        # Check if teilnehmer can be deleted
        if not teilnehmer_service.can_delete(id):
            flash('Teilnehmer kann nicht gelöscht werden - es existieren abhängige Datensätze', 'error')
            return redirect(url_for('teilnehmer.index'))
            
        # Delete using service
        success = teilnehmer_service.delete(id)
        if success:
            flash('Teilnehmer erfolgreich gelöscht', 'success')
        else:
            flash('Fehler beim Löschen des Teilnehmers', 'error')
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in delete: {str(e)}")
        flash('Fehler beim Löschen des Teilnehmers', 'error')
        
    return redirect(url_for('teilnehmer.index'))
"""
File: app/routes/bp_figures_refactored.py 
Version: 2.0.0
Created: 2025-03-02
Description: Refactored blueprint for managing scoring figures using service layer
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash
from app.models import db, TaskType
from app.services.services_figures import FiguresService
from sqlalchemy.exc import SQLAlchemyError
import logging

# Configure logger
logger = logging.getLogger(__name__)

# Create blueprint
figures_bp = Blueprint('figures', __name__)

# Initialize service
figures_service = FiguresService()

def process_form_data(form):
    """Process form data for TaskType model"""
    form_data = form.to_dict()
    form_data.pop('csrf_token', None)

    # Handle boolean fields
    form_data['is_active'] = form_data.get('is_active') == 'on'
    
    # Convert numeric fields
    for field in ['max_value', 'sort_order', 'k_factor']:
        if field in form_data and form_data[field]:
            try:
                if field == 'max_value':
                    form_data[field] = float(form_data[field])
                else:
                    form_data[field] = int(form_data[field])
            except ValueError:
                form_data[field] = None
    
    return form_data

@figures_bp.route('/')
def index():
    """Display list of all scoring figures with their descriptions and values"""
    try:
        # Get figures ordered by sort_order
        task_types = figures_service.get_ordered_figures()
        
        return render_template('figures/figures_main.html', 
                             task_types=task_types)
                             
    except SQLAlchemyError as e:
        logger.error(f"Database error in figures.index: {str(e)}")
        flash('Fehler beim Laden der Figuren', 'error')
        return render_template('figures/figures_main.html', task_types=[])

@figures_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    """Edit a figure's details"""
    try:
        task = figures_service.get_by_id(id)
        if not task:
            flash('Figur nicht gefunden', 'error')
            return redirect(url_for('figures.index'))
        
        if request.method == 'POST':
            # Process form data
            form_data = process_form_data(request.form)
            
            # Only renumber if is_active changed (deactivation pushes figure to end)
            was_active = task.is_active
            figures_service.update(id, **form_data)
            if was_active and not form_data.get('is_active'):
                figures_service.renumber_figures()
            flash('Figur erfolgreich aktualisiert', 'success')
            return redirect(url_for('figures.index'))
            
        return render_template('figures/figures_form.html', task=task)
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in figures.edit: {str(e)}")
        flash('Fehler beim Bearbeiten der Figur', 'error')
        return redirect(url_for('figures.index'))

@figures_bp.route('/add', methods=['GET', 'POST'])
def add():
    """Add a new figure"""
    try:
        if request.method == 'POST':
            # Process form data
            form_data = process_form_data(request.form)
            
            # Set default values for required fields
            if 'score_type' not in form_data:
                form_data['score_type'] = 'float'
            if 'name' not in form_data:
                form_data['name'] = form_data.get('name_de', '')
            
            figures_service.create(**form_data)
            flash('Figur erfolgreich angelegt', 'success')
            return redirect(url_for('figures.index'))
            
        return render_template('figures/figures_form.html', task=None)
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in figures.add: {str(e)}")
        flash('Fehler beim Anlegen der Figur', 'error')
        return redirect(url_for('figures.index'))

@figures_bp.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    """Delete a figure"""
    try:
        # Check if figure can be deleted
        if not figures_service.can_delete(id):
            flash('Figur kann nicht gelöscht werden - es existieren abhängige Wertungen', 'error')
            return redirect(url_for('figures.index'))
            
        # Get task for name in flash message
        task = figures_service.get_by_id(id)
        name = task.name_de if task else str(id)
        
        # Delete using service
        figures_service.delete(id)
        flash(f'Figur {name} erfolgreich gelöscht', 'success')
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in figures.delete: {str(e)}")
        flash('Fehler beim Löschen der Figur', 'error')
        
    return redirect(url_for('figures.index'))
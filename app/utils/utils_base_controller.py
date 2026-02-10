"""
File: app/utils/utils_base_controller.py
Version: 1.0.0
Created: 2025-03-01
Description: Base controller utility class for common route operations
"""

from flask import render_template, redirect, url_for, request, flash
from app.models import db

class BaseController:
    """Base controller class for common route operations."""
    
    def __init__(self, model_class, template_prefix, route_prefix, display_name):
        """
        Initialize the base controller.
        
        Args:
            model_class: SQLAlchemy model class
            template_prefix: Prefix for template paths
            route_prefix: Prefix for route names
            display_name: Display name for flash messages
        """
        self.model_class = model_class
        self.template_prefix = template_prefix
        self.route_prefix = route_prefix
        self.display_name = display_name
    
    def index(self):
        """Display list of all records."""
        try:
            items = self.model_class.query.all()
            return render_template(f'{self.template_prefix}/{self.template_prefix}_main.html', items=items)
        except Exception as e:
            flash(f'Fehler beim Laden der {self.display_name}-Liste: {str(e)}', 'error')
            return render_template(f'{self.template_prefix}/{self.template_prefix}_main.html', items=[])
    
    def create(self):
        """Create new record form handler."""
        if request.method == 'POST':
            try:
                # Extract form data
                form_data = request.form.to_dict()
                
                # Create new record
                record = self.model_class(**form_data)
                db.session.add(record)
                db.session.commit()
                
                flash(f'{self.display_name} erfolgreich erstellt', 'success')
                return redirect(url_for(f'{self.route_prefix}.index'))
            except Exception as e:
                db.session.rollback()
                flash(f'Fehler beim Erstellen des {self.display_name}: {str(e)}', 'error')
                return render_template(f'{self.template_prefix}/{self.template_prefix}_add.html')
                
        return render_template(f'{self.template_prefix}/{self.template_prefix}_add.html')
    
    def edit(self, id):
        """Edit existing record form handler."""
        try:
            record = self.model_class.query.get_or_404(id)
            
            if request.method == 'POST':
                # Extract form data
                form_data = request.form.to_dict()
                
                # Update record
                for key, value in form_data.items():
                    setattr(record, key, value)
                
                db.session.commit()
                
                flash(f'{self.display_name} erfolgreich aktualisiert', 'success')
                return redirect(url_for(f'{self.route_prefix}.index'))
                
            return render_template(f'{self.template_prefix}/{self.template_prefix}_edit.html', item=record)
        except Exception as e:
            db.session.rollback()
            flash(f'Fehler beim Bearbeiten des {self.display_name}: {str(e)}', 'error')
            return redirect(url_for(f'{self.route_prefix}.index'))
    
    def delete(self, id):
        """Delete record handler."""
        try:
            record = self.model_class.query.get_or_404(id)
            db.session.delete(record)
            db.session.commit()
            
            flash(f'{self.display_name} erfolgreich gelöscht', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Fehler beim Löschen des {self.display_name}: {str(e)}', 'error')
            
        return redirect(url_for(f'{self.route_prefix}.index'))
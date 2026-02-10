"""
File: app/routes/bp_rules.py
Version: 1.0.0
Created: 2025-03-02
Description: Blueprint for managing scoring rule sets and rules
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from app.models import db, ScoringRuleSet, ScoringRule
from app.services.services_rules import RuleService
from sqlalchemy.exc import SQLAlchemyError
import logging
import json

# Configure logger
logger = logging.getLogger(__name__)

# Create blueprint
rules_bp = Blueprint('rules', __name__)

# Initialize service
rule_service = RuleService()

@rules_bp.route('/')
def index():
    """Display rule sets overview"""
    try:
        rule_sets = rule_service.get_all_rule_sets()
        return render_template('rules/rules_main.html', rule_sets=rule_sets)
    except SQLAlchemyError as e:
        logger.error(f"Database error in rules.index: {str(e)}")
        flash('Fehler beim Laden der Regelwerke', 'error')
        return render_template('rules/rules_main.html', rule_sets=[])

@rules_bp.route('/create', methods=['GET', 'POST'])
def create_rule_set():
    """Create a new rule set"""
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            description = request.form.get('description')
            
            if not name:
                flash('Name ist erforderlich', 'error')
                return render_template('rules/rule_set_form.html')
            
            rule_set = rule_service.create_rule_set(name, description)
            flash('Regelwerk erfolgreich erstellt', 'success')
            return redirect(url_for('rules.edit_rule_set', rule_set_id=rule_set.rule_set_id))
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error in create_rule_set: {str(e)}")
            flash('Fehler beim Erstellen des Regelwerks', 'error')
            
    return render_template('rules/rule_set_form.html')

@rules_bp.route('/edit/<int:rule_set_id>', methods=['GET', 'POST'])
def edit_rule_set(rule_set_id):
    """Edit a rule set and its rules"""
    try:
        rule_set = rule_service.get_rule_set_by_id(rule_set_id)
        if not rule_set:
            flash('Regelwerk nicht gefunden', 'error')
            return redirect(url_for('rules.index'))
        
        if request.method == 'POST':
            name = request.form.get('name')
            description = request.form.get('description')
            is_active = 'is_active' in request.form
            
            if not name:
                flash('Name ist erforderlich', 'error')
                return render_template('rules/rule_set_form.html', rule_set=rule_set)
            
            rule_service.update_rule_set(rule_set_id, name, description, is_active)
            flash('Regelwerk erfolgreich aktualisiert', 'success')
            
        # Get rule types for the rule editor
        rule_types = rule_service.get_available_rule_types()
        return render_template('rules/rule_set_edit.html', 
                              rule_set=rule_set, 
                              rule_types=rule_types)
            
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in edit_rule_set: {str(e)}")
        flash('Fehler beim Bearbeiten des Regelwerks', 'error')
        return redirect(url_for('rules.index'))

@rules_bp.route('/delete/<int:rule_set_id>', methods=['POST'])
def delete_rule_set(rule_set_id):
    """Delete a rule set"""
    try:
        success = rule_service.delete_rule_set(rule_set_id)
        if success:
            flash('Regelwerk erfolgreich gelöscht', 'success')
        else:
            flash('Regelwerk nicht gefunden', 'error')
            
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in delete_rule_set: {str(e)}")
        flash('Fehler beim Löschen des Regelwerks', 'error')
        
    return redirect(url_for('rules.index'))

@rules_bp.route('/api/rules/<int:rule_set_id>', methods=['GET'])
def get_rules(rule_set_id):
    """API endpoint to get rules for a rule set"""
    try:
        rules = rule_service.get_rules_for_set(rule_set_id)
        
        # Convert rules to a simpler format
        rules_data = []
        for rule in rules:
            try:
                parameters = json.loads(rule.parameters)
            except json.JSONDecodeError:
                parameters = {}
                
            rules_data.append({
                'rule_id': rule.rule_id,
                'rule_type': rule.rule_type,
                'order': rule.order,
                'parameters': parameters
            })
        
        return jsonify({'rules': rules_data})
        
    except Exception as e:
        logger.error(f"Error in get_rules: {str(e)}")
        return jsonify({'error': str(e), 'rules': []}), 500

@rules_bp.route('/api/rules/<int:rule_set_id>', methods=['POST'])
def save_rules(rule_set_id):
    """API endpoint to save rules for a rule set"""
    try:
        if not request.is_json:
            return jsonify({'status': 'error', 'message': 'Request must be JSON'}), 400
            
        data = request.get_json()
        rules_data = data.get('rules', [])
        
        logger.info(f"Received rules data: {rules_data}")
        
        # Update rules in the database
        success = rule_service.update_rules_for_set(rule_set_id, rules_data)
        
        if success:
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to update rules'}), 400
            
    except Exception as e:
        logger.error(f"Error in save_rules: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@rules_bp.route('/duplicate/<int:rule_set_id>', methods=['POST'])
def duplicate_rule_set(rule_set_id):
    """Duplicate an existing rule set"""
    try:
        new_rule_set = rule_service.duplicate_rule_set(rule_set_id)
        if new_rule_set:
            flash(f'Regelwerk dupliziert als "{new_rule_set.name}"', 'success')
            return redirect(url_for('rules.edit_rule_set', rule_set_id=new_rule_set.rule_set_id))
        else:
            flash('Regelwerk nicht gefunden', 'error')
            
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in duplicate_rule_set: {str(e)}")
        flash('Fehler beim Duplizieren des Regelwerks', 'error')
        
    return redirect(url_for('rules.index'))

@rules_bp.route('/activate/<int:rule_set_id>', methods=['POST'])
def activate_rule_set(rule_set_id):
    """Set a rule set as the active one"""
    try:
        success = rule_service.set_active_rule_set(rule_set_id)
        if success:
            flash('Regelwerk aktiviert', 'success')
        else:
            flash('Regelwerk nicht gefunden', 'error')
            
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in activate_rule_set: {str(e)}")
        flash('Fehler beim Aktivieren des Regelwerks', 'error')
        
    return redirect(url_for('rules.index'))

@rules_bp.route('/export/<int:rule_set_id>')
def export_rule_set(rule_set_id):
    """Export a rule set as JSON"""
    try:
        rule_set_data = rule_service.export_rule_set(rule_set_id)
        if rule_set_data:
            return jsonify(rule_set_data)
        else:
            flash('Regelwerk nicht gefunden', 'error')
            return redirect(url_for('rules.index'))
            
    except Exception as e:
        logger.error(f"Error in export_rule_set: {str(e)}")
        flash('Fehler beim Exportieren des Regelwerks', 'error')
        return redirect(url_for('rules.index'))

@rules_bp.route('/import', methods=['POST'])
def import_rule_set():
    """Import a rule set from JSON"""
    try:
        rule_set_data = request.json
        new_rule_set = rule_service.import_rule_set(rule_set_data)
        
        if new_rule_set:
            return jsonify({
                'status': 'success',
                'rule_set_id': new_rule_set.rule_set_id
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Invalid rule set data'
            }), 400
            
    except Exception as e:
        logger.error(f"Error in import_rule_set: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
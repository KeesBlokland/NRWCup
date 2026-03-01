"""
File: app/routes/bp_bugreport.py
Created: 2026-03-01
Description: Simple bug/note report screen for internal use
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.models import db, BugReport
import logging

logger = logging.getLogger(__name__)
bugreport_bp = Blueprint('bugreport', __name__)


@bugreport_bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        description = request.form.get('description', '').strip()
        if not description:
            flash('Bitte eine Beschreibung eingeben', 'error')
            return redirect(url_for('bugreport.index'))
        try:
            report = BugReport(description=description)
            db.session.add(report)
            db.session.commit()
            flash('Notiz gespeichert', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving bug report: {e}")
            flash('Fehler beim Speichern', 'error')
        return redirect(url_for('bugreport.index'))

    reports = BugReport.query.order_by(BugReport.created_at.desc()).all()
    return render_template('bugreport/bugreport_main.html', reports=reports)


@bugreport_bp.route('/toggle/<int:report_id>', methods=['POST'])
def toggle(report_id):
    report = BugReport.query.get_or_404(report_id)
    try:
        report.status = 'done' if report.status == 'new' else 'new'
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling bug report {report_id}: {e}")
        flash('Fehler beim Aktualisieren', 'error')
    return redirect(url_for('bugreport.index'))


@bugreport_bp.route('/delete/<int:report_id>', methods=['POST'])
def delete(report_id):
    report = BugReport.query.get_or_404(report_id)
    try:
        db.session.delete(report)
        db.session.commit()
        flash('Notiz geloscht', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting bug report {report_id}: {e}")
        flash('Fehler beim Loschen', 'error')
    return redirect(url_for('bugreport.index'))

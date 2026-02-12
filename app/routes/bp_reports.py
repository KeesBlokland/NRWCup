"""
File: app/routes/bp_reports.py
Version: 2.3.0
Created: 2025-03-24
Updated: 2025-04-20
Description: Updated reports blueprint with removal of start order functionality
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file, jsonify
from app.models import db, Event, Round, Team, TeamRound, Score, Teilnehmer
from app.services.services_scoring import ScoringService
from app.services.pdf_service import PdfService
import logging
import pandas as pd

# Configure logger
logger = logging.getLogger(__name__)

# Create blueprint
reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/')
def index():
    """Redirect to unified scoring and standings view"""
    return redirect(url_for('scoring.score_list'))

@reports_bp.route('/standings')
def standings():
    """Redirect to unified view or handle API requests"""
    # Check if this is an API request asking for JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('format') == 'json':
        # Keep original JSON response for API calls
        try:
            event_id = request.args.get('event_id', type=int)
            
            if not event_id:
                active_event = Event.query.filter_by(status='Active').first()
                if active_event:
                    event_id = active_event.event_id
                else:
                    # Get most recent event
                    event = Event.query.order_by(Event.event_date.desc()).first()
                    if event:
                        event_id = event.event_id
            
            # Get event and calculate standings
            event = Event.query.get_or_404(event_id)
            standings = ScoringService().calculate_final_standings(event_id)
            
            # Convert to simple dict for JSON
            result = {
                'event': {
                    'id': event.event_id,
                    'name': event.name,
                    'date': event.event_date.isoformat() if event.event_date else None
                },
                'standings': []
            }
            
            for standing in standings:
                result['standings'].append({
                    'rank': standing['rank'],
                    'team_number': standing['team'].team_nummer,
                    'score': standing['score'],
                    'normalized': (standing['score'] / standings[0]['score'] * 1000) if standings[0]['score'] > 0 else 0
                })
                
            return jsonify(result)
        except Exception as e:
            logger.error(f"Error in standings API: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    # For regular browser requests, redirect to the unified view
    return redirect(url_for('scoring.score_list', event_id=request.args.get('event_id')))

@reports_bp.route('/round_details/<int:round_id>')
def round_details(round_id):
    """Display detailed scores for a specific round"""
    try:
        round_obj = Round.query.get_or_404(round_id)
        event = Event.query.get_or_404(round_obj.event_id)
        
        # Get all team rounds for this round
        team_rounds = TeamRound.query.filter_by(round_id=round_id).all()
        
        # Get scores for all teams
        team_scores = {}
        for team_round in team_rounds:
            scores = Score.query.filter_by(team_round_id=team_round.team_round_id).all()
            team_scores[team_round.team_id] = {
                'team_round': team_round,
                'scores': scores
            }
        
        # Calculate normalized scores
        scoring_service = ScoringService()
        normalized_scores = scoring_service.normalize_round_scores(round_id)
        
        # Calculate raw scores for each team
        raw_scores = {}
        for team_id in team_scores:
            team_round = team_scores[team_id]['team_round']
            raw_scores[team_id] = scoring_service.aggregate_judge_scores(team_round.team_round_id)
        
        return render_template('reports/reports_round_details.html',
                              round=round_obj,
                              event=event,
                              team_scores=team_scores,
                              normalized_scores=normalized_scores,
                              raw_scores=raw_scores)  # Add raw_scores to template context
        
    except Exception as e:
        logger.error(f"Error in round details: {str(e)}")
        flash(f'Fehler beim Laden der Durchgangsdetails: {str(e)}', 'error')
        return redirect(url_for('scoring.score_list'))

@reports_bp.route('/export/<report_type>')
def export(report_type):
    """Export reports in various formats"""
    try:
        # Get event ID
        event_id = request.args.get('event_id', type=int)
        
        if not event_id:
            flash('No event selected', 'warning')
            return redirect(url_for('scoring.score_list'))
        
        # Handle different report types
        if report_type == 'results':
            return redirect(url_for('reports.print_results', event_id=event_id))
        elif report_type == 'scoresheet':
            # Get round ID
            round_id = request.args.get('round_id', type=int)
            if not round_id:
                flash('No round selected', 'warning')
                return redirect(url_for('scoring.score_list', event_id=event_id))
            
            return redirect(url_for('reports.print_scoresheet', round_id=round_id))
        
        flash('Unbekannter Berichtstyp', 'warning')
        return redirect(url_for('scoring.score_list'))
        
    except Exception as e:
        logger.error(f"Error in export: {str(e)}")
        flash(f'Error exporting report: {str(e)}', 'error')
        return redirect(url_for('scoring.score_list'))

@reports_bp.route('/print/results/<int:event_id>')
def print_results(event_id):
    """Print results for an event"""
    try:
        pdf_service = PdfService()
        buffer = pdf_service.generate_results_pdf(event_id)
        
        if not buffer:
            flash('Error generating results PDF', 'error')
            return redirect(url_for('scoring.score_list'))
            
        event = Event.query.get(event_id)
        filename = f"results_{event.name.replace(' ', '_')}" if event else f"results_event_{event_id}"
                
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"{filename}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Error printing results: {str(e)}")
        flash(f'Error printing results: {str(e)}', 'error')
        return redirect(url_for('scoring.score_list'))

@reports_bp.route('/print/scoresheet/<int:round_id>')
def print_scoresheet(round_id):
    """Print blank scoresheets for a round"""
    try:
        # Optional team ID filter
        team_id = request.args.get('team_id', type=int)
        
        pdf_service = PdfService()
        buffer = pdf_service.generate_scoresheet_pdf(round_id, team_id)
        
        if not buffer:
            flash('Error generating scoresheet PDF', 'error')
            return redirect(url_for('scoring.score_list'))
        
        round_obj = Round.query.get(round_id)
        if round_obj:
            filename = f"scoresheet_round_{round_obj.round_number}"
        else:
            filename = f"scoresheet_round_{round_id}"
            
        if team_id:
            team = Team.query.get(team_id)
            if team:
                filename += f"_team_{team.team_nummer}"
                
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"{filename}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Error printing scoresheet: {str(e)}")
        flash(f'Error printing scoresheet: {str(e)}', 'error')
        return redirect(url_for('scoring.score_list'))

@reports_bp.route('/email_results_recipients/<int:event_id>', methods=['POST'])
def email_results_recipients(event_id):
    """Return list of Wettkampfleitung recipients for selection"""
    try:
        recipients = []
        for t in Teilnehmer.query.filter(
            Teilnehmer.is_wettkampfleitung == True,
            Teilnehmer.email.isnot(None),
            Teilnehmer.email != ''
        ).all():
            recipients.append({'email': t.email, 'name': t.name, 'role': 'Wettkampfleitung'})
        return jsonify({'success': True, 'recipients': recipients})
    except Exception as e:
        logger.error(f"Error getting recipients: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@reports_bp.route('/email_results/<int:event_id>', methods=['POST'])
def email_results(event_id):
    """Email results to selected recipients"""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from app.config import Config

        data = request.get_json()
        selected_emails = data.get('recipients', []) if data else []

        if not selected_emails:
            return jsonify({'success': False, 'message': 'Keine Empfänger ausgewählt'})

        event = Event.query.get_or_404(event_id)

        # Get standings for email content
        scoring_service = ScoringService()
        standings = scoring_service.calculate_final_standings(event_id)
        rounds = Round.query.filter_by(event_id=event_id).order_by(Round.round_number).all()

        html_content = render_template('reports/results_email.html',
                                     event=event,
                                     standings=standings,
                                     rounds=rounds)

        smtp_server = Config.MAIL_SERVER
        smtp_port = Config.MAIL_PORT
        email_user = Config.MAIL_USERNAME
        email_password = Config.MAIL_PASSWORD

        msg = MIMEMultipart()
        msg['From'] = email_user
        msg['To'] = ', '.join(selected_emails)
        msg['Subject'] = f"Ergebnisse - {event.name}"
        msg.attach(MIMEText(html_content, 'html'))

        import ssl
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(email_user, email_password)
            server.send_message(msg)

        return jsonify({'success': True, 'message': f'Ergebnisse an {len(selected_emails)} Empfänger gesendet'})

    except Exception as e:
        logger.error(f"Email error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@reports_bp.route('/export_excel/<int:event_id>')
def export_excel(event_id):
    try:
        import pandas as pd
        import io
        from datetime import datetime
        
        # Get event and data
        event = Event.query.get_or_404(event_id)
        scoring_service = ScoringService()
        standings = scoring_service.calculate_final_standings(event_id)
        rounds = Round.query.filter_by(event_id=event_id).order_by(Round.round_number).all()
        
        if not standings:
            flash('Keine Ergebnisse zum Exportieren gefunden', 'warning')
            return redirect(url_for('scoring.score_list'))
        
        # Prepare data for Excel
        data = []
        for standing in standings:
            row = {
                'Rang': standing['rank'],
                'Team': standing['team'].team_nummer,
                'Schlepper_Pilot': standing['team'].schlepper_pilot.name if standing['team'].schlepper_pilot else '',
                'Segler_Pilot': standing['team'].segler_pilot.name if standing['team'].segler_pilot else '',
            }
            
            # Add round scores
            for i, round_obj in enumerate(rounds):
                col_name = f'Durchgang_{round_obj.round_number}'
                if i < len(standing['round_scores']):
                    score = standing['round_scores'][i]
                    if i in standing.get('dropped_indices', []):
                        row[col_name] = f"{score:.1f} (gestrichen)"
                    else:
                        row[col_name] = f"{score:.1f}"
                else:
                    row[col_name] = ''
            
            # Add totals
            row['Gesamt'] = f"{standing['score']:.1f}"
            if standings[0]['score'] > 0:
                normalized = (standing['score'] / standings[0]['score']) * 1000
                row['Normalisiert'] = f"{normalized:.1f}"
            else:
                row['Normalisiert'] = "0.0"
            
            data.append(row)
        
        # Create Excel file
        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Ergebnisse')
            
            # Add this section for column widths
            workbook = writer.book
            worksheet = writer.sheets['Ergebnisse']
            
            # Set all columns to 1.75 inches (≈13 character units)
            for column in worksheet.columns:
                column_letter = column[0].column_letter
                worksheet.column_dimensions[column_letter].width = 20

        output.seek(0)
        
        # Generate filename
        event_name = event.name.replace(' ', '_').replace('/', '-')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        filename = f"Ergebnisse_{event_name}_{timestamp}.xlsx"
        
        return send_file(
            output,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True
        )
        
    except Exception as e:
        logger.error(f"Excel export error: {str(e)}")
        flash(f'Fehler beim Excel-Export: {str(e)}', 'error')
        return redirect(url_for('scoring.score_list'))


@reports_bp.route('/export_excel_debug/<int:event_id>')
def export_excel_debug(event_id):
    try:
        import pandas as pd
        import io
        from datetime import datetime
        
        # Get event
        event = Event.query.get_or_404(event_id)
        return f"Event found: {event.name}"
        
    except Exception as e:
        return f"Error: {str(e)}"
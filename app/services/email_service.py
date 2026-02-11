"""
File: app/services/email_service.py
Version: 1.0.0
Created: 2025-05-05
Description: Email service for sending competition scores and notifications
"""

import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.models import db, Score, Teilnehmer, Team, TeamRound, Round, TaskType, ScoreValue
from app.config import Config
import logging

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails"""
    
    @staticmethod
    def send_score_email(score_id):
        """
        Send an email with score details to team members
        
        Args:
            score_id: ID of the locked score to send
            
        Returns:
            dict with status and message
        """
        try:
            # Get the score
            score = Score.query.get(score_id)
            if not score:
                return {'success': False, 'message': 'Bewertung nicht gefunden'}
            
            # Check if the score is locked
            if not score.locked:
                return {'success': False, 'message': 'Die Bewertung muss gesperrt sein, bevor sie gesendet werden kann'}
            
            # Get team round, team, and members
            team_round = TeamRound.query.get(score.team_round_id)
            if not team_round:
                return {'success': False, 'message': 'Team-Runde nicht gefunden'}
                
            team = Team.query.get(team_round.team_id)
            if not team:
                return {'success': False, 'message': 'Team nicht gefunden'}
                
            schlepper_pilot = Teilnehmer.query.get(team.schlepper_pilot_id) if team.schlepper_pilot_id else None
            segler_pilot = Teilnehmer.query.get(team.segler_pilot_id) if team.segler_pilot_id else None
            
            # Get judge
            judge = Teilnehmer.query.get(score.judge_id)
            
            # Collect email addresses
            email_addresses = []
            if schlepper_pilot and schlepper_pilot.email:
                email_addresses.append(schlepper_pilot.email)
            if segler_pilot and segler_pilot.email:
                email_addresses.append(segler_pilot.email)
                
            if not email_addresses:
                return {'success': False, 'message': 'Keine E-Mail-Adressen für die Teammitglieder gefunden'}
            
            # Get round info
            round_obj = Round.query.get(team_round.round_id)
            
            # Format email content
            email_content = EmailService._format_score_email(score, team, round_obj, judge)
            
            # Send the email
            result = EmailService._send_email(
                recipients=email_addresses,
                subject=f"NRW Cup {datetime.now().year} - Bewertung Team {team.team_nummer}, Durchgang {round_obj.round_number}",
                html_content=email_content
            )
            
            if result['success']:
                return {'success': True, 'message': f'Bewertung erfolgreich an {", ".join(email_addresses)} gesendet'}
            else:
                return {'success': False, 'message': result['message']}
                
        except Exception as e:
            logger.error(f"Error processing email score: {str(e)}")
            return {'success': False, 'message': f'Fehler beim Verarbeiten der Bewertung: {str(e)}'}
    
    @staticmethod
    def _format_score_email(score, team, round_obj, judge):
        """Format the email HTML content with score details"""
        # Generate the score summary
        score_values = ScoreValue.query.filter_by(score_id=score.score_id).all()
        score_details = []
        total_points = 0
        
        for score_value in score_values:
            task_type = TaskType.query.get(score_value.task_type_id)
            if not task_type:
                continue
                
            value = score_value.value
            k_factor = task_type.k_factor or 1
            
            # Special handling for Seglerzeit
            if task_type.code == 'SEGZEIT' or (task_type.name_de and 'Flugzeit' in task_type.name_de):
                target_time = 200
                max_points = 300
                penalty_factor = 3
                
                time_diff = abs(target_time - value)
                points = max(0, max_points - (time_diff * penalty_factor))
            else:
                points = value * k_factor
                
            score_details.append({
                'name': task_type.name_de,
                'value': value,
                'points': points
            })
            total_points += points
        
        # Create HTML email content
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h2>NRW Cup {datetime.now().year} - Bewertungsbogen</h2>
            <p><strong>Team:</strong> {team.team_nummer}</p>
            <p><strong>Durchgang:</strong> {round_obj.round_number}</p>
            <p><strong>Punktrichter:</strong> {judge.name if judge else '-'}</p>
            <p><strong>Datum:</strong> {score.locked_at.strftime('%d.%m.%Y %H:%M') if score.locked_at else '-'}</p>
            
            <table>
                <tr>
                    <th>Figur</th>
                    <th>Wert</th>
                    <th>Punkte</th>
                </tr>
        """
        
        for detail in score_details:
            html += f"""
                <tr>
                    <td>{detail['name']}</td>
                    <td>{detail['value']}</td>
                    <td>{detail['points']}</td>
                </tr>
            """
            
        html += f"""
                <tr>
                    <td colspan="2"><strong>Gesamtpunktzahl</strong></td>
                    <td><strong>{total_points}</strong></td>
                </tr>
            </table>
            
            <p>Anmerkungen: {score.notes}</p>
            <p>Diese Bewertung wurde am {score.locked_at.strftime('%d.%m.%Y %H:%M') if score.locked_at else '-'} gesperrt.</p>
        </body>
        </html>
        """
        
        return html
    
    @staticmethod
    def _send_email(recipients, subject, html_content, text_content=None):
        """
        Send an email with the configured SMTP settings
        
        Args:
            recipients: List of email addresses
            subject: Email subject
            html_content: HTML content of the email
            text_content: Optional plain text content
            
        Returns:
            dict with success status and message
        """
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = Config.MAIL_DEFAULT_SENDER
            msg['To'] = ', '.join(recipients)
            
            # Add text part if provided
            if text_content:
                part1 = MIMEText(text_content, 'plain')
                msg.attach(part1)
            
            # Add HTML part
            part2 = MIMEText(html_content, 'html')
            msg.attach(part2)
            
            # Connect to SMTP server
            if Config.MAIL_USE_SSL:
                server = smtplib.SMTP_SSL(Config.MAIL_SERVER, Config.MAIL_PORT)
            else:
                server = smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT)
                
                if Config.MAIL_USE_TLS:
                    server.starttls()
            
            # Login if credentials are provided
            if Config.MAIL_USERNAME and Config.MAIL_PASSWORD:
                server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            
            # Send email
            server.sendmail(Config.MAIL_DEFAULT_SENDER, recipients, msg.as_string())
            server.quit()
            
            return {'success': True, 'message': 'Email sent successfully'}
            
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return {'success': False, 'message': f'Fehler beim Senden der E-Mail: {str(e)}'}
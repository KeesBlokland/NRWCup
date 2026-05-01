"""
File: app/services/pdf_service.py
Version: 1.3.0
Created: 2025-03-01
Last Modified: 2025-04-21
Description: Service for PDF generation with strikethrough for dropped rounds
"""

import io
from datetime import datetime
from app.models import Event, Round, Team, TeamRound, TaskType
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import logging

logger = logging.getLogger(__name__)

class PdfService:
    """Service for PDF generation"""
    
    def generate_scoresheet_pdf(self, round_id, team_id=None):
        """Generate printable scoresheets for a round or specific team"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []
        
        # Add title and header
        styles = getSampleStyleSheet()
        # Fetch round and event early so we can use event.name in the title
        _round_early = Round.query.get(round_id)
        _event_early = Event.query.get(_round_early.event_id) if _round_early else None
        _title = f"{_event_early.name} - Bewertungsbogen" if _event_early else f"NRW Cup {datetime.now().year} - Bewertungsbogen"
        elements.append(Paragraph(_title, styles['Title']))
        
        # Get teams for this round
        query = TeamRound.query.filter_by(round_id=round_id)
        if team_id:
            query = query.filter_by(team_id=team_id)
        
        team_rounds = query.all()
        
        # Get scoring figures
        figures = TaskType.query.filter_by(is_active=True).order_by(TaskType.sort_order).all()
        
        # Get round info
        round_obj = Round.query.get(round_id)
        if round_obj:
            elements.append(Paragraph(f"Durchgang: {round_obj.round_number}", styles['Heading2']))
            _date_str = _event_early.event_date.strftime('%d.%m.%Y') if _event_early and _event_early.event_date else datetime.now().strftime('%d.%m.%Y')
            elements.append(Paragraph(f"Datum: {_date_str}", styles['Normal']))
            elements.append(Spacer(1, 12))  # Add 12 points (equivalent to 1 line) of space
        
        # Create scoresheets
        for team_round in team_rounds:
            team = Team.query.get(team_round.team_id)
            if not team:
                continue
                
            # Team header
            elements.append(Paragraph(f"Team {team.team_nummer}", styles['Heading3']))
            
            if team.schlepper_pilot:
                elements.append(Paragraph(f"Schlepperpilot: {team.schlepper_pilot.name}", styles['Normal']))
            if team.segler_pilot:
                elements.append(Paragraph(f"Seglerpilot: {team.segler_pilot.name}", styles['Normal']))
                
            elements.append(Spacer(1, 12))
            
            # Score table
            data = [['Aufgabe', 'Punktzahl', 'Anmerkungen']]
            for figure in figures:
                data.append([figure.name_de, '', ''])
                
            # Judge signature
            data.append(['', '', ''])
            data.append(['Name des Richters:', '', ''])
            data.append(['Unterschrift:', '', ''])
            
            table = Table(data, colWidths=[200, 100, 200])
            table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ]))
            
            elements.append(table)
            elements.append(PageBreak())
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer
        
    def generate_results_pdf(self, event_id):
        """Generate results PDF for an event in landscape orientation"""
        buffer = io.BytesIO()
        
        # Use landscape orientation (A4 sideways)
        doc = SimpleDocTemplate(buffer, 
                                pagesize=landscape(A4),  # Use landscape orientation
                                rightMargin=30, 
                                leftMargin=30, 
                                topMargin=30, 
                                bottomMargin=30)
        elements = []
        
        # Add title and header
        styles = getSampleStyleSheet()
        
        # Create strikethrough style for dropped rounds
        strike_style = ParagraphStyle('strikethrough', 
                                    parent=styles['Normal'],
                                    textColor=colors.gray,
                                    strikethrough=1)
        
        # Get event info
        event = Event.query.get(event_id)
        if not event:
            return None

        # Title + Date
        event_year = event.event_date.year if event.event_date else datetime.now().year
        elements.append(Paragraph(f"{event.name} - Ergebnisse", styles['Heading2']))
        elements.append(Paragraph(event.event_date.strftime('%d.%m.%Y'), styles['Normal']))

        # Get scoring service and standings - we'll use this data directly 
        from app.services.services_scoring import ScoringService
        scoring_service = ScoringService()
        standings, standings_rounds = scoring_service.calculate_final_standings(event_id)

        # Table header
        header = ['Rang', 'Team', 'Piloten']
        for round_obj in standings_rounds:
            header.append(f"D {round_obj.round_number}")
        header.append('Endstand')
        
        data = [header]
        
        # Add team rows - USE THE EXISTING STANDINGS DATA
        for standing in standings:
            team = standing['team']
            
            # Get pilot names
            pilots = []
            if hasattr(team, 'schlepper_pilot') and team.schlepper_pilot:
                pilots.append(f"{team.schlepper_pilot.name}")
            if hasattr(team, 'segler_pilot') and team.segler_pilot:
                pilots.append(f"{team.segler_pilot.name}")
            pilots_str = "\n".join(pilots)
            
            row = [
                standing['rank'],
                f"Team {team.team_nummer}",
                pilots_str
            ]
            
            # Add round scores using the existing data
            if 'round_scores' in standing and 'dropped_indices' in standing:
                round_scores = standing['round_scores']
                dropped_indices = standing['dropped_indices']
                
                # Add scores for each round, using strikethrough for dropped rounds
                for i, score in enumerate(round_scores):
                    score_text = f"{score:.1f}"
                    if i in dropped_indices:
                        # Use the strikethrough style for dropped rounds
                        row.append(Paragraph(f"<para align='center'><strike>{score_text}</strike></para>", strike_style))
                    else:
                        row.append(score_text)

            # Add empty cells if we have fewer scores than rounds
            while len(row) < len(header) - 1:  # -1 for Endstand column
                row.append("-")

            # Endstand = sum of Promille-Punkte for best rounds
            row.append(f"{standing['score']:.1f}")
            
            data.append(row)
            
        # Create table with appropriate column widths
        # Adjust widths for landscape orientation
        col_count = len(header)
        rank_width = 30
        team_width = 60
        pilot_width = 120
        score_width = (doc.width - rank_width - team_width - pilot_width) / (col_count - 3)
        
        colWidths = [rank_width, team_width, pilot_width] + ([score_width] * (col_count - 3))
        
        table = Table(data, colWidths=colWidths)
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (3, 0), (-1, -1), 'CENTER'),  # Center all score columns
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),  # Smaller font to fit more content
            # ADDED: Highlight the Final and Normalized columns
            ('BACKGROUND', (-2, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (-2, 0), (-1, 0), colors.white),
        ]))
        
        elements.append(table)

        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer

    def generate_start_order_pdf(self, round_id):
        """Generate start order PDF for a round"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []

        styles = getSampleStyleSheet()

        round_obj = Round.query.get(round_id)
        if not round_obj:
            return None

        event = Event.query.get(round_obj.event_id)
        event_year = event.event_date.year if event and event.event_date else datetime.now().year

        elements.append(Paragraph(f"NRW Cup {event_year} - Startfolge Durchgang {round_obj.round_number}", styles['Heading2']))
        if event and event.event_date:
            elements.append(Paragraph(event.event_date.strftime('%d.%m.%Y'), styles['Normal']))
        elements.append(Spacer(1, 20))

        team_rounds = TeamRound.query.filter_by(round_id=round_id)\
            .order_by(TeamRound.start_order).all()

        data = [['Start Nr.', 'Team', 'Schlepper', 'Segler']]
        for tr in team_rounds:
            team = Team.query.get(tr.team_id)
            if not team:
                continue
            data.append([
                tr.start_order,
                f"Team {team.team_nummer}",
                team.schlepper_pilot.name if team.schlepper_pilot else '-',
                team.segler_pilot.name if team.segler_pilot else '-'
            ])

        table = Table(data, colWidths=[70, 80, 180, 180])
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
        ]))

        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        return buffer
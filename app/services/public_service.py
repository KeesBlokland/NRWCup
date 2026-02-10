"""
File: app/services/public_service.py
Version: 1.0.1
Created: 2025-03-01
Last Modified: 2025-03-24
Description: Service for generating public content
"""

from flask import render_template, current_app
from app.models import Event, Round
from app.services.services_scoring import ScoringService
from datetime import datetime
import os

class PublicService:
    """Service for generating public content"""
    
    def generate_public_results(self, event_id):
        """Generate public results HTML file"""
        event = Event.query.get_or_404(event_id)
        
        # Check if event is published
        if event.status != 'Published':
            return False
        
        # Get scoring service
        scoring_service = ScoringService()
        standings = scoring_service.calculate_final_standings(event_id)
        
        # Get rounds for this event
        rounds = Round.query.filter_by(event_id=event_id).order_by(Round.round_number).all()
        
        # Generate HTML content
        with current_app.app_context():
            html_content = render_template('public/results.html', 
                                         event=event,
                                         rounds=rounds,
                                         standings=standings,
                                         generated_at=datetime.now())
        
        # Write to file in public directory
        public_dir = os.path.join(current_app.root_path, 'public')
        os.makedirs(public_dir, exist_ok=True)
        
        with open(os.path.join(public_dir, f'results_{event_id}.html'), 'w') as f:
            f.write(html_content)
        
        return True
"""
File: utils/generate_scores.py
Version: 1.1.0
Created: 2025-03-01
Description: Utility script to generate random scores for testing with figure variants
"""

import os
import sys
import random
from datetime import datetime

# Add project root to path to allow imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

from app.models import db, Team, Round, TeamRound, Teilnehmer, Score, ScoreValue, TaskType
from flask import Flask
from sqlalchemy import and_

def create_app():
    """Initialize Flask app with database"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(project_root, 'instance', 'NRWCup2025.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app

def generate_gaussian_score(mean=7.0, std_dev=1.5, min_val=0, max_val=10):
    """Generate a score using Gaussian distribution, centered around 7 (±3)"""
    score = random.gauss(mean, std_dev)
    return max(min_val, min(max_val, round(score * 2) / 2))  # Round to nearest 0.5

def generate_landing_score():
    """Generate score for landing zones (0, 5, 10, 20, 30)"""
    return random.choice([0, 5, 10, 20, 30])

def handle_mutually_exclusive_figures(task_types):
    """Handle figures that are mutually exclusive (only one gets a value, others are 0)
       Returns dictionary with chosen variants that should be consistent across judges"""
    
    chosen_variants = {}
    
    # Group 1: Platzrunde variants
    platzrunde_variants = [task for task in task_types if 
                          task.name_de and 'Platzrunde' in task.name_de]
    if platzrunde_variants:
        # Choose one random variant to score
        chosen_variants['platzrunde'] = random.choice(platzrunde_variants).type_id
    
    # Group 2: Platzüberflug variants
    platzu_variants = [task for task in task_types if 
                       task.name_de and 'Platz' in task.name_de and 'berflug' in task.name_de]
    if platzu_variants:
        # Choose one random variant to score
        chosen_variants['platzu'] = random.choice(platzu_variants).type_id
    
    return chosen_variants

def clear_all_scores():
    """Clear all scores from the database"""
    print("Clearing all scores from the database")
    
    try:
        # Delete all score values first (foreign key constraint)
        ScoreValue.query.delete()
        
        # Then delete all scores
        Score.query.delete()
        
        # Commit the changes
        db.session.commit()
        print("All scores cleared")
    except Exception as e:
        db.session.rollback()
        print(f"Error clearing scores: {str(e)}")
        raise

def generate_scores_for_round(round_id):
    """Generate scores for all teams in the specified round"""
    # Special case: if round_id is 0, clear all scores
    if round_id == 0:
        clear_all_scores()
        return
    
    print(f"Generating scores for round {round_id}")
    
    # Get active teams
    teams = Team.query.filter_by(status='active').all()
    if not teams:
        print("No active teams found")
        return
    
    # Get the round
    round_obj = Round.query.get(round_id)
    if not round_obj:
        print(f"Round {round_id} not found")
        return
    
    # Get judges
    judges = Teilnehmer.query.filter_by(is_punktwerter=True).all()
    if not judges:
        print("No judges found")
        return
    
    # Get active task types
    task_types = TaskType.query.filter_by(is_active=True).order_by(TaskType.sort_order).all()
    if not task_types:
        print("No active task types found")
        return
    
    # Get or create TeamRounds for each team
    team_rounds = []
    for team in teams:
        team_round = TeamRound.query.filter_by(
            round_id=round_id,
            team_id=team.team_id
        ).first()
        
        if not team_round:
            # Create new team round
            team_round = TeamRound(
                round_id=round_id,
                team_id=team.team_id,
                status='Pending',
                start_order=team.team_nummer
            )
            db.session.add(team_round)
            db.session.flush()
        
        team_rounds.append(team_round)
    
    # First, clear existing scores for this round
    for team_round in team_rounds:
        existing_scores = Score.query.filter_by(team_round_id=team_round.team_round_id).all()
        for score in existing_scores:
            # Delete score values first
            ScoreValue.query.filter_by(score_id=score.score_id).delete()
            # Then delete the score itself
            db.session.delete(score)
    
    # Commit to ensure all deletions are processed
    db.session.commit()
    
    # Choose figure variants for the team (consistent across judges)
    # This needs to be done for each team, not each judge
    scores_generated = 0
    
    # For each team, decide which figure variants to use (applies to all judges)
    for team_round in team_rounds:
        # Select which variant each team uses (same for all judges)
        chosen_variants = handle_mutually_exclusive_figures(task_types)
        
        # Generate scores for each judge for this team
        for judge in judges:
            # Create new score
            score = Score(
                team_round_id=team_round.team_round_id,
                judge_id=judge.teilnehmer_id,
                entered_at=datetime.utcnow(),
                notes=f"Auto-generated score for testing"
            )
            db.session.add(score)
            db.session.flush()
            
            # Prepare values for all task types
            task_values = {}
            for task_type in task_types:
                if task_type.code in ['LANDGM', 'LANS', 'SEILZ']:
                    # Landing zones have specific values
                    task_values[task_type.type_id] = generate_landing_score()
                elif task_type.code == 'SEGZEIT':
                    # Glider time (170-230 seconds)
                    task_values[task_type.type_id] = random.randint(170, 230)
                else:
                    # For Platzrunde variants
                    if 'platzrunde' in chosen_variants and task_type.name_de and 'Platzrunde' in task_type.name_de:
                        if task_type.type_id == chosen_variants['platzrunde']:
                            task_values[task_type.type_id] = generate_gaussian_score()
                        else:
                            task_values[task_type.type_id] = 0.0
                    # For Platzüberflug variants
                    elif 'platzu' in chosen_variants and task_type.name_de and 'Platz' in task_type.name_de and 'berflug' in task_type.name_de:
                        if task_type.type_id == chosen_variants['platzu']:
                            task_values[task_type.type_id] = generate_gaussian_score()
                        else:
                            task_values[task_type.type_id] = 0.0
                    else:
                        # Standard scores centered around 7
                        task_values[task_type.type_id] = generate_gaussian_score()
                    
                    # If task has max_value set, respect it
                    if task_type.type_id in task_values and task_type.max_value is not None:
                        task_values[task_type.type_id] = min(task_values[task_type.type_id], task_type.max_value)
            
            # Add score values to database
            for task_type in task_types:
                if task_type.type_id in task_values:
                    score_value = ScoreValue(
                        score_id=score.score_id,
                        task_type_id=task_type.type_id,
                        value=task_values[task_type.type_id]
                    )
                    db.session.add(score_value)
            
            scores_generated += 1
    
    # Commit all changes
    db.session.commit()
    print(f"Generated {scores_generated} scores for {len(team_rounds)} teams and {len(judges)} judges")

def print_usage():
    print("Usage: python generate_scores.py <round_id>")
    print("  round_id: ID of the round to generate scores for")
    print("  Use round_id=0 to clear all scores")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print_usage()
        sys.exit(1)
    
    try:
        round_id = int(sys.argv[1])
    except ValueError:
        print("Error: round_id must be an integer")
        print_usage()
        sys.exit(1)
    
    app = create_app()
    with app.app_context():
        generate_scores_for_round(round_id)
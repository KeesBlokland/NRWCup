# File: recalculate_scores.py
# Run this script to recalculate all team scores with the fixed aggregation logic

from app import create_app
from app.models import db, TeamRound
from app.services.services_scoring import ScoringService
import logging

def recalculate_all_scores():
    """Recalculate all team scores using the corrected aggregation logic"""
    
    app = create_app()
    with app.app_context():
        scoring_service = ScoringService()
        
        # Get all team rounds that have scores
        team_rounds = TeamRound.query.all()
        
        updated_count = 0
        
        for team_round in team_rounds:
            try:
                # Recalculate raw score using fixed aggregation
                old_raw_score = team_round.raw_score
                new_raw_score = scoring_service.aggregate_judge_scores(team_round.team_round_id)
                
                if new_raw_score is not None:
                    team_round.raw_score = new_raw_score
                    updated_count += 1
                    
                    # Log significant changes
                    if old_raw_score and abs(new_raw_score - old_raw_score) > 50:
                        print(f"Team Round {team_round.team_round_id}: {old_raw_score:.1f} -> {new_raw_score:.1f}")
                        
            except Exception as e:
                print(f"Error recalculating team round {team_round.team_round_id}: {e}")
        
        # Recalculate normalized scores for all rounds
        rounds_processed = set()
        for team_round in team_rounds:
            if team_round.round_id not in rounds_processed:
                try:
                    # Recalculate normalized scores for this round
                    normalized_scores = scoring_service.normalize_round_scores(team_round.round_id)
                    
                    # Update team rounds with new normalized scores
                    round_team_rounds = TeamRound.query.filter_by(round_id=team_round.round_id).all()
                    for tr in round_team_rounds:
                        if tr.team_id in normalized_scores:
                            tr.normalized_score = normalized_scores[tr.team_id]
                    
                    rounds_processed.add(team_round.round_id)
                    
                except Exception as e:
                    print(f"Error normalizing round {team_round.round_id}: {e}")
        
        # Commit all changes
        db.session.commit()
        
        print(f"Recalculated {updated_count} team scores")
        print(f"Processed {len(rounds_processed)} rounds")
        print("All scores have been updated with the corrected aggregation logic")

if __name__ == "__main__":
    recalculate_all_scores()
    
# app/routes/bp_public.py
public_bp = Blueprint('public', __name__, url_prefix='/public')

@public_bp.route('/')
def index():
    """Public home page"""
    # Show only published events
    events = Event.query.filter_by(status='Published').order_by(Event.event_date.desc()).all()
    return render_template('public/index.html', events=events)

@public_bp.route('/results/<int:event_id>')
def results(event_id):
    """Display public results for an event"""
    event = Event.query.get_or_404(event_id)
    
    # Check if results are published
    if event.status != 'Published':
        return render_template('public/not_available.html')
    
    # Get scoring service
    scoring_service = ScoringService()
    standings = scoring_service.calculate_final_standings(event_id)
    
    # Get rounds for this event
    rounds = Round.query.filter_by(event_id=event_id).order_by(Round.round_number).all()
    
    return render_template('public/results.html', 
                          event=event,
                          rounds=rounds,
                          standings=standings)
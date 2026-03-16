# File: app/routes/bp_scoring_results.py
"""
Routes for team results display, scoresheet PDF, email, and admin recalculate.
Registers onto the shared scoring_bp blueprint (prefix /scoring).
Split from bp_scoring.py to keep file sizes manageable.
"""

from flask import render_template, request, redirect, url_for, flash, jsonify, make_response
from app.models import db, Score, TaskType, TeamRound, Teilnehmer, Team, Round, Event, ScoreValue
from app.services.services_scoring import ScoringService
from app.utils.scoring_constants import get_scoring_constants
from app.utils.auth import admin_required
from app.config import Config

import logging

from app.routes.bp_scoring import scoring_bp, scoring_service

logger = logging.getLogger(__name__)


@scoring_bp.route('/team_results')
def team_results():
    """Display team results - simple version using existing logic"""
    try:
        event_id = request.args.get('event_id', type=int)
        round_id = request.args.get('round_id', type=int)
        team_id = request.args.get('team_id', type=int)

        MESSWERTUNG_CODES, ALWAYS_MANDATORY, EXCLUSIVE_GROUPS = get_scoring_constants()

        events = Event.query.filter_by(is_hidden=False).order_by(Event.event_date.desc()).all()

        if not event_id and events:
            event_id = events[0].event_id
        event = Event.query.get(event_id) if event_id else None

        rounds = Round.query.filter_by(event_id=event_id).order_by(Round.round_number).all() if event_id else []

        if not round_id and rounds:
            round_id = rounds[0].round_id

        teams = []
        if round_id:
            team_ids_with_scores = db.session.query(TeamRound.team_id)\
                .join(Score, TeamRound.team_round_id == Score.team_round_id)\
                .filter(TeamRound.round_id == round_id)\
                .distinct().all()

            if team_ids_with_scores:
                team_ids = [t[0] for t in team_ids_with_scores]
                teams = Team.query.filter(Team.team_id.in_(team_ids))\
                    .filter(Team.status == 'active')\
                    .order_by(Team.team_nummer).all()

        team_data = None
        unchosen_codes = set()
        if team_id and round_id:
            team = Team.query.get(team_id)
            if team:
                figures = TaskType.query.filter_by(is_active=True).order_by(TaskType.sort_order).all()
                team_round = TeamRound.query.filter_by(team_id=team_id, round_id=round_id).first()
                if team_round:
                    scores = Score.query.options(
                        db.joinedload(Score.values).joinedload(ScoreValue.task_type),
                        db.joinedload(Score.judge)
                    ).filter_by(team_round_id=team_round.team_round_id).all()

                    type_id_to_code = {f.type_id: f.code for f in figures}
                    for group in EXCLUSIVE_GROUPS:
                        group_type_ids = {f.type_id for f in figures if f.code in group}
                        chosen_type_id = next(
                            (sv.task_type_id for s in scores
                             for sv in s.values
                             if sv.task_type_id in group_type_ids
                             and sv.value and sv.value > 0),
                            None
                        )
                        if chosen_type_id:
                            chosen_code = type_id_to_code[chosen_type_id]
                            unchosen_codes.update(c for c in group if c != chosen_code)
                        else:
                            unchosen_codes.update(group)

                    team_data = {
                        'team': team,
                        'figures': figures,
                        'scores': scores,
                        'team_round': team_round
                    }

        wkl_users = Teilnehmer.query.filter_by(is_wettkampfleitung=True).order_by(Teilnehmer.name).all()

        return render_template('scoring/team_results.html',
                               events=events,
                               event=event,
                               rounds=rounds,
                               teams=teams,
                               team_data=team_data,
                               unchosen_codes=unchosen_codes,
                               wkl_users=wkl_users,
                               selected_event_id=event_id,
                               selected_round_id=round_id,
                               selected_team_id=team_id)

    except Exception as e:
        logger.error(f"Error in team_results: {str(e)}")
        return render_template('scoring/team_results.html')


@scoring_bp.route('/email_team_results', methods=['POST'])
def email_team_results():
    """Email team results as HTML to pilots"""
    try:
        import smtplib
        import ssl
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        data = request.get_json()
        team_id = data.get('team_id')
        round_id = data.get('round_id')
        event_id = data.get('event_id')

        team = Team.query.get(team_id)
        if not team:
            return jsonify({'success': False, 'message': 'Team not found'})

        round_obj = Round.query.get(round_id)
        event = Event.query.get(event_id)

        team_round = TeamRound.query.filter_by(team_id=team_id, round_id=round_id).first()
        if not team_round:
            return jsonify({'success': False, 'message': 'No scores found'})

        scores = Score.query.options(
            db.joinedload(Score.values).joinedload(ScoreValue.task_type),
            db.joinedload(Score.judge)
        ).filter_by(team_round_id=team_round.team_round_id).all()

        figures = TaskType.query.filter_by(is_active=True).order_by(TaskType.sort_order).all()

        team_data = {
            'team': team,
            'figures': figures,
            'scores': scores,
            'team_round': team_round,
        }

        html_content = render_template('scoring/team_scoresheet_pdf.html',
                                       team_data=team_data,
                                       round_obj=round_obj,
                                       event=event,
                                       is_email=True)

        provided = [r.strip() for r in (data.get('recipients') or []) if r and r.strip()]
        if provided:
            recipients = provided
            admin_fallback = False
        else:
            recipients = []
            if team.schlepper_pilot and team.schlepper_pilot.email:
                recipients.append(team.schlepper_pilot.email)
            if team.segler_pilot and team.segler_pilot.email:
                recipients.append(team.segler_pilot.email)
            admin_fallback = not recipients
            if admin_fallback:
                if not Config.ADMIN_EMAIL:
                    return jsonify({'success': False, 'message': 'Keine Email-Adressen und keine Admin-Email konfiguriert'})
                recipients = [Config.ADMIN_EMAIL]

        msg = MIMEMultipart()
        msg['From'] = Config.MAIL_USERNAME
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = f"Team {team.team_nummer} Ergebnisse - {event.name if event else 'NRW Cup'}"
        msg.attach(MIMEText(html_content, 'html'))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(Config.MAIL_SERVER, Config.MAIL_PORT, context=context) as server:
            server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            server.send_message(msg)

        if admin_fallback:
            return jsonify({'success': True, 'message': f'Keine Team-Adressen -- gesendet an Admin: {Config.ADMIN_EMAIL}'})
        return jsonify({'success': True, 'message': f'Email gesendet an: {", ".join(recipients)}'})

    except Exception as e:
        logger.error(f"Email error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})


@scoring_bp.route('/admin/recalculate_scores', methods=['GET', 'POST'])
@admin_required
def recalculate_scores():
    """Admin route to recalculate all scores"""
    if request.method == 'POST':
        try:
            team_rounds = TeamRound.query.all()
            updated_count = 0
            significant_changes = []

            for team_round in team_rounds:
                try:
                    old_raw_score = team_round.raw_score
                    new_raw_score = scoring_service.aggregate_judge_scores(team_round.team_round_id)
                    if new_raw_score is not None:
                        team_round.raw_score = new_raw_score
                        updated_count += 1
                        if old_raw_score and abs(new_raw_score - old_raw_score) > 50:
                            team = Team.query.get(team_round.team_id)
                            round_obj = Round.query.get(team_round.round_id)
                            significant_changes.append({
                                'team_number': team.team_nummer if team else 'Unknown',
                                'round_number': round_obj.round_number if round_obj else 'Unknown',
                                'old_score': old_raw_score,
                                'new_score': new_raw_score,
                                'difference': new_raw_score - old_raw_score
                            })
                except Exception as e:
                    logger.error(f"Error recalculating team round {team_round.team_round_id}: {e}")

            rounds_processed = set()
            for team_round in team_rounds:
                if team_round.round_id not in rounds_processed:
                    try:
                        normalized_scores = scoring_service.normalize_round_scores(team_round.round_id)
                        round_team_rounds = TeamRound.query.filter_by(round_id=team_round.round_id).all()
                        for tr in round_team_rounds:
                            if tr.team_id in normalized_scores:
                                tr.normalized_score = normalized_scores[tr.team_id]
                        rounds_processed.add(team_round.round_id)
                    except Exception as e:
                        logger.error(f"Error normalizing round {team_round.round_id}: {e}")

            db.session.commit()
            flash(f'Recalculated {updated_count} team scores across {len(rounds_processed)} rounds', 'success')
            return render_template('scoring/recalculate_results.html',
                                   updated_count=updated_count,
                                   rounds_processed=len(rounds_processed),
                                   significant_changes=significant_changes)

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in recalculation: {str(e)}")
            flash(f'Error during recalculation: {str(e)}', 'error')

    return render_template('scoring/recalculate_confirm.html')


@scoring_bp.route('/team_scoresheet_pdf/<int:team_id>/<int:round_id>')
def team_scoresheet_pdf(team_id, round_id):
    """Generate HTML scoresheet for a team in a specific round (renders as PDF in browser)"""
    try:
        team = Team.query.get_or_404(team_id)
        round_obj = Round.query.get_or_404(round_id)
        event = Event.query.get_or_404(round_obj.event_id)

        team_round = TeamRound.query.filter_by(team_id=team_id, round_id=round_id).first()
        if not team_round:
            flash('Keine Wertungen fur dieses Team in diesem Durchgang gefunden', 'error')
            return redirect(url_for('scoring.team_results'))

        scores = Score.query.options(
            db.joinedload(Score.values).joinedload(ScoreValue.task_type),
            db.joinedload(Score.judge)
        ).filter_by(team_round_id=team_round.team_round_id).all()

        figures = TaskType.query.filter_by(is_active=True).order_by(TaskType.sort_order).all()

        team_data = {
            'team': team,
            'figures': figures,
            'scores': scores,
            'team_round': team_round,
        }

        html = render_template('scoring/team_scoresheet_pdf.html',
                               team_data=team_data,
                               round_obj=round_obj,
                               event=event)

        response = make_response(html)
        response.headers['Content-Type'] = 'text/html'
        return response

    except Exception as e:
        logger.error(f"Error generating scoresheet PDF: {str(e)}")
        flash(f'Fehler beim Erstellen des Bewertungsbogens: {str(e)}', 'error')
        return redirect(url_for('scoring.team_results'))

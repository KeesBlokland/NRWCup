"""
File: app/routes/bp_system.py
Version: 2.0.0
Created: 2024-12-04
Last Updated: 2024-12-04
Description: Complete blueprint for system management including backup, users, and logs
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify
from app.models import db, User, AuditLog, SystemConfig, Event
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy.exc import SQLAlchemyError
from app.utils.auth import admin_required
from app.utils.audit import audit_log
import logging
import os
import shutil
from datetime import datetime, timedelta
import zipfile

# Configure logger
logger = logging.getLogger(__name__)

# Project root: this file lives at app/routes/bp_system.py → two levels up
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Create blueprint
system_bp = Blueprint('system', __name__)

_EMPTY_STATS = {'user_count': 0, 'log_count': 0, 'backup_count': 0, 'db_size': 0}

def get_log_files_info():
    """Get information about log files in the logs directory"""
    log_files = []
    log_dir = os.path.join(PROJECT_ROOT, 'logs')
    if os.path.exists(log_dir):
        for filename in sorted(os.listdir(log_dir)):
            if filename.endswith('.log'):
                file_path = os.path.join(log_dir, filename)
                size = os.path.getsize(file_path)
                if size < 1024:
                    size_formatted = f"{size} B"
                elif size < 1024 * 1024:
                    size_formatted = f"{size / 1024:.1f} KB"
                else:
                    size_formatted = f"{size / (1024 * 1024):.1f} MB"
                log_files.append({
                    'name': filename,
                    'size_formatted': size_formatted,
                    'modified': datetime.fromtimestamp(os.path.getmtime(file_path))
                })
    return log_files

def get_system_stats():
    """Gather system statistics"""
    try:
        stats = {
            'user_count': 0,
            'log_count': 0,
            'backup_count': 0,
            'db_size': 0
        }
        
        # Get user count
        stats['user_count'] = User.query.count()
        
        # Get log count
        stats['log_count'] = AuditLog.query.count()
        
        # Count backups
        backup_dir = os.path.join(PROJECT_ROOT, 'backups')
        if os.path.exists(backup_dir):
            stats['backup_count'] = len([f for f in os.listdir(backup_dir) 
                                       if f.endswith('.zip')])
        
        # Get database size
        db_path = os.path.join(PROJECT_ROOT, 'instance', 'NRWCup2025.db')
        if os.path.exists(db_path):
            stats['db_size'] = os.path.getsize(db_path)
            
        return stats
        
    except Exception as e:
        logger.error(f"Error gathering system stats: {str(e)}")
        return _EMPTY_STATS

def create_backup():
    """Create full project backup (database + code + config)"""
    try:
        project_root = PROJECT_ROOT
        backup_dir = os.path.join(project_root, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        backup_name = f'nrwcup_backup_{timestamp}.zip'
        backup_path = os.path.join(backup_dir, backup_name)

        # Directories to skip
        exclude_dirs = {'__pycache__', '.git', 'venv', 'backups', 'doc_archives',
                        'instance', 'node_modules', '.pytest_cache', 'logs'}
        # File extensions to skip
        exclude_ext = {'.pyc', '.pyo', '.pyd', '.bak'}

        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Database first (kept under instance/ path in the archive)
            db_path = os.path.join(project_root, 'instance', 'NRWCup2025.db')
            if os.path.exists(db_path):
                zf.write(db_path, 'instance/NRWCup2025.db')

            # Walk entire project tree
            for root, dirs, files in os.walk(project_root):
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                for file in files:
                    if os.path.splitext(file)[1] in exclude_ext:
                        continue
                    file_path = os.path.join(root, file)
                    arc_path = os.path.relpath(file_path, project_root)
                    zf.write(file_path, arc_path)

        size_mb = os.path.getsize(backup_path) / (1024 * 1024)
        logger.info(f"Backup created: {backup_name} ({size_mb:.1f} MB)")
        return backup_name

    except Exception as e:
        logger.error(f"Backup creation failed: {str(e)}")
        raise

# Route handlers
@system_bp.route('/')
@admin_required
def index():
    """System dashboard"""
    try:
        stats = get_system_stats()
        log_files = get_log_files_info()

        # Check logging status
        logging_config = SystemConfig.query.filter_by(config_key='logging_enabled').first()
        is_logging_enabled = logging_config is not None and logging_config.config_value == 'true'

        events = Event.query.order_by(Event.event_date.desc()).all()

        return render_template('system/system_main.html',
                             stats=stats,
                             log_files=log_files,
                             is_logging_enabled=is_logging_enabled,
                             events=events)
    except Exception as e:
        flash('Fehler beim Laden der Systemübersicht', 'error')
        return render_template('system/system_main.html', stats=_EMPTY_STATS)

        
@system_bp.route('/backup', methods=['GET', 'POST'])
@admin_required
def backup():
    """Backup management"""
    if request.method == 'POST':
        try:
            backup_name = create_backup()
            flash(f'Backup {backup_name} erfolgreich erstellt', 'success')
        except Exception as e:
            flash('Fehler beim Erstellen des Backups', 'error')
            logger.error(f"Backup creation error: {str(e)}")
    
    # List existing backups
    backups = []
    backup_dir = os.path.join(PROJECT_ROOT, 'backups')
    if os.path.exists(backup_dir):
        for filename in sorted(os.listdir(backup_dir), reverse=True):
            if filename.endswith('.zip'):
                file_path = os.path.join(backup_dir, filename)
                # Parse date from filename (nrwcup_backup_2026-02-12_07-30-00.zip)
                try:
                    ts = filename.replace('nrwcup_backup_', '').replace('.zip', '')
                    backup_date = datetime.strptime(ts, '%Y-%m-%d_%H-%M-%S')
                except ValueError:
                    backup_date = datetime.fromtimestamp(os.path.getmtime(file_path))
                backups.append({
                    'name': filename,
                    'size': os.path.getsize(file_path),
                    'date': backup_date
                })
    
    return render_template('system/system_backup.html', backups=backups,
                           backup_dir=os.path.join(PROJECT_ROOT, 'backups'))

@system_bp.route('/backup/download/<filename>')
@admin_required
def download_backup(filename):
    """Download specific backup"""
    try:
        safe_filename = secure_filename(filename)
        backup_path = os.path.join(PROJECT_ROOT, 'backups', safe_filename)
        if os.path.exists(backup_path) and safe_filename.endswith('.zip'):
            return send_file(
                backup_path,
                mimetype='application/zip',
                as_attachment=True,
                download_name=filename
            )
        else:
            flash('Backup nicht gefunden', 'error')
    except Exception as e:
        flash('Fehler beim Download des Backups', 'error')
        logger.error(f"Backup download error: {str(e)}")
    
    return redirect(url_for('system.backup'))

@system_bp.route('/backup/delete', methods=['POST'])
@admin_required
def delete_backups():
    """Delete selected backups"""
    selected = request.form.getlist('selected')
    deleted = 0
    for filename in selected:
        safe_name = secure_filename(filename)
        if safe_name.endswith('.zip'):
            file_path = os.path.join(PROJECT_ROOT, 'backups', safe_name)
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted += 1
                logger.info(f"Backup deleted: {safe_name}")
    if deleted:
        flash(f'{deleted} Backup(s) gelöscht', 'success')
    else:
        flash('Keine Backups gelöscht', 'warning')
    return redirect(url_for('system.backup'))

@system_bp.route('/users')
@admin_required
def users():
    """User management"""
    try:
        users_list = User.query.order_by(User.username).all()
        return render_template('system/system_users.html', users=users_list)
    except SQLAlchemyError as e:
        logger.error(f"Database error in users: {str(e)}")
        flash('Fehler beim Laden der Benutzer', 'error')
        return render_template('system/system_users.html', users=[])

@system_bp.route('/users/add', methods=['POST'])
@admin_required
def add_user():
    """Add new user"""
    try:
        username = request.form['username']
        if User.query.filter_by(username=username).first():
            flash('Benutzername existiert bereits', 'error')
            return redirect(url_for('system.users'))
            
        user = User(
            username=username,
            password=generate_password_hash(request.form['password'], method='pbkdf2:sha256'),
            role=request.form['role']
        )
        db.session.add(user)
        audit_log('users', None, 'created', None, f'{username} ({request.form["role"]})')
        db.session.commit()
        flash('Benutzer erfolgreich angelegt', 'success')
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error adding user: {str(e)}")
        flash('Fehler beim Anlegen des Benutzers', 'error')
        
    return redirect(url_for('system.users'))

@system_bp.route('/users/edit/<int:user_id>', methods=['POST'])
@admin_required
def edit_user(user_id):
    """Edit existing user"""
    try:
        user = User.query.get_or_404(user_id)
        if request.form.get('password'):
            user.password = generate_password_hash(
                request.form['password'],
                method='pbkdf2:sha256'
            )
        if request.form.get('role'):
            user.role = request.form['role']

        audit_log('users', user_id, 'updated', None, user.username)
        db.session.commit()
        flash('Benutzer erfolgreich aktualisiert', 'success')
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error editing user: {str(e)}")
        flash('Fehler beim Aktualisieren des Benutzers', 'error')
        
    return redirect(url_for('system.users'))

@system_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete user"""
    try:
        user = User.query.get_or_404(user_id)
        if user.username == 'admin':
            flash('Der Admin-Benutzer kann nicht gelöscht werden', 'error')
            return redirect(url_for('system.users'))
            
        audit_log('users', user_id, 'deleted', user.username, None)
        db.session.delete(user)
        db.session.commit()
        flash('Benutzer erfolgreich gelöscht', 'success')
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error deleting user: {str(e)}")
        flash('Fehler beim Löschen des Benutzers', 'error')
        
    return redirect(url_for('system.users'))

@system_bp.route('/logs')
@admin_required
def logs():
    """System logs"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 50

        logs_query = AuditLog.query\
            .order_by(AuditLog.changed_at.desc())\
            .paginate(page=page, per_page=per_page)
        log_files = get_log_files_info()

        return render_template('system/system_logs.html', logs=logs_query,
                               log_files=log_files)

    except SQLAlchemyError as e:
        logger.error(f"Database error in logs: {str(e)}")
        flash('Fehler beim Laden der Logs', 'error')
        return render_template('system/system_logs.html', logs=None, log_files=[])

@system_bp.route('/logs/download/<filename>')
@admin_required
def download_log(filename):
    """Download a log file"""
    try:
        safe_filename = secure_filename(filename)
        log_path = os.path.join(PROJECT_ROOT, 'logs', safe_filename)
        if os.path.exists(log_path) and safe_filename.endswith('.log'):
            return send_file(log_path, as_attachment=True, download_name=safe_filename)
        else:
            flash('Log-Datei nicht gefunden', 'error')
    except Exception as e:
        flash('Fehler beim Download der Log-Datei', 'error')
        logger.error(f"Log download error: {str(e)}")
    return redirect(url_for('system.logs'))

@system_bp.route('/logs/clear', methods=['POST'])
@admin_required
def clear_logs():
    """Clear old logs"""
    try:
        cutoff = datetime.now() - timedelta(days=30)
        AuditLog.query.filter(AuditLog.changed_at < cutoff).delete()
        db.session.commit()
        flash('Alte Logs erfolgreich gelöscht', 'success')
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error clearing logs: {str(e)}")
        flash('Fehler beim Löschen der Logs', 'error')
        
    return redirect(url_for('system.logs'))

@system_bp.route('/logs/cleanup', methods=['POST'])
@admin_required
def cleanup_log_files():
    """Delete startup-only log files, keep 5 most recent"""
    try:
        log_dir = os.path.join(PROJECT_ROOT, 'logs')
        if not os.path.exists(log_dir):
            flash('Kein Log-Verzeichnis vorhanden', 'warning')
            return redirect(url_for('system.index'))

        log_files = sorted(f for f in os.listdir(log_dir) if f.endswith('.log'))
        deleted = 0
        flagged = []

        # Keep the 5 most recent regardless
        candidates = log_files[:-5] if len(log_files) > 5 else []

        for filename in candidates:
            file_path = os.path.join(log_dir, filename)
            with open(file_path, 'r') as f:
                has_real_content = any(
                    'Application starting' not in line
                    for line in f if line.strip()
                )
            if has_real_content:
                flagged.append(filename)
            else:
                os.remove(file_path)
                deleted += 1

        msg = f'{deleted} Log-Datei(en) gelöscht'
        if flagged:
            msg += f', {len(flagged)} mit Inhalt übersprungen: {", ".join(flagged)}'
        flash(msg, 'success')

    except Exception as e:
        logger.error(f"Log cleanup error: {str(e)}")
        flash('Fehler beim Bereinigen der Log-Dateien', 'error')

    return redirect(url_for('system.index'))

@system_bp.route('/logs/delete', methods=['POST'])
@admin_required
def delete_log_files():
    """Delete selected log files"""
    selected = request.form.getlist('selected')
    deleted = 0
    for filename in selected:
        safe_name = secure_filename(filename)
        if safe_name.endswith('.log'):
            file_path = os.path.join(PROJECT_ROOT, 'logs', safe_name)
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted += 1
                logger.info(f"Log file deleted: {safe_name}")
    if deleted:
        flash(f'{deleted} Log-Datei(en) gelöscht', 'success')
    else:
        flash('Keine Log-Dateien gelöscht', 'warning')
    return redirect(url_for('system.logs'))

@system_bp.route('/check_email', methods=['GET'])
def check_email():
    """Check if the mail server is reachable"""
    try:
        import socket
        from app.config import Config
        sock = socket.create_connection((Config.MAIL_SERVER, Config.MAIL_PORT), timeout=5)
        sock.close()
        return jsonify({'available': True})
    except Exception:
        return jsonify({'available': False})

@system_bp.route('/toggle_logging', methods=['POST'])
@admin_required
def toggle_logging():
    """Enable or disable application logging"""
    try:
        current_status = SystemConfig.query.filter_by(config_key='logging_enabled').first()

        if not current_status:
            current_status = SystemConfig(
                config_key='logging_enabled',
                config_value='false',
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(current_status)

        current_status.config_value = 'true' if current_status.config_value == 'false' else 'false'
        current_status.updated_at = datetime.utcnow()
        db.session.commit()

        status_text = 'aktiviert' if current_status.config_value == 'true' else 'deaktiviert'
        flash(f'Logging {status_text}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Fehler: {str(e)}', 'error')

    return redirect(url_for('system.index'))

@system_bp.route('/hilfe')
def hilfe():
    """Display Benutzerhandbuch (pre-rendered into template)"""
    return render_template('system/hilfe.html')


@system_bp.route('/toggle_event_hidden/<int:event_id>', methods=['POST'])
@admin_required
def toggle_event_hidden(event_id):
    """Toggle visibility of an event (admin only)"""
    try:
        event = Event.query.get_or_404(event_id)
        event.is_hidden = not event.is_hidden
        db.session.commit()
        state = 'verborgen' if event.is_hidden else 'sichtbar'
        flash(f'Wettbewerb "{event.name}" ist jetzt {state}.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error toggling event visibility: {str(e)}")
        flash('Fehler beim Ändern der Sichtbarkeit', 'error')
    return redirect(url_for('system.index'))

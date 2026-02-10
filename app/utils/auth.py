"""
File: app/utils/auth.py
Version: 1.0.0
Created: 2026-02-10
Description: Shared authentication decorators for route protection
"""

from functools import wraps
from flask import session, flash, redirect, url_for


def admin_required(f):
    """Decorator that requires admin session to access a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Admin-Zugang erforderlich', 'error')
            return redirect(url_for('scoring.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

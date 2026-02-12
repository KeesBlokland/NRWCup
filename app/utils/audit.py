# app/utils/audit.py
"""Simple audit logging — records who changed what and when."""

import logging
from datetime import datetime
from app.models import db, AuditLog

logger = logging.getLogger(__name__)


def audit_log(table_name, record_id, action, old_value=None, new_value=None):
    """Write an entry to the audit log.

    Args:
        table_name: e.g. 'scores', 'users', 'events'
        record_id: primary key of the affected record (or None)
        action:    short description, stored in field_changed
        old_value: previous value (optional)
        new_value: new value (optional)
    """
    try:
        entry = AuditLog(
            table_name=table_name,
            record_id=record_id,
            field_changed=action,
            old_value=str(old_value)[:200] if old_value is not None else None,
            new_value=str(new_value)[:200] if new_value is not None else None,
            changed_at=datetime.utcnow()
        )
        db.session.add(entry)
        # Don't commit — let the caller's commit include this
    except Exception as e:
        logger.error(f"Audit log failed: {e}")

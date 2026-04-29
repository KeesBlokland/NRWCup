# File: app/utils/scoring_constants.py
# Scoring rule constants derived from the task_types DB table.
# Organisers manage these via the Figuren edit page -- no code changes needed.

def get_scoring_constants():
    """
    Read scoring rule constants from the DB.
    Returns (ALWAYS_MANDATORY, EXCLUSIVE_GROUPS).

    ALWAYS_MANDATORY   -- set of codes that are active, not messwertung, and not in any exclusive group
    EXCLUSIVE_GROUPS   -- list of sets, one per exclusive_group number; each set contains the codes in that group
    """
    from app.models import TaskType

    active = TaskType.query.filter_by(is_active=True).all()

    # Collect exclusive groups: {group_number: {code, ...}}
    groups = {}
    for t in active:
        if t.exclusive_group is not None:
            groups.setdefault(t.exclusive_group, set()).add(t.code)
    exclusive_groups = list(groups.values())

    all_exclusive_codes = {code for g in exclusive_groups for code in g}
    always_mandatory = {t.code for t in active if not t.is_messwertung and t.code not in all_exclusive_codes}

    return always_mandatory, exclusive_groups

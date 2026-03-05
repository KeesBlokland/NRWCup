"""
scripts/migrate_2026.py
2026 rules migration: rename figure display names, deactivate removed figures.

Run ONCE on each environment (dev, Pi, VPS) after deploying the 2026 code.
Safe to run more than once -- checks current state before making changes.

Usage:
  python3 scripts/migrate_2026.py
  python3 scripts/migrate_2026.py --dry-run
"""

import sys
import os
import argparse
import sqlite3

# Locate the database
CANDIDATE_PATHS = [
    os.path.join(os.path.dirname(__file__), '..', 'instance', 'NRWCup2025.db'),
    '/home/NRWcup/instance/NRWCup2025.db',
]


def find_db():
    for p in CANDIDATE_PATHS:
        path = os.path.normpath(p)
        if os.path.exists(path):
            return path
    return None


# Figures to rename: (code, new_name_de)
RENAMES = [
    ('STRT',     'Start'),
    ('PLTZR',    'Steigflug'),
    ('PLTZR-M',  'Steigflug mit Figur-M'),
    ('PLTZU',    'Ueberflug'),
    ('PLTZU-OV', 'Ueberflug mit 2 Halbkreisen'),
    ('ERSCH',    'Gesamterscheinungsbild Schleppgespann'),
]

# Figures to deactivate: code
DEACTIVATE = ['PLTZR-MK', 'PLTZU-KR']


def run(dry_run=False):
    db_path = find_db()
    if not db_path:
        print("ERROR: database not found. Tried:")
        for p in CANDIDATE_PATHS:
            print("  " + os.path.normpath(p))
        sys.exit(1)

    print("Database: " + db_path)
    if dry_run:
        print("DRY RUN -- no changes will be written")
    print()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    changes = 0

    # --- Renames ---
    for code, new_name in RENAMES:
        cur.execute(
            "SELECT name_de FROM task_types WHERE code = ?", (code,)
        )
        row = cur.fetchone()
        if row is None:
            print("SKIP (not found): " + code)
            continue
        current = row[0]
        if current == new_name:
            print("OK (already done): " + code + " = " + new_name)
            continue
        print("RENAME: " + code + "  '" + current + "'  ->  '" + new_name + "'")
        if not dry_run:
            cur.execute(
                "UPDATE task_types SET name_de = ? WHERE code = ?",
                (new_name, code)
            )
        changes += 1

    # --- Deactivations ---
    for code in DEACTIVATE:
        cur.execute(
            "SELECT name_de, is_active FROM task_types WHERE code = ?", (code,)
        )
        row = cur.fetchone()
        if row is None:
            print("SKIP (not found): " + code)
            continue
        name, active = row
        if not active:
            print("OK (already inactive): " + code + " (" + name + ")")
            continue
        print("DEACTIVATE: " + code + " (" + name + ")")
        if not dry_run:
            cur.execute(
                "UPDATE task_types SET is_active = 0 WHERE code = ?", (code,)
            )
        changes += 1

    # --- Add num_judges column to events if missing ---
    cur.execute("PRAGMA table_info(events)")
    col_names = [row[1] for row in cur.fetchall()]
    if 'num_judges' in col_names:
        print("OK (already exists): events.num_judges")
    else:
        print("ADD COLUMN: events.num_judges INTEGER DEFAULT 3")
        if not dry_run:
            cur.execute("ALTER TABLE events ADD COLUMN num_judges INTEGER DEFAULT 3")
        changes += 1

    if changes == 0:
        print()
        print("Nothing to do -- database already up to date.")
    elif dry_run:
        print()
        print(str(changes) + " change(s) would be applied (dry run, nothing written).")
    else:
        conn.commit()
        print()
        print(str(changes) + " change(s) applied and committed.")

    conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='NRW Cup 2026 DB migration')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would change without writing anything')
    args = parser.parse_args()
    run(dry_run=args.dry_run)

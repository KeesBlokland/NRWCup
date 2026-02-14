# User/Authentication System Review

**Date:** 2026-02-14
**Status:** Review complete, implementation pending

## Current State

The User management system is **largely vestigial** — it exists but isn't used for authentication or tracking.

### How Auth Actually Works

- Login at `/auth/login` compares the entered password against a **single hardcoded config value** `ADMIN_PASSWORD` (set to `'NRWAdmin'`)
- On success, it sets `session['is_admin'] = True`
- The `@admin_required` decorator only checks `session['is_admin']`, never looks at the User model
- Everyone logs in with the same shared password

### What the User Model Has (But Doesn't Use)

- **User table**: `user_id`, `username`, `password` (hashed), `role` (Admin/Judge/User)
- **CRUD routes** at `/system/users` — create, edit, delete users works
- **Foreign keys** pointing to User:
  - `Score.entered_by` — never populated (always NULL)
  - `AuditLog.changed_by` — never populated (always NULL)
- **Roles** (Admin/Judge/User) exist in the model but are **never enforced**

### Consequences

- No way to know *who* made a change (audit log `changed_by` is always empty)
- Created users sit in the database unused
- The "Benutzer verwalten" page works technically, but users it manages don't connect to anything

## Files Involved

| File | Role |
|------|------|
| `app/models.py` | User model definition (user_id, username, password, role) |
| `app/routes/bp_auth.py` | Login route — uses `ADMIN_PASSWORD` config, NOT User model |
| `app/routes/bp_system.py` | User CRUD routes (`/system/users`) |
| `app/templates/system/system_users.html` | User management UI |
| `app/utils/auth.py` | `@admin_required` decorator — checks `session['is_admin']` only |
| `app/utils/audit.py` | `audit_log()` — has `changed_by` param but callers never pass it |
| `config.py` | `ADMIN_PASSWORD = 'NRWAdmin'` |

## Options

### Option 1: Remove It
- Delete the vestigial User model and CRUD routes
- Simplify to just the shared password
- Least effort, cleanest codebase

### Option 2: Connect It (Recommended)
- Wire up actual per-user login using the existing User model
- Populate `entered_by` / `changed_by` in scores and audit logs
- Enforce roles:
  - **Judge**: can only view and score assigned rounds
  - **Admin**: full access (current behavior)
  - **User**: read-only access to results
- Benefits: know who scored what, accountability, proper audit trail

### Option 3: Leave As-Is
- Doesn't break anything, just unused code
- Least risk but adds confusion

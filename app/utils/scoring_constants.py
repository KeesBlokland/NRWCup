# File: app/utils/scoring_constants.py
# Scoring rule constants shared across bp_scoring and round_status.
# Update here when rules change -- do not duplicate elsewhere.

MESSWERTUNG_CODES = {'SEGZEIT', 'LANDGM', 'LANS', 'SEILZ'}

ALWAYS_MANDATORY = {
    'STRT', 'AUSKL', 'VKURV', 'SEILW',
    'LANM', 'LANDM', 'LANDGS', 'LANDS', 'ERSCH'
}

# Exactly ONE from each group must be scored per flight (non-zero)
EXCLUSIVE_GROUPS = [
    {'PLTZR', 'PLTZR-M'},   # Steigflug: Standard OR mit Figur-M
    {'PLTZU', 'PLTZU-OV'},  # Ueberflug: Standard OR mit 2 Halbkreisen
]

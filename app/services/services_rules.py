"""
File: app/services/services_rules.py
Version: 1.0.0
Created: 2025-03-02
Description: Service for managing scoring rules and rule sets
"""

from app.models import db, ScoringRuleSet, ScoringRule
from app.utils.utils_base_service import BaseService
from sqlalchemy import desc
import json
from datetime import datetime
import copy

class RuleService(BaseService):
    """Service for ScoringRuleSet and ScoringRule operations"""
    
    def __init__(self):
        super().__init__(ScoringRuleSet)
    
    def get_all_rule_sets(self):
        """
        Get all rule sets ordered by creation date.
        
        Returns:
            List of ScoringRuleSet instances
        """
        return self.model_class.query\
            .order_by(desc(self.model_class.created_at))\
            .all()
    
    def get_rule_set_by_id(self, rule_set_id):
        """
        Get a rule set by ID with its rules.
        
        Args:
            rule_set_id: ID of the rule set
            
        Returns:
            ScoringRuleSet instance with rules loaded
        """
        return self.model_class.query\
            .options(db.joinedload(ScoringRuleSet.rules))\
            .filter_by(rule_set_id=rule_set_id)\
            .first()
    
    def create_rule_set(self, name, description=None):
        """
        Create a new rule set.
        
        Args:
            name: Name of the rule set
            description: Optional description
            
        Returns:
            Created ScoringRuleSet instance
        """
        rule_set = ScoringRuleSet(
            name=name,
            description=description,
            is_active=False,
            created_at=datetime.utcnow(),
            version="1.0.0"
        )
        
        db.session.add(rule_set)
        db.session.commit()
        
        # Add default rules for NRW Cup
        self._add_default_rules(rule_set.rule_set_id)
        
        return rule_set
    
    def update_rule_set(self, rule_set_id, name, description=None, is_active=False):
        """
        Update a rule set.
        
        Args:
            rule_set_id: ID of the rule set to update
            name: New name
            description: New description
            is_active: Whether the rule set is active
            
        Returns:
            Updated ScoringRuleSet instance
        """
        rule_set = self.get_by_id(rule_set_id)
        if not rule_set:
            return None
            
        rule_set.name = name
        rule_set.description = description
        
        # If activating this rule set, deactivate all others
        if is_active and not rule_set.is_active:
            self._deactivate_all_rule_sets()
            rule_set.is_active = True
        elif not is_active:
            rule_set.is_active = False
            
        db.session.commit()
        return rule_set
    
    def delete_rule_set(self, rule_set_id):
        """
        Delete a rule set and all its rules.
        
        Args:
            rule_set_id: ID of the rule set to delete
            
        Returns:
            True if successful, False otherwise
        """
        rule_set = self.get_by_id(rule_set_id)
        if not rule_set:
            return False
            
        # First delete all rules
        ScoringRule.query.filter_by(rule_set_id=rule_set_id).delete()
        
        # Then delete the rule set
        db.session.delete(rule_set)
        db.session.commit()
        
        return True
    
    def get_rules_for_set(self, rule_set_id):
        """
        Get all rules for a rule set ordered by execution order.
        
        Args:
            rule_set_id: ID of the rule set
            
        Returns:
            List of ScoringRule instances
        """
        return ScoringRule.query\
            .filter_by(rule_set_id=rule_set_id)\
            .order_by(ScoringRule.order)\
            .all()
    
    def update_rules_for_set(self, rule_set_id, rules_data):
        """
        Update rules for a rule set based on JSON data.
        
        Args:
            rule_set_id: ID of the rule set
            rules_data: List of rule data dicts
            
        Returns:
            True if successful, False otherwise
        """
        rule_set = self.get_by_id(rule_set_id)
        if not rule_set:
            return False
            
        try:
            # First delete all existing rules
            ScoringRule.query.filter_by(rule_set_id=rule_set_id).delete()
            
            # Then create new rules
            for i, rule_data in enumerate(rules_data):
                # Ensure we have the required fields
                if 'rule_type' not in rule_data:
                    continue
                    
                # Make sure parameters is a dict, default to empty dict if missing
                params = rule_data.get('parameters', {})
                if not isinstance(params, dict):
                    params = {}
                    
                rule = ScoringRule(
                    rule_set_id=rule_set_id,
                    rule_type=rule_data['rule_type'],
                    order=i,  # Use index as order to ensure sequential ordering
                    parameters=json.dumps(params)
                )
                db.session.add(rule)
                
            # Increment version number
            version_parts = rule_set.version.split('.')
            version_parts[-1] = str(int(version_parts[-1]) + 1)
            rule_set.version = '.'.join(version_parts)
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"Error updating rules: {str(e)}")
            return False
    
    def duplicate_rule_set(self, rule_set_id):
        """
        Duplicate a rule set including all its rules.
        
        Args:
            rule_set_id: ID of the rule set to duplicate
            
        Returns:
            New ScoringRuleSet instance
        """
        original = self.get_rule_set_by_id(rule_set_id)
        if not original:
            return None
            
        # Create new rule set
        new_rule_set = ScoringRuleSet(
            name=f"{original.name} (Copy)",
            description=original.description,
            is_active=False,
            created_at=datetime.utcnow(),
            version=original.version
        )
        
        db.session.add(new_rule_set)
        db.session.flush()  # Get ID without committing
        
        # Create new rules
        for rule in original.rules:
            new_rule = ScoringRule(
                rule_set_id=new_rule_set.rule_set_id,
                rule_type=rule.rule_type,
                order=rule.order,
                parameters=rule.parameters
            )
            db.session.add(new_rule)
            
        db.session.commit()
        return new_rule_set
    
    def set_active_rule_set(self, rule_set_id):
        """
        Set a rule set as the active one.
        
        Args:
            rule_set_id: ID of the rule set to activate
            
        Returns:
            True if successful, False otherwise
        """
        rule_set = self.get_by_id(rule_set_id)
        if not rule_set:
            return False
            
        # Deactivate all rule sets
        self._deactivate_all_rule_sets()
        
        # Activate the requested rule set
        rule_set.is_active = True
        db.session.commit()
        
        return True
    
    def get_active_rule_set(self):
        """
        Get the currently active rule set.
        
        Returns:
            Active ScoringRuleSet instance or None
        """
        return self.model_class.query\
            .filter_by(is_active=True)\
            .options(db.joinedload(ScoringRuleSet.rules))\
            .first()
    
    def export_rule_set(self, rule_set_id):
        """
        Export a rule set and its rules as a dictionary.
        
        Args:
            rule_set_id: ID of the rule set to export
            
        Returns:
            Dict representation of the rule set
        """
        rule_set = self.get_rule_set_by_id(rule_set_id)
        if not rule_set:
            return None
            
        # Convert to dictionary
        result = {
            'name': rule_set.name,
            'description': rule_set.description,
            'version': rule_set.version,
            'rules': []
        }
        
        # Add rules
        for rule in sorted(rule_set.rules, key=lambda r: r.order):
            result['rules'].append({
                'rule_type': rule.rule_type,
                'parameters': json.loads(rule.parameters)
            })
            
        return result
    
    def import_rule_set(self, rule_set_data):
        """
        Import a rule set from a dictionary.
        
        Args:
            rule_set_data: Dict representation of the rule set
            
        Returns:
            Imported ScoringRuleSet instance
        """
        if not isinstance(rule_set_data, dict) or 'name' not in rule_set_data:
            return None
            
        # Create new rule set
        new_rule_set = ScoringRuleSet(
            name=rule_set_data['name'],
            description=rule_set_data.get('description', ''),
            is_active=False,
            created_at=datetime.utcnow(),
            version=rule_set_data.get('version', '1.0.0')
        )
        
        db.session.add(new_rule_set)
        db.session.flush()  # Get ID without committing
        
        # Create rules
        for i, rule_data in enumerate(rule_set_data.get('rules', [])):
            new_rule = ScoringRule(
                rule_set_id=new_rule_set.rule_set_id,
                rule_type=rule_data['rule_type'],
                order=i,
                parameters=json.dumps(rule_data['parameters'])
            )
            db.session.add(new_rule)
            
        db.session.commit()
        return new_rule_set
    
    def get_available_rule_types(self):
        """
        Get available rule types with their parameters.
        
        Returns:
            Dict of rule types with parameter schemas
        """
        # These are the supported rule types for NRW Cup scoring
        return {
            'judge_averaging': {
                'name': 'Punktrichterwertung',
                'description': 'Berechnet den Durchschnitt der Punktrichterwertungen',
                'parameters': {
                    'min_judges': {
                        'type': 'integer',
                        'description': 'Mindestzahl an Punktrichtern',
                        'default': 3
                    },
                    'drop_lowest': {
                        'type': 'boolean',
                        'description': 'Niedrigste Wertung streichen',
                        'default': True
                    },
                    'drop_highest': {
                        'type': 'boolean',
                        'description': 'Höchste Wertung streichen',
                        'default': False
                    }
                }
            },
            'normalization': {
                'name': 'Normalisierung',
                'description': 'Normalisiert Wertungen auf eine bestimmte Skala',
                'parameters': {
                    'scale_factor': {
                        'type': 'integer',
                        'description': 'Skalierungsfaktor',
                        'default': 1000
                    },
                    'reference': {
                        'type': 'select',
                        'description': 'Referenzwert für Normalisierung',
                        'options': ['max', 'avg'],
                        'default': 'max'
                    }
                }
            },
            'drop_lowest_round': {
                'name': 'Niedrigste Runde streichen',
                'description': 'Streicht die niedrigste Rundenwertung bei der Gesamtwertung',
                'parameters': {
                    'min_rounds_required': {
                        'type': 'integer',
                        'description': 'Mindestzahl an Runden',
                        'default': 4
                    }
                }
            },
            'tiebreaker': {
                'name': 'Gleichstandsregel',
                'description': 'Regelt den Umgang mit Gleichständen',
                'parameters': {
                    'tiebreak_method': {
                        'type': 'select',
                        'description': 'Methode zur Auflösung von Gleichständen',
                        'options': ['best_round', 'count_back'],
                        'default': 'best_round'
                    }
                }
            }
        }
    
    def _deactivate_all_rule_sets(self):
        """Deactivate all rule sets"""
        self.model_class.query.update({ScoringRuleSet.is_active: False})
    
    def _add_default_rules(self, rule_set_id):
        """
        Add default NRW Cup rules to a new rule set.
        
        Args:
            rule_set_id: ID of the rule set
        """
        # NRW Cup default rules
        default_rules = [
            {
                'rule_type': 'judge_averaging',
                'order': 0,
                'parameters': {
                    'min_judges': 3,
                    'drop_lowest': True,
                    'drop_highest': False
                }
            },
            {
                'rule_type': 'normalization',
                'order': 1,
                'parameters': {
                    'scale_factor': 1000,
                    'reference': 'max'
                }
            },
            {
                'rule_type': 'drop_lowest_round',
                'order': 2,
                'parameters': {
                    'min_rounds_required': 4
                }
            }
        ]
        
        # Add rules
        for rule_data in default_rules:
            rule = ScoringRule(
                rule_set_id=rule_set_id,
                rule_type=rule_data['rule_type'],
                order=rule_data['order'],
                parameters=json.dumps(rule_data['parameters'])
            )
            db.session.add(rule)
            
        db.session.commit()
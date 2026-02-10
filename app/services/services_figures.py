"""
File: app/services/services_figures.py
Version: 1.0.0
Created: 2025-03-02
Description: Specialized service for TaskType (figures) model
"""

from sqlalchemy import nullslast
from app.models import db, TaskType, Score, ScoreValue
from app.utils.utils_base_service import BaseService

class FiguresService(BaseService):
    """Service for TaskType operations"""
    
    def __init__(self):
        super().__init__(TaskType)
    
    def get_active_figures(self):
        """
        Get all active scoring figures.
        
        Returns:
            List of TaskType instances that are active
        """
        return self.model_class.query\
            .filter(self.model_class.is_active == True)\
            .order_by(nullslast(self.model_class.sort_order), self.model_class.name_de)\
            .all()
    
    def get_ordered_figures(self):
        """
        Get all figures ordered by sort_order.
        
        Returns:
            List of TaskType instances ordered by sort_order
        """
        return self.model_class.query\
            .order_by(nullslast(self.model_class.sort_order), self.model_class.name_de)\
            .all()
    
    def get_by_code(self, code):
        """
        Get figure by code.
        
        Args:
            code: Figure code
            
        Returns:
            TaskType instance or None if not found
        """
        return self.model_class.query\
            .filter(self.model_class.code == code)\
            .first()
    
    def can_delete(self, figure_id):
        """
        Check if a figure can be deleted.
        
        Args:
            figure_id: ID of the figure to check
            
        Returns:
            True if can be deleted, False otherwise
        """
        # Check for related score values
        has_scores = db.session.query(ScoreValue.query\
            .filter(ScoreValue.task_type_id == figure_id)\
            .exists())\
            .scalar()
        
        return not has_scores
    
    def update_multiple(self, figures_data):
        """
        Update multiple figures at once.
        
        Args:
            figures_data: List of dicts with figure data
            
        Returns:
            Number of updated figures
        """
        count = 0
        for figure_data in figures_data:
            figure_id = figure_data.pop('type_id', None)
            if figure_id:
                try:
                    self.update(figure_id, **figure_data)
                    count += 1
                except Exception:
                    db.session.rollback()
        return count
"""
File: app/services/base_service.py
Version: 1.0.1
Created: 2025-03-01
Last Modified: 2025-03-24
Description: Base service class for common database operations
"""

from sqlalchemy.exc import SQLAlchemyError
from app.models import db

class BaseService:
    """Base service class for common database operations."""
    
    def __init__(self, model_class):
        """
        Initialize the base service.
        
        Args:
            model_class: SQLAlchemy model class
        """
        self.model_class = model_class
    
    def get_all(self, order_by=None, filters=None):
        """
        Get all records of the model with optional ordering and filtering.
        
        Args:
            order_by: SQLAlchemy order_by clause or attribute name
            filters: Dict of filter conditions
            
        Returns:
            List of model instances
        """
        query = self.model_class.query
        
        # Apply filters if provided
        if filters:
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    query = query.filter(getattr(self.model_class, key) == value)
        
        # Apply ordering if provided
        if order_by:
            if isinstance(order_by, str) and hasattr(self.model_class, order_by):
                query = query.order_by(getattr(self.model_class, order_by))
            else:
                query = query.order_by(order_by)
        
        return query.all()
    
    def get_by_id(self, id):
        """
        Get a record by ID.
        
        Args:
            id: ID of the record to retrieve
            
        Returns:
            Model instance or None if not found
        """
        return self.model_class.query.get(id)
    
    def create(self, **kwargs):
        """
        Create a new record.
        
        Args:
            **kwargs: Model attributes
            
        Returns:
            Created model instance or None if error
        """
        try:
            record = self.model_class(**kwargs)
            db.session.add(record)
            db.session.commit()
            return record
        except SQLAlchemyError:
            db.session.rollback()
            raise
    
    def update(self, id, **kwargs):
        """
        Update an existing record.
        
        Args:
            id: ID of the record to update
            **kwargs: Model attributes to update
            
        Returns:
            Updated model instance or None if error
        """
        try:
            record = self.get_by_id(id)
            if not record:
                return None
            
            for key, value in kwargs.items():
                if hasattr(record, key):
                    setattr(record, key, value)
            
            db.session.commit()
            return record
        except SQLAlchemyError:
            db.session.rollback()
            raise
    
    def delete(self, id):
        """
        Delete a record.
        
        Args:
            id: ID of the record to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            record = self.get_by_id(id)
            if not record:
                return False
            
            db.session.delete(record)
            db.session.commit()
            return True
        except SQLAlchemyError:
            db.session.rollback()
            raise
    
    def exists(self, **kwargs):
        """
        Check if a record exists with the given attributes.
        
        Args:
            **kwargs: Model attributes to filter by
            
        Returns:
            True if exists, False otherwise
        """
        filters = []
        for key, value in kwargs.items():
            if hasattr(self.model_class, key):
                filters.append(getattr(self.model_class, key) == value)
        
        return db.session.query(self.model_class.query.filter(*filters).exists()).scalar()
    
    def count(self, filters=None):
        """
        Count records with optional filtering.
        
        Args:
            filters: Dict of filter conditions
            
        Returns:
            Count of records
        """
        query = self.model_class.query
        
        # Apply filters if provided
        if filters:
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    query = query.filter(getattr(self.model_class, key) == value)
        
        return query.count()
    
    def get_or_create(self, defaults=None, **kwargs):
        """
        Get a record matching the kwargs, or create it with defaults.
        
        Args:
            defaults: Dict of default values for creation
            **kwargs: Model attributes to filter by
            
        Returns:
            Tuple of (record, created) where created is a boolean
        """
        try:
            filters = []
            for key, value in kwargs.items():
                if hasattr(self.model_class, key):
                    filters.append(getattr(self.model_class, key) == value)
            
            record = self.model_class.query.filter(*filters).first()
            if record:
                return record, False
            
            # Record doesn't exist, create it
            create_kwargs = kwargs.copy()
            if defaults:
                create_kwargs.update(defaults)
            
            record = self.create(**create_kwargs)
            return record, True
        except SQLAlchemyError:
            db.session.rollback()
            raise
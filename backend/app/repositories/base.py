"""
Base repository pattern for generic CRUD operations.

Provides common database operations that can be inherited by specific repositories.
"""

from typing import Generic, TypeVar, Type, Optional, List
from sqlalchemy.orm import Session

from app.database.models import Base

# Type variable for model class
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Base repository with generic CRUD operations.

    Usage:
        class UserRepository(BaseRepository[User]):
            def __init__(self, db: Session):
                super().__init__(User, db)
    """

    def __init__(self, model: Type[ModelType], db: Session):
        """
        Initialize repository with model class and database session.

        Args:
            model: SQLAlchemy model class
            db: Database session
        """
        self.model = model
        self.db = db

    def get(self, id: int) -> Optional[ModelType]:
        """
        Get a single record by ID.

        Args:
            id: Primary key ID

        Returns:
            Model instance or None if not found
        """
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """
        Get all records with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of model instances
        """
        return self.db.query(self.model).offset(skip).limit(limit).all()

    def create(self, obj: ModelType) -> ModelType:
        """
        Create a new record.

        Args:
            obj: Model instance to create

        Returns:
            Created model instance with ID populated
        """
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, id: int, **kwargs) -> Optional[ModelType]:
        """
        Update a record by ID.

        Args:
            id: Primary key ID
            **kwargs: Fields to update

        Returns:
            Updated model instance or None if not found
        """
        obj = self.get(id)
        if obj:
            for key, value in kwargs.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
            self.db.commit()
            self.db.refresh(obj)
        return obj

    def delete(self, id: int) -> bool:
        """
        Delete a record by ID.

        Args:
            id: Primary key ID

        Returns:
            True if deleted, False if not found
        """
        obj = self.get(id)
        if obj:
            self.db.delete(obj)
            self.db.commit()
            return True
        return False

    def count(self) -> int:
        """
        Count total records.

        Returns:
            Total number of records
        """
        return self.db.query(self.model).count()

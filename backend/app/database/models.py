"""
SQLAlchemy database models for MEF-Immobili backend.

Models:
- User: User accounts and authentication
- Run: Analysis runs and results
- Feedback: User feedback on buildings
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class User(Base):
    """User account model."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    runs = relationship("Run", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class Run(Base):
    """Analysis run model - stores complete analysis session."""

    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Query and status
    query = Column(Text, nullable=False)
    status = Column(String(50), default="processing", nullable=False)

    # Results
    results = Column(JSON, nullable=True)
    gemini_responses = Column(JSON, nullable=True)
    location_data = Column(JSON, nullable=True)
    status_message = Column(Text, nullable=True)

    # Metadata
    dataset_key = Column(String(50), default="full")
    analysis_mode = Column(String(50), default="agent")
    results_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="runs")
    feedback = relationship(
        "Feedback", back_populates="run", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Run(id={self.id}, run_id='{self.run_id}', status='{self.status}')>"


class Feedback(Base):
    """User feedback on individual buildings."""

    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(100), ForeignKey("runs.run_id"), nullable=False, index=True)
    # building_id is optional to support app-level feedback (not tied to a single building)
    building_id = Column(String(100), nullable=True, index=True)

    # Feedback content
    rating = Column(
        Integer, nullable=True
    )  # 1-5 stars (optional for app-level feedback)
    comment = Column(Text, nullable=True)
    helpful = Column(Integer, nullable=True)  # 0=no, 1=yes, null=not answered

    # Additional evaluation fields
    feedback_e1 = Column(Text, nullable=True)
    feedback_e2 = Column(Text, nullable=True)
    feedback_e3 = Column(Text, nullable=True)
    feedback_e4 = Column(Text, nullable=True)
    feedback_e5 = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    run = relationship("Run", back_populates="feedback")

    def __repr__(self):
        return f"<Feedback(id={self.id}, building_id='{self.building_id}', rating={self.rating})>"

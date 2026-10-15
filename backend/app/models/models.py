from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    subjects = relationship("Subject", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    concept_states = relationship("ConceptState", back_populates="user", cascade="all, delete-orphan")


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(20), default="#4f46e5")
    priority_weight = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    user = relationship("User", back_populates="subjects")
    topics = relationship("Topic", back_populates="subject", cascade="all, delete-orphan")
    concepts = relationship("Concept", back_populates="subject", cascade="all, delete-orphan")
    materials = relationship("Material", back_populates="subject", cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    name = Column(String(120), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    subject = relationship("Subject", back_populates="topics")
    concepts = relationship("Concept", back_populates="topic", cascade="all, delete-orphan")


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    subject = relationship("Subject", back_populates="materials")


class Concept(Base):
    __tablename__ = "concepts"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    subject = relationship("Subject", back_populates="concepts")
    topic = relationship("Topic", back_populates="concepts")
    questions = relationship("Question", back_populates="concept", cascade="all, delete-orphan")
    concept_states = relationship("ConceptState", back_populates="concept", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    concept_id = Column(Integer, ForeignKey("concepts.id"), nullable=False)
    text = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)  # list of strings: ["opt A", "opt B", ...]
    answer_index = Column(Integer, nullable=False)
    explanation = Column(Text, nullable=True)
    status = Column(String(20), default="approved")  # "draft", "approved", "flagged"
    created_at = Column(DateTime(timezone=True), default=utc_now)

    concept = relationship("Concept", back_populates="questions")
    attempts = relationship("Attempt", back_populates="question")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)
    is_completed = Column(Boolean, default=False)
    started_at = Column(DateTime(timezone=True), default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="sessions")
    attempts = relationship("Attempt", back_populates="session", cascade="all, delete-orphan")


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    concept_id = Column(Integer, ForeignKey("concepts.id"), nullable=False)
    event_id = Column(String(80), unique=True, index=True, nullable=False)  # Idempotent event ID
    selected_index = Column(Integer, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    answered_at = Column(DateTime(timezone=True), default=utc_now)

    session = relationship("Session", back_populates="attempts")
    question = relationship("Question", back_populates="attempts")


class ConceptState(Base):
    """User-concept pair state tracking HLR estimates and practice history."""
    __tablename__ = "concept_state"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    concept_id = Column(Integer, ForeignKey("concepts.id"), nullable=False)
    total_correct = Column(Integer, default=0)
    total_incorrect = Column(Integer, default=0)
    last_practiced_at = Column(DateTime(timezone=True), nullable=True)
    h_hat = Column(Float, default=2.0)  # estimated half-life in days
    p_hat_cached = Column(Float, default=0.5)  # latest estimated recall probability
    next_review_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    __table_args__ = (UniqueConstraint("user_id", "concept_id", name="uq_user_concept"),)

    user = relationship("User", back_populates="concept_states")
    concept = relationship("Concept", back_populates="concept_states")


class TrainingRecord(Base):
    """Record saved at session-close for offline/online HLR training."""
    __tablename__ = "training_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    concept_id = Column(Integer, ForeignKey("concepts.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    p = Column(Float, nullable=False)  # observed session recall rate
    delta_days = Column(Float, nullable=False)  # elapsed days since last practice
    x_before = Column(JSON, nullable=False)  # feature vector before session
    created_at = Column(DateTime(timezone=True), default=utc_now)


class ModelVersion(Base):
    """Stores model weights and feature specs."""
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, index=True)
    version_name = Column(String(60), unique=True, nullable=False)
    theta = Column(JSON, nullable=False)  # list of floats [theta_0, theta_1, theta_2, ...]
    feature_spec = Column(String(40), default="raw_counts")  # "raw_counts" or "sqrt_counts"
    hyperparameters = Column(JSON, default=dict)
    metrics = Column(JSON, default=dict)  # MAE, AUC, etc.
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    daily_minutes = Column(Integer, default=60)
    subject_priorities = Column(JSON, default=dict)  # {subject_id: priority_multiplier}
    exam_dates = Column(JSON, default=dict)  # {subject_id: "YYYY-MM-DD"}
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="settings")

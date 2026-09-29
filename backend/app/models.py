import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class RunnerProfile(Base):
    __tablename__ = "runner_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    age = Column(Integer, nullable=False)
    gender = Column(String(20), nullable=False)
    experience_level = Column(String(30), nullable=False)
    pb_5k = Column(String(10), nullable=False)
    pb_10k = Column(String(10), nullable=True)
    target_race_distance = Column(String(30), nullable=False)
    target_race_time = Column(String(10), nullable=False)
    current_weekly_mileage = Column(Float, nullable=False)
    training_days_per_week = Column(Integer, nullable=False)
    preferred_training_days = Column(String(100), nullable=False)  # Comma separated, e.g. "Tuesday,Thursday,Saturday,Sunday"
    plan_duration_weeks = Column(Integer, nullable=False)
    injury_limitations = Column(Text, nullable=True)
    easy_run_pace = Column(String(10), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    training_plans = relationship("TrainingPlan", back_populates="profile", cascade="all, delete-orphan")


class TrainingPlan(Base):
    __tablename__ = "training_plans"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    runner_profile_id = Column(String(36), ForeignKey("runner_profiles.id"), nullable=False)
    
    calculated_vdot = Column(Float, nullable=False)
    target_pace = Column(String(10), nullable=False)
    
    # Store JSON strings for rule-based and AI-generated outputs for direct research comparison
    rule_based_plan_json = Column(Text, nullable=False)
    ai_plan_json = Column(Text, nullable=False)
    
    explainability_summary = Column(Text, nullable=False)
    ai_model_used = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("RunnerProfile", back_populates="training_plans")
    evaluations = relationship("PlanEvaluation", back_populates="plan", cascade="all, delete-orphan")


class PlanEvaluation(Base):
    __tablename__ = "plan_evaluations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    training_plan_id = Column(String(36), ForeignKey("training_plans.id"), nullable=False)
    
    # Identifies whether the participant evaluated the 'rule_based' baseline or the 'ai_personalized' plan
    evaluated_plan_type = Column(String(20), nullable=False, default="ai_personalized")
    
    # 1 to 5 Likert Scale criteria for S2 research paper
    personalization_score = Column(Integer, nullable=False)
    usefulness_score = Column(Integer, nullable=False)
    clarity_score = Column(Integer, nullable=False)
    confidence_score = Column(Integer, nullable=False)
    
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    plan = relationship("TrainingPlan", back_populates="evaluations")

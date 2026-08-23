"""
SQLAlchemy ORM Models for History, Logging, Scheduler, and Auxiliary system tables.
"""

import datetime
from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text

from src.database.base import Base


class SearchHistoryModel(Base):
    __tablename__ = "SearchHistory"

    run_id = Column(String, primary_key=True)
    triggered_at = Column(DateTime, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=False)
    sources_run = Column(Text, nullable=True)
    items_collected = Column(Integer, default=0)
    items_after_dedup = Column(Integer, default=0)
    items_emailed = Column(Integer, default=0)
    errors = Column(Text, nullable=True)


class EmailHistoryModel(Base):
    __tablename__ = "EmailHistory"

    id = Column(String, primary_key=True)
    opportunity_id = Column(String, ForeignKey("Opportunities.id"), nullable=False, index=True)
    email_run_id = Column(String, nullable=False)
    sent_at = Column(DateTime, nullable=False)
    clicked = Column(Boolean, default=False)


class SchedulerStateModel(Base):
    __tablename__ = "scheduler_state"

    id = Column(Integer, primary_key=True, default=1)
    last_email_sent = Column(Text, nullable=True)
    last_pipeline_run = Column(Text, nullable=True)
    updated_at = Column(Text, nullable=True)


class AppLogModel(Base):
    __tablename__ = "AppLogs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.datetime.utcnow, index=True)
    level = Column(String, nullable=False, index=True)
    module = Column(String, nullable=False, index=True)
    function_name = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    execution_time_ms = Column(Float, nullable=True)
    exception_text = Column(Text, nullable=True)
    correlation_id = Column(String, nullable=True)


class PreferenceModel(Base):
    __tablename__ = "Preferences"

    id = Column(String, primary_key=True)
    key = Column(String, nullable=False, unique=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class StatisticModel(Base):
    __tablename__ = "Statistics"

    id = Column(String, primary_key=True)
    date = Column(Date, nullable=False)
    source_id = Column(String, ForeignKey("Sources.id"), nullable=True)
    category = Column(String, nullable=True)
    count = Column(Integer, default=0)
    avg_score = Column(Float, default=0.0)


class KeywordModel(Base):
    __tablename__ = "Keywords"

    id = Column(String, primary_key=True)
    term = Column(String, nullable=False)
    domain = Column(String, nullable=True)
    synonym_of = Column(String, ForeignKey("Keywords.id"), nullable=True)


class SchemaVersionModel(Base):
    __tablename__ = "schema_version"

    version = Column(Integer, primary_key=True)
    applied_at = Column(DateTime, nullable=False)
    description = Column(Text, nullable=True)


class SchedulerWebhookRequestModel(Base):
    __tablename__ = "scheduler_webhook_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(128), unique=True, nullable=False, index=True)
    timestamp = Column(Integer, nullable=False)
    received_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    status = Column(String(32), nullable=False, default="accepted")
    source = Column(String(64), nullable=False, default="google_apps_script")
    execution_details = Column(Text, nullable=True)
    email_status = Column(String(32), nullable=True, default=None)


SchedulerTriggerNonce = SchedulerWebhookRequestModel



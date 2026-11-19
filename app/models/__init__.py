"""
Database Models Package
-----------------------
SQLAlchemy ORM models matching the MySQL schema.
Each model maps to one database table from the ER diagram.
"""

from app.models.role import Role
from app.models.user import User
from app.models.session import Session
from app.models.task import Task
from app.models.interaction_data import InteractionData
from app.models.cognitive_metrics import CognitiveMetrics
from app.models.aggregated_metrics import AggregatedMetrics
from app.models.alert import Alert
from app.models.publication import Publication
from app.models.feedback_request import FeedbackRequest
from app.models.feedback import Feedback
from app.models.notification import Notification
from app.models.analytics_report import AnalyticsReport
from app.models.system_log import SystemLog
from app.models.system_settings import SystemSettings
from app.models.email_message import EmailMessage

__all__ = [
    'Role', 'User', 'Session', 'Task', 'InteractionData',
    'CognitiveMetrics', 'AggregatedMetrics', 'Alert',
    'Publication', 'FeedbackRequest', 'Feedback', 'Notification',
    'AnalyticsReport', 'SystemLog', 'SystemSettings', 'EmailMessage',
]

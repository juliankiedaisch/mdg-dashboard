# Dashboard Module - Database Models
from src.db import db
from datetime import datetime, timezone
from src.utils import utc_isoformat


class DashboardPage(db.Model):
    """Highest level in the hierarchy. Can contain multiple topics."""
    __tablename__ = 'dashboard_page'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text, default='')
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    topics = db.relationship('DashboardTopic', back_populates='page', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'sort_order': self.sort_order,
            'is_deleted': self.is_deleted,
            'created_at': utc_isoformat(self.created_at),
            'updated_at': utc_isoformat(self.updated_at),
        }

    def to_dict_full(self):
        """Include nested topics and their applications."""
        data = self.to_dict()
        data['topics'] = [
            t.to_dict_full()
            for t in self.topics.filter_by(is_deleted=False).order_by(DashboardTopic.sort_order).all()
        ]
        return data


class DashboardTopic(db.Model):
    """Belongs to a page. Acts as a section header for related applications."""
    __tablename__ = 'dashboard_topic'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default='')
    page_id = db.Column(db.Integer, db.ForeignKey('dashboard_page.id'), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    page = db.relationship('DashboardPage', back_populates='topics')
    applications = db.relationship('DashboardApplication', back_populates='topic', lazy='dynamic')

    # Unique name within the same page
    __table_args__ = (
        db.UniqueConstraint('name', 'page_id', name='uq_topic_name_per_page'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'page_id': self.page_id,
            'page_name': self.page.name if self.page else None,
            'sort_order': self.sort_order,
            'is_deleted': self.is_deleted,
            'created_at': utc_isoformat(self.created_at),
            'updated_at': utc_isoformat(self.updated_at),
        }

    def to_dict_full(self):
        """Include nested applications."""
        data = self.to_dict()
        data['applications'] = [
            a.to_dict()
            for a in self.applications.filter_by(is_deleted=False).order_by(DashboardApplication.sort_order).all()
        ]
        return data


class DashboardApplication(db.Model):
    """An application link belonging to a topic."""
    __tablename__ = 'dashboard_application'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default='')
    url = db.Column(db.Text, nullable=False)
    icon = db.Column(db.Text, default='')
    topic_id = db.Column(db.Integer, db.ForeignKey('dashboard_topic.id'), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    topic = db.relationship('DashboardTopic', back_populates='applications')

    # Unique name within the same topic
    __table_args__ = (
        db.UniqueConstraint('name', 'topic_id', name='uq_app_name_per_topic'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'url': self.url,
            'icon': self.icon,
            'topic_id': self.topic_id,
            'topic_name': self.topic.name if self.topic else None,
            'page_id': self.topic.page_id if self.topic else None,
            'page_name': self.topic.page.name if self.topic and self.topic.page else None,
            'sort_order': self.sort_order,
            'is_deleted': self.is_deleted,
            'created_at': utc_isoformat(self.created_at),
            'updated_at': utc_isoformat(self.updated_at),
        }

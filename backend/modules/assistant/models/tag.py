# Assistant Module - Database Models: Tag & Source-Tag Mapping
"""
Tag system for knowledge source access control.
Each tag maps to a dynamic permission: ASSISTANT_TAG_<TAG_NAME_UPPERCASE>
"""
from src.db import db
from datetime import datetime, timezone
from src.utils import utc_isoformat


# Association table for many-to-many: SourceConfig <-> AssistantTag
source_tag_mapping = db.Table(
    'assistant_source_tag_mapping',
    db.Column('source_id', db.Integer, db.ForeignKey('assistant_source_config.id', ondelete='CASCADE'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('assistant_tag.id', ondelete='CASCADE'), primary_key=True),
)


class AssistantTag(db.Model):
    """A tag used to categorize and restrict access to knowledge sources."""
    __tablename__ = 'assistant_tag'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(500), default='')
    automatic = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationship to sources via the mapping table
    sources = db.relationship(
        'SourceConfig',
        secondary=source_tag_mapping,
        backref=db.backref('tags', lazy='joined'),
        lazy='joined',
    )

    @property
    def permission_id(self) -> str:
        """The dynamically generated permission ID for this tag."""
        return f"ASSISTANT_TAG_{self.name.upper()}"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'automatic': self.automatic,
            'permission_id': self.permission_id,
            'created_at': utc_isoformat(self.created_at),
            'source_count': len(self.sources) if self.sources else 0,
        }

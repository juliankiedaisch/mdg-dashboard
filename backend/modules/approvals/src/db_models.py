# models.py
from src.db import db
from datetime import datetime, timezone

approval_group_association = db.Table(
    'approval_group_association',
    db.Column('approval_id', db.Integer, db.ForeignKey('approvals.id')),
    db.Column('group_id', db.Integer, db.ForeignKey('group.id'))
)

approval_user_association = db.Table(
    'approval_user_association',
    db.Column('approval_id', db.Integer, db.ForeignKey('approvals.id')),
    db.Column('user_id', db.String(80), db.ForeignKey('user.uuid'))
)

def extend_user(User, db):
    # Reverse relationships are already created by backref on the Approval
    # model (received_approvals, approvals_given).  Nothing to add here.
    pass

def extend_group(Group, db):
    # Reverse relationship 'approvals' is already created by backref on
    # the Approval model.  Nothing to add here.
    pass


class Applications(db.Model):
    __tablename__ = 'applications'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text)
    description = db.Column(db.Text)
    url = db.Column(db.Text)
    approvals = db.relationship('Approval', back_populates='application')

class Approval(db.Model):
    __tablename__ = 'approvals'
    id = db.Column(db.Integer, primary_key=True)

    groups = db.relationship(
        'Group',
        secondary=approval_group_association,
        backref='approvals',
    )

    # Nutzer, die dieses Approval erhalten haben (m:n)
    approved_users = db.relationship(
        'User',
        secondary=approval_user_association,
        primaryjoin='Approval.id == approval_user_association.c.approval_id',
        secondaryjoin='approval_user_association.c.user_id == User.uuid',
        backref='received_approvals',
    )

    # Nutzer, der dieses Approval vergeben hat (1:n)
    user_id = db.Column(db.String(80), db.ForeignKey('user.uuid'), nullable=False)
    given_by = db.relationship(
        'User',
        foreign_keys='Approval.user_id',
        backref='approvals_given',
    )
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False)
    application = db.relationship('Applications', back_populates='approvals')
    start = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    end = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def is_active(self):
        now = datetime.now(timezone.utc)
        return (self.start <= now) and (self.end is None or self.end >= now)
# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from src.db import db, plugin_field_user_hooks, plugin_field_group_hooks
from src.utils import utc_isoformat
import uuid as uuid_lib

user_group_association = db.Table(
    'user_group_association',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('group_id', db.Integer, db.ForeignKey('group.id'))
)

# ── Permission System Association Tables ────────────────────────────

profile_permission_association = db.Table(
    'profile_permission',
    db.Column('profile_id', db.Integer, db.ForeignKey('profile.id', ondelete='CASCADE')),
    db.Column('permission_id', db.String, db.ForeignKey('permission.id', ondelete='CASCADE'))
)

user_profile_association = db.Table(
    'user_profile',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE')),
    db.Column('profile_id', db.Integer, db.ForeignKey('profile.id', ondelete='CASCADE'))
)

group_profile_association = db.Table(
    'group_profile',
    db.Column('group_id', db.Integer, db.ForeignKey('group.id', ondelete='CASCADE')),
    db.Column('profile_id', db.Integer, db.ForeignKey('profile.id', ondelete='CASCADE'))
)


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String, unique=True)
    username = db.Column(db.String, unique=True, nullable=False)
    last_login = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    groups = db.relationship(
        'Group',
        secondary=user_group_association,
        back_populates='users'
    )

    profiles = db.relationship(
        'Profile',
        secondary=user_profile_association,
        back_populates='users',
        lazy='dynamic'
    )

class Group(db.Model):
    __tablename__ = 'group'
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String, unique=True)
    name = db.Column(db.String, unique=True, nullable=False)

    users = db.relationship(
        'User',
        secondary=user_group_association,
        back_populates='groups'
    )

    profiles = db.relationship(
        'Profile',
        secondary=group_profile_association,
        back_populates='groups',
        lazy='dynamic'
    )


# ── Permission System Models ────────────────────────────────────────

class Permission(db.Model):
    __tablename__ = 'permission'
    id = db.Column(db.String, primary_key=True)  # e.g. "survey.view"
    module = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    profiles = db.relationship(
        'Profile',
        secondary=profile_permission_association,
        back_populates='permissions'
    )

    def to_dict(self):
        return {
            "id": self.id,
            "module": self.module,
            "description": self.description,
            "created_at": utc_isoformat(self.created_at)
        }


class Profile(db.Model):
    __tablename__ = 'profile'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    description = db.Column(db.String, default='')
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    permissions = db.relationship(
        'Permission',
        secondary=profile_permission_association,
        back_populates='profiles',
        lazy='joined'
    )

    users = db.relationship(
        'User',
        secondary=user_profile_association,
        back_populates='profiles'
    )

    groups = db.relationship(
        'Group',
        secondary=group_profile_association,
        back_populates='profiles'
    )

    def to_dict(self, include_permissions=False, include_assignments=False):
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": utc_isoformat(self.created_at)
        }
        if include_permissions:
            data["permissions"] = [p.to_dict() for p in self.permissions]
        if include_assignments:
            data["users"] = [{"id": u.id, "uuid": u.uuid, "username": u.username} for u in self.users]
            data["groups"] = [{"id": g.id, "uuid": g.uuid, "name": g.name} for g in self.groups]
        return data


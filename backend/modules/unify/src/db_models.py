# models.py
from src.db import db

class DeviceGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True)

class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mac = db.Column(db.String, unique=True)
    ip = db.Column(db.String)
    name = db.Column(db.String)
    group_id = db.Column(db.Integer, db.ForeignKey('device_group.id'))
    group = db.relationship('DeviceGroup', backref='devices')

class DeviceLocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'))
    timestamp = db.Column(db.DateTime)
    ap_mac = db.Column(db.String)
    ap_name = db.Column(db.String)
    device = db.relationship('Device', backref='locations')
from datetime import datetime
from flask_login import UserMixin
from .db import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id       = db.Column(db.Integer, primary_key=True)
    email    = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    created  = db.Column(db.DateTime, default=datetime.utcnow)

class Recommendation(db.Model):
    __tablename__ = 'recommendations'
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    queried_at   = db.Column(db.DateTime, default=datetime.utcnow)
    user_cat     = db.Column(db.String(64))
    user_note    = db.Column(db.String(64))
    weather_desc = db.Column(db.String(64))
    results_json = db.Column(db.Text)

    user = db.relationship('User', backref='recommendations')

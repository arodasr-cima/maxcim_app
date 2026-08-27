from __future__ import annotations

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(120), nullable=False)
    initials = db.Column(db.String(4), nullable=False, default="DM")
    role = db.Column(db.String(40), nullable=False, default="DOCENTE")
    password_hash = db.Column(db.String(255), nullable=False)

    materials = db.relationship("Material", back_populates="owner", cascade="all, delete-orphan")
    sessions = db.relationship("LearningSession", back_populates="owner", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

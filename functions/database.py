from flask_login import UserMixin
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from functions.base import Base
import bcrypt

class User(Base, UserMixin):
    """User model for authentication"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default='viewer')  # admin, viewer
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def has_role(self, role):
        """Check if user has specific role"""
        if self.role == 'admin':
            return True  # Admin has all roles
        return self.role == role

    def __repr__(self):
        return f'<User {self.username}>'

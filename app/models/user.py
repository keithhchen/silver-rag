from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum
from pydantic import BaseModel
from uuid import uuid4
import enum
from app.models.base import Base

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"

class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid4()))
    username = Column(String(50), unique=True, index=True)
    password_hash = Column(String(128))
    role = Column(Enum(UserRole), default=UserRole.USER)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole = UserRole.USER

class UserUpdate(BaseModel):
    password: str

class User(BaseModel):
    id: int
    uuid: str
    username: str
    role: UserRole
    created_at: datetime
    updated_at: datetime

class UserLog(Base):
    __tablename__ = "user_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    action = Column(String(50))
    details = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
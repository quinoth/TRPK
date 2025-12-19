from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from ..database import Base 


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)  # используется как login
    password_hash = Column(String, nullable=False)
    first_name = Column(String)
    last_name = Column(String)

    attributes = Column(JSON, default=lambda: {
        "services": {},
        "is_email_confirmed": True,
        "role": "user"
      #  "is_underground": False  # флаг
    })

    deleted_at = Column(DateTime, default=None)  # soft delete

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
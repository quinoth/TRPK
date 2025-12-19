from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean 
from datetime import datetime, timedelta
from shared.database import Base
 
class ResetToken(Base):
    __tablename__ = "reset_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    token = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
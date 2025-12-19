from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from datetime import datetime, timedelta
from shared.database import Base
from shared.models.user import User
from sqlalchemy.orm import relationship

class ConfirmationCode(Base):
    __tablename__ = "confirmation_codes"

    id = Column(Integer, primary_key=True)
    code = Column(String(6), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(minutes=15))
    used = Column(Boolean, default=False)
    user = relationship("User", backref="confirmation_codes")
    def is_valid(self):
        return not self.used and datetime.utcnow() < self.expires_at
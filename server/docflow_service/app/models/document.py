

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from datetime import datetime
from shared.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    
    # Имя файла
    title = Column(String, nullable=False)

    # Путь к файлу на сервере
    file_path = Column(String, nullable=False)

    # Метаданные файла
    file_size = Column(Integer, nullable=False)        # в байтах
    content_type = Column(String, nullable=False)      # MIME-тип: image/png, application/pdf

    # Статус
    is_signed = Column(Boolean, default=False)
    signed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    signed_at = Column(DateTime, nullable=True)

    # Мягкое удаление
    deleted_at = Column(DateTime, nullable=True)

    # Аудит
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
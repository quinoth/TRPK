

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from contextlib import contextmanager

# Загрузка переменных окружения
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не найдена в .env")

# Создание движка
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# === КРИТИЧНЫЙ ИМПОРТ МОДЕЛЕЙ ДЛЯ РЕГИСТРАЦИИ ТАБЛИЦ В METADATA ===
# Эти импорты должны быть здесь — после создания engine,
# чтобы избежать проблемы с отсутствующими таблицами при FK-связях.
try:
    from shared.models.user import User           # Таблица: users
    from app.models.chat import ChatGroup         # Таблица: chat_groups
    from app.models.chat import GroupMember       # Таблица: group_members
    from app.models.chat import Message           
except ImportError as e:
    raise ImportError(f"Ошибка при импорте моделей: {e}")

# При необходимости можно раскомментировать для разработки (не для продакшена!)
# Base.metadata.create_all(bind=engine)  # ← создаёт таблицы, если их нет


def get_db():
    """
    Зависимость для FastAPI: предоставляет сессию БД.
    Используется как: def endpoint(db: Session = Depends(get_db))
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()  # Автоматический коммит при успехе
    except Exception:
        db.rollback()  # Откат при ошибке
        raise
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Контекстный менеджер для использования вне HTTP (например, WebSocket, CLI).
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

import sys
import os

# Добавляем путь к корню (server/) — туда, где лежит shared/
current_dir = os.path.dirname(os.path.abspath(__file__))  # app/
project_root = os.path.dirname(os.path.dirname(current_dir))  # server/

if project_root not in sys.path:
    sys.path.insert(0, project_root)
from shared.models.user import User
from app.utils.database import SessionLocal
from app.core.security import get_password_hash

def init_admin():
    db = SessionLocal()
    admin = db.query(User).filter(User.email == "admin1@example.com").first()
    if not admin:
        admin = User(
            email="admin1@example.com",
            password_hash=get_password_hash("admin123"),
            first_name="Admin",
            last_name="One",
            attributes={
                "services": {
                    "admin": {"read": True, "write": True, "delete": True},
                    "auth": {"read": True, "write": True, "delete": True},
                    "storage": {"read": True, "write": True, "delete": True},
                    "analytics": {"read": True, "write": False, "delete": False}
                },
                "is_email_confirmed": True,
                "role": "admin"
            }
        )
        db.add(admin)
        db.commit()
        print(" Admin user 'admin1@example.com' created.")
    db.close()
from fastapi import FastAPI
from app.routes.admin import router as admin_router
from app.utils.database import engine, SessionLocal
from shared.models.user import User
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
import os 
app = FastAPI(title="Admin Service Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ "http://localhost:3000",   
        "http://127.0.0.1:3000",
        "http://localhost:5173",   
        "http://127.0.0.1:5173",
        ],
    allow_credentials=True,
    allow_methods=["*"],  # разрешить все методы (GET, POST, OPTIONS и т.д.)
    allow_headers=["*"], 
    )# разрешить все заголовки 

# Создаём таблицы
User.metadata.create_all(bind=engine)

# Роуты
app.include_router(admin_router)

@app.get("/")
def root():
    return {"message": "Admin Service Backend. Use /api/admin/*"}

@app.on_event("startup")
def create_default_admin():
    db = SessionLocal()
    admin_email = os.getenv("ADMIN_EMAIL", "admin1@example.com")
    if not db.query(User).filter(User.email == admin_email, User.deleted_at.is_(None)).first():
        from app.utils.database import get_password_hash

        admin = User(
            email=admin_email,
            password_hash=get_password_hash("admin123"),
            first_name="System",
            last_name="Admin",
            attributes={
                "role": "admin",
                "services": {
                    "admin": {"read": True, "write": True, "delete": True},
                    "storage": {"read": True, "write": True, "delete": True}
                },
                "is_email_confirmed": True
            }
        )
        db.add(admin)
        db.commit()
        print(f" Администратор создан: {admin_email} / пароль: admin123")
    db.close()
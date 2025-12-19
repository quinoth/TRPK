
import logging
from fastapi import APIRouter, Depends, Request, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from shared.models.user import User
from app.utils.database import get_db
import httpx
import os
from typing import Optional
from datetime import datetime

 #===== Pydantic модели =====
class UpdateProfileRequest(BaseModel): 
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    bio: str | None = None
    organization: str | None = None

    class Config:
        from_attributes = True  # Pydantic v2
        
        
# === Настройка логирования ===
logger = logging.getLogger("app.bff")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Логируем начало загрузки модуля
logger.info(" Модуль BFF начат: загрузка конфигурации")


SERVICES = {
    "auth": os.getenv("AUTH_SERVICE_URL", "http://localhost:8001"),
    "chat": os.getenv("CHAT_SERVICE_URL", "http://localhost:8005"),
    "workflow": os.getenv("WORKFLOW_SERVICE_URL", "http://localhost:8004"),
    "admin": os.getenv("ADMIN_SERVICE_URL", "http://localhost:8003"),
    "docflow": os.getenv("DOCFLOW_SERVICE_URL", "http://localhost:8002"),
    "analytics": os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8006"),
    "logging": os.getenv("LOGGING_SERVICE_URL", "http://localhost:8007"),
    "video": os.getenv("VIDEO_SERVICE_URL", "http://localhost:8008"),
}

logger.info(f" Сервисы BFF настроены: {list(SERVICES.keys())}")

# Создаём роутер
router = APIRouter(prefix="/bff", tags=["BFF"])
logger.info(" Роутер BFF создан с префиксом /bff")




class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


# ===== Зависимость: получение текущего пользователя =====
def get_current_user_bff(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning(" Отсутствует заголовок Authorization")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth_header.split(" ", 1)[1]
    logger.debug(f" Получен токен: {token[:20]}...")

    try:
        from app.core.security import get_current_user
        user = get_current_user(token=token, db=db)
        logger.info(f" Пользователь аутентифицирован: {user.email} (ID={user.id})")
        return user
    except Exception as e:
        logger.error(f" Ошибка аутентификации: {str(e)}")
        raise


# ===== ПРОФИЛЬ =====
@router.get("/profile")
async def get_profile(
    #request: Request,
    user: User = Depends(get_current_user_bff),
    db: Session = Depends(get_db)
):
    logger.info(f" GET /bff/profile запрошен пользователем {user.email}")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"{SERVICES['auth']}/auth/users/{user.id}"
            logger.debug(f" Запрос к auth_service: {url}")
            response = await client.get(
                url,
                headers={"Authorization": request.headers.get("Authorization")}
            )

            if response.status_code == 200:
                user_db = response.json()
                logger.debug(f"🟢 Данные из auth_service получены: {user_db}")
                first_name = user_db.get("first_name") or user.email.split("@")[0]
                last_name = user_db.get("last_name") or "User"
                phone = user_db.get("phone", "")
                created_at = user_db.get("created_at", "")
                last_login = user_db.get("last_login", "")
            else:
                logger.warning(f" auth_service вернул статус {response.status_code}: {response.text}")
                first_name = user.email.split("@")[0]
                last_name = "User"
                phone = ""
                created_at = ""
                last_login = ""

    except Exception as e:
        logger.error(f" Ошибка при обращении к auth_service: {str(e)}")
        first_name = user.email.split("@")[0]
        last_name = "User"
        phone = ""
        created_at = ""
        last_login = ""

    profile_data = {
        "id": user.id,
        "username": user.email.split("@")[0],
        "email": user.email,
        "firstName": first_name,
        "lastName": last_name,
        "fullName": f"{first_name} {last_name}".strip(),
        "role": getattr(user, "role", "user"),
        "phone": phone,
        "bio": getattr(user, "bio", ""),
        "organization": getattr(user, "organization", ""),
        "createdAt": created_at,
        "lastLogin": last_login,
    }

    logger.info(f"📤 Ответ /bff/profile отправлен: {profile_data}")
    return profile_data


# ===== PUT /profile — Обновление своего профиля =====
@router.put("/profile")
async def update_profile(
    data:UpdateProfileRequest,
    user: User = Depends(get_current_user_bff),
    db: Session = Depends(get_db)
):
    logger.info(f" PUT /bff/profile от {user.email}, данные: {data}")

    # Собираем поля для обновления
    if data.first_name is not None:
        user.first_name = data.first_name
    if data.last_name is not None:
        user.last_name = data.last_name
    if data.phone is not None:
        user.phone = data.phone
    if data.bio is not None:
        user.bio = data.bio
    if data.organization is not None:
        user.organization = data.organization

    user.updated_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(user)
        logger.info(" Профиль успешно обновлён в БД")
    except Exception as e:
        db.rollback()
        logger.error(f" Ошибка при сохранении: {str(e)}")
        raise HTTPException(status_code=500, detail="Не удалось сохранить профиль")

    # Возвращаем полный профиль (как в GET)
    return {
        "id": str(user.id),
        "username": user.email.split("@")[0],
        "email": user.email,
        "firstName": user.first_name or "",
        "lastName": user.last_name or "",
        "fullName": f"{user.first_name or ''} {user.last_name or ''}".strip(),
        "role": user.role or "user",
        "phone": user.phone or "",
        "bio": user.bio or "",
        "organization": user.organization or "",
        "createdAt": user.created_at.isoformat() if user.created_at else "",
        
    }
    
    
    
    
    
    
# ===== POST /change-password =====
@router.post("/profile/change-password")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user_bff)
):
    logger.info(f" POST /bff/profile/change-password запрос от {user.email}")
    if not body.old_password or not body.new_password:
        logger.warning(" Не указан старый или новый пароль")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Необходимо указать старый и новый пароли"
        )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"{SERVICES['auth']}/auth/change-password"
            logger.debug(f" Отправка запроса на смену пароля: {url}")
            response = await client.post(
                url,
                json={
                    "old_password": body.old_password,
                    "new_password": body.new_password
                },
                headers={"Authorization": request.headers.get("Authorization")}
            )
            if response.status_code == 401:
                logger.warning(" Неверный текущий пароль")
                raise HTTPException(status_code=401, detail="Неверный текущий пароль")
            elif response.status_code != 200:
                logger.error(f" Ошибка смены пароля: {response.status_code} — {response.text}")
                raise HTTPException(status_code=response.status_code, detail="Ошибка при смене пароля")
            logger.info(" Пароль успешно изменён")
    except Exception as e:
        logger.critical(f" Ошибка при смене пароля: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Сервис недоступен: {str(e)}")

    return {"status": "success", "message": "Пароль успешно изменён"}


# ===== Другие BFF-эндпоинты =====
@router.get("/consultations")
async def get_consultations(user: User = Depends(get_current_user_bff)):
    logger.info(f" GET /bff/consultations для пользователя {user.email}")
    return {
        "upcoming": [
            {
                "id": 1,
                "title": "Видеоконсультация",
                "date": "2024-12-05",
                "time": "14:00",
                "specialist": "Иван Петров",
                "status": "scheduled",
                "type": "video"
            }
        ],
        "history": [
            {
                "id": 2,
                "title": "Первичная консультация",
                "date": "2024-11-28",
                "time": "15:30",
                "specialist": "Мария Сидорова",
                "status": "completed",
                "type": "video"
            }
        ]
    }


@router.get("/documents")
async def get_documents(user: User = Depends(get_current_user_bff)):
    logger.info(f" GET /bff/documents для пользователя {user.email}")
    return {"documents": []}


@router.get("/activity-log")
async def get_activity_log(user: User = Depends(get_current_user_bff)):
    logger.info(f" GET /bff/activity-log для пользователя {user.email}")
    return {"logs": []}


@router.get("/sidebar-menu")
async def get_sidebar_menu(user: User = Depends(get_current_user_bff)):
    logger.info(f" GET /bff/sidebar-menu для пользователя {user.email}")
    menu = [
        {"title": "Профиль", "link": "/profile"},
        {"title": "Чат", "link": "/chat"}
    ]
    if getattr(user, "role", None) == "admin":
        menu.append({"title": "Админка", "link": "/admin"})
    logger.debug(f" Сгенерировано меню: {menu}")
    return {"menu": menu}


#  Финальное сообщение: модуль загружен
logger.info(" Модуль BFF полностью загружен и готов к работе")



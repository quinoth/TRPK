from jose import jwt
from fastapi import Depends, HTTPException, status
from shared.models.user import User
from app.utils.database import get_db
import os 
from sqlalchemy.orm import Session
import logging
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError 

# Настройка логирования
logger = logging.getLogger("auth_debug")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter("[%(levelname)s] %(asctime)s - %(message)s", datefmt="%H:%M:%S")
)
if not logger.handlers:
    logger.addHandler(handler)
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
def has_permission(user_attrs: dict, service: str, permission: str) -> bool:
    return user_attrs.get("services", {}).get(service, {}).get(permission, False)

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Получает текущего пользователя по JWT токену.
    Все этапы проверки логируются.
    """
    print("\n" + "="*60)
    print(" НАЧАЛО АУТЕНТИФИКАЦИИ ПОЛЬЗОВАТЕЛЯ")
    print("="*60)

    #  Шаг 1: Проверяем, передан ли вообще токен
    if not token or token == "null" or token == "undefined":
        logger.error(" Токен не предоставлен или имеет недопустимое значение")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация: токен отсутствует",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f" Получен токен длиной {len(token)} символов")
    if len(token) < 100:
        logger.warning(f"  Подозрительно короткий токен: {repr(token)}")

    #  Шаг 2: Проверяем формат JWT (3 сегмента)
    segments = token.split(".")
    if len(segments) != 3:
        logger.error(f" Неверный формат JWT: найдено {len(segments)} сегментов вместо 3")
        logger.debug(f"Сегменты: {segments}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format: Not enough segments",
            headers={"WWW-Authenticate": "Bearer"},
        )

    #  Шаг 3: Проверяем SECRET_KEY
    if SECRET_KEY == "your-super-secret-key-change-in-production":
        logger.critical(" ОШИБКА: SECRET_KEY не изменён! Это небезопасно.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка сервера: SECRET_KEY не настроен"
        )
    else:
        logger.info(" SECRET_KEY установлен")

    #  Шаг 4: Декодируем JWT
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.info(f" Успешно декодирован JWT: {payload}")

        # Извлекаем email (основной идентификатор)
        email: str = payload.get("email")
        if not email:
            logger.error(" В токене отсутствует поле 'email'")
            raise HTTPException(401, "Invalid token: missing 'email'")

        
        user_id_str = payload.get("sub")
        if user_id_str:
            logger.info(f" sub (user_id): {user_id_str}")

    except JWTError as e:
        error_msg = str(e)
        logger.error(f" Ошибка при декодировании JWT: {error_msg}")

        if "Signature has expired" in error_msg:
            logger.warning(" Токен просрочен — требуется повторный вход")
        elif "Invalid signature" in error_msg:
            logger.critical(" Подпись невалидна — возможно, SECRET_KEY отличается между сервисами!")
        elif "Not enough segments" in error_msg:
            logger.error(" Формат токена повреждён — строка обрезана или пуста")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.critical(f" Неожиданная ошибка при обработке токена: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    #  Шаг 5: Поиск пользователя в БД по email
    logger.info(f" Поиск пользователя в БД по email: {email}")
    user = db.query(User).filter(
        User.email == email,
        User.deleted_at.is_(None)  # Учитываем soft delete
    ).first()

    if not user:
        logger.error(f" Пользователь с email={email} не найден или удалён")
        # Логируем всех активных пользователей для отладки
        available_users = db.query(User.email, User.id).filter(User.deleted_at.is_(None)).all()
        logger.debug(f" Активные пользователи в БД: {available_users}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не существует или удалён",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f" Пользователь аутентифицирован: {user.email} (ID={user.id})")
    return user
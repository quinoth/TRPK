
from jose import jwt, JWTError
from datetime import datetime
from shared.models.user import User
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = payload.get("exp")
        if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
            return None
        return payload
    except JWTError:
        return None




def get_user_from_token(token: str, db: Session) -> User | None:
    payload = decode_access_token(token)
    if not payload:
        return None

    email = payload.get("email")
    user_id = payload.get("sub")

    if not email or not user_id:
        return None

    #  Ключевое: загружаем все нужные поля сразу
    user = db.query(User).filter(User.id == int(user_id), User.email == email).first()

    if user and user.attributes:
        # Принудительно обращаемся к attributes, чтобы загрузить из БД
        _ = user.attributes  # или просто используй где нужно

    return user
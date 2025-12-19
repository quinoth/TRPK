from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Annotated
from itsdangerous import URLSafeTimedSerializer
from fastapi.security import OAuth2PasswordRequestForm
from shared.models.user import User
from app.models.confirmation_code import ConfirmationCode
from app.core.security import get_password_hash,verify_password,create_access_token
from app.utils.database import get_db
from app.utils.email import send_confirmation_code_sync, send_reset_link,update_profile
from app.models.reset_token import ResetToken
from fastapi import Body
from pydantic import EmailStr
from datetime import datetime
from typing import Optional




"""class UpdateProfileRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    organization: Optional[str] = None"""
    

s = URLSafeTimedSerializer("your-secret-key")
router = APIRouter()

class RegisterRequest(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    department: str


@router.post("/register")
def register_user(
    request: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)]
):
    if db.query(User).filter(User.email == request.email).first():
        raise HTTPException(400, "Email уже зарегистрирован")

   
    hashed = get_password_hash(request.password)

   
    new_user = User(
        email=request.email,
        password_hash=hashed,
        first_name=request.first_name,
        last_name=request.last_name,
        attributes={
            "role": request.department,
            "is_email_confirmed": False,
            "services": {}
        }
    )
    db.add(new_user)
    db.flush()  

    
    #code = f"{random.randint(100000, 999999)}"
    code = "123456"
   
    conf_code = ConfirmationCode(user_id=new_user.id, code=code)
    db.add(conf_code)
    db.commit()

    
   # background_tasks.add_task(send_confirmation_code_sync, request.email, code)

    return {"msg": "Регистрация успешна. Проверьте email для подтверждения."}




@router.post("/login")
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)]
):
    
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные учётные данные",
            headers={"WWW-Authenticate": "Bearer"},
        )


    if not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные учётные данные",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.attributes.get("is_email_confirmed", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email не подтверждён. Проверьте почту."
        )

 
    permissions = user.attributes.get("services", {})

    
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        permissions=permissions
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
"""@router.post("/forgot-password")
async def forgot_password(email: EmailStr, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"msg": "Если email существует — вы получите ссылку"}

    token = s.dumps(email, salt="password-reset-salt")
    
   
    reset_token = ResetToken(user_id=user.id, token=token)
    db.add(reset_token)
    db.commit()

    
    await send_reset_link(email, token)

    return {"msg": "Ссылка для сброса отправлена на email"}"""
    
    


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        return {"msg": "Если email существует — вы получите ссылку"}

    token = s.dumps(request.email, salt="password-reset-salt")

    reset_token = ResetToken(user_id=user.id, token=token)
    db.add(reset_token)
    db.commit()

    await send_reset_link(request.email, token)

    return {"msg": "Ссылка для сброса отправлена на email"}

@router.post("/reset-password")
async def reset_password(token: str, new_password: str, db: Session = Depends(get_db)):
    try:
        email = s.loads(token, salt="password-reset-salt", max_age=900)  # 15 мин
    except:
        raise HTTPException(400, "Неверный или просроченный токен")

    reset_record = db.query(ResetToken).filter(ResetToken.token == token, ResetToken.used == False).first()
    if not reset_record:
        raise HTTPException(400, "Токен уже использован")

    user = db.query(User).get(reset_record.user_id)
    user.password_hash = get_password_hash(new_password)
    
    reset_record.used = True
    db.commit()

    return {"msg": "Пароль успешно изменён"}

@router.post("/confirm-code")
def confirm_code(
    email: str = Body(embed=True),
    code: str = Body(embed=True),
    db: Session = Depends(get_db)
):
    # 1. Проверяем пользователя
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(400, "Пользователь не найден")

    # 2. Ищем активный код
    confirmation = (
        db.query(ConfirmationCode)
        .filter(
            ConfirmationCode.user_id == user.id,
            ConfirmationCode.used == False,
            ConfirmationCode.expires_at > datetime.utcnow()
        )
        .order_by(ConfirmationCode.expires_at.desc())
        .first()
    )

    if not confirmation:
        raise HTTPException(400, "Не найдено активное подтверждение")

    # 3. Сравниваем коды
    if confirmation.code.strip() != code.strip():
        raise HTTPException(400, "Неверный код")

    # 4. Обновляем attributes БЕЗ flag_modified
    user.attributes = {
        **(user.attributes or {}),  
        "is_email_confirmed": True  
    }

    # 5. Помечаем код как использованный
    confirmation.used = True

    # 6. Сохраняем
    db.commit()

    return {"msg": "Email подтверждён! Теперь можно войти."}





    
    



# === PUT /users/{user_id} — Обновление профиля ===
@router.put("/auth/users/{user_id}")
def update_user_profile(
    user_id: int,
     UpdateProfileRequest,
    db: Annotated[Session, Depends(get_db)]
):
    # Находим пользователя
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Обновляем поля модели (не attributes)
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

    # Обновляем время
    user.updated_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save profile")

    # Возвращаем обновлённые данные
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "bio": user.bio,
        "organization": user.organization,
        "role": user.role,
        "created_at": user.created_at,
        "updated_at": user.updated_at
    }
    
    
    
"""@router.get("/auth/users/{user_id}", response_model=UserResponse)
def get_user_profile(
    user_id: int,
    db: Annotated[Session, Depends(get_db)]
):
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "bio": user.bio,
        "organization": user.organization,
        "role": user.role,
        "created_at": user.created_at,
        "updated_at": user.updated_at
    }"""
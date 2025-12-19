from fastapi import APIRouter, Depends, HTTPException, File, UploadFile,Query, Body
import os 
import sys
from datetime import datetime, timezone
from shared.models.user import User
from sqlalchemy.orm import Session 
from typing import List
from app.core.security import get_admin_user
from app.utils.csv_import import parse_csv_users, create_underground_user
from app.utils.database import get_db 
#from shared.security import get_password_hash
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel
from typing import Dict, Any




router = APIRouter(prefix="/admin", tags=["Admin Panel"])

# === 1. Список всех активных пользователей (не удалённых) ===
@router.get("/users")
def list_users(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    users = db.query(User).filter(User.deleted_at.is_(None)).all()
    result = []
    for u in users:
        attrs = u.attributes or {}
        result.append({
            "id": u.id,
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "role": attrs.get("role", "user"),
         #   "is_underground": attrs.get("is_underground", False),
            "services": attrs.get("services", {}),
            #"can_edit": not attrs.get("is_underground", False)
        })
    return  result

# === 2. Создать underground-пользователя вручную ===
@router.post("/underground")
def create_regular_user(
    email: str = Body(..., embed=True),
    password: str = Body(..., embed=True),
    first_name: str = Body(None),
    last_name: str = Body(None),
    role: str = Body("user"),  # можно задать роль
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """
    Создаёт полноценного пользователя:
    - email подтверждён
    - роль указана
    - активен
    - services пустой объект
    """
    # Проверка: существует ли уже активный пользователь с таким email
    existing_user = db.query(User).filter(
        User.email == email,
        User.deleted_at.is_(None)
    ).first()

    if existing_user:
        raise HTTPException(400, "Пользователь с таким email уже существует")

    # Хешируем пароль
    hashed_password = get_password_hash(password)

    # Подтверждённый email → is_email_confirmed = True
    attributes = {
        "role": role,
        "is_email_confirmed": True,
        "services": {}
    }

    new_user = User(
        email=email,
        password_hash=hashed_password,
        first_name=first_name,
        last_name=last_name,
        attributes=attributes,
        is_active=True,
        deleted_at=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return {
            "msg": "Пользователь успешно создан",
            "user": {
                "id": new_user.id,
                "email": new_user.email,
                "first_name": new_user.first_name,
                "last_name": new_user.last_name,
                "role": attributes["role"],
                "status": "active"
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Ошибка при создании пользователя: {str(e)}")

# === 3. Импорт underground-пользователей из CSV ===
@router.post("/underground/import")
async def import_underground(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    content = await file.read()
    try:
        text = content.decode("utf-8")
        users_data = parse_csv_users(text)
    except Exception as e:
        raise HTTPException(400, f"Invalid CSV format: {str(e)}")

    imported = []
    failed = []

    for data in users_data:
        if db.query(User).filter(User.email == data["email"], User.deleted_at.is_(None)).first():
            failed.append({"email": data["email"], "error": "already exists"})
            continue

        user = create_underground_user(**data)
        try:
            db.add(user)
            db.commit()
            db.refresh(user)
            imported.append(user.email)
        except Exception:
            db.rollback()
            failed.append({"email": data["email"], "error": "save failed"})

    return {
        "msg": "Import completed",
        "imported": len(imported),
        "failed": failed
    }

class PermissionUpdateRequest(BaseModel):
    permissions: Dict[str, Dict[str, bool]]  # Например: {"docflow": {"read": true, "write": false}}


@router.post("/users/{user_id}/permissions")
def update_permissions(
    user_id: int,
    request: PermissionUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    print(f" Обновление прав для user_id={user_id}")

    # 1. Найти пользователя
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(404, "User not found")

    # 2. Проверка на "underground"
    attrs = user.attributes or {}
    if not isinstance(attrs, dict):
        attrs = {}

    if attrs.get("is_underground"):
        raise HTTPException(403, "Cannot modify permissions of underground user")

    # 3. Получить текущие права из services
    current_services = attrs.get("services", {})
    if not isinstance(current_services, dict):
        current_services = {}

    print(f" Текущие services: {current_services}")
    print(f" Новые permissions: {request.permissions}")

    #  Починка: если есть артефакт 'permissions' → извлечь данные и удалить
    if "permissions" in attrs:
        print(" Обнаружен устаревший ключ 'permissions', мигрируем...")
        nested_perms = attrs["permissions"]
        if isinstance(nested_perms, dict):
            for service_name, flags in nested_perms.items():
                if isinstance(flags, dict):
                    perms_list = [perm for perm, enabled in flags.items() if enabled]
                    if perms_list:
                        existing = current_services.get(service_name, [])
                        if isinstance(existing, list):
                            current_services[service_name] = list(set(existing + perms_list))
                        else:
                            current_services[service_name] = perms_list
        attrs.pop("permissions", None)  

    # 4. Объединение: добавляем и удаляем права по флагам
    merged_services = {}
    all_services = set(current_services.keys()) | set(request.permissions.keys())

    for service in all_services:
        # Старые права
        old_perms = current_services.get(service, [])
        if not isinstance(old_perms, list):
            old_perms = [str(old_perms)] if old_perms else []

        # Новые флаги
        flags = request.permissions.get(service, {})

        # Что нужно добавить / удалить
        perms_to_add = [perm for perm, enabled in flags.items() if enabled]
        perms_to_remove = [perm for perm, enabled in flags.items() if not enabled]

        # Удаляем отключённые права
        filtered_perms = [p for p in old_perms if p not in perms_to_remove]
        # Добавляем включённые
        combined = list(set(filtered_perms + perms_to_add))

        # Сохраняем только если есть права
        if combined:
            merged_services[service] = combined
        # Если нет — сервис не попадает в результат (удаляется)

    print(f" Результат слияния: {merged_services}")

    # 5. Формируем новые атрибуты
    new_attrs = {**attrs, "services": merged_services}

    # Проверка сериализуемости
    try:
        import json
        json.dumps(new_attrs)
    except TypeError as e:
        print(f" Невозможно сериализовать attributes: {e}")
        raise HTTPException(500, "Invalid data in attributes")

    # Присваиваем и помечаем изменение
    user.attributes = new_attrs
    flag_modified(user, "attributes")  

    # Сохраняем в БД
    try:
        db.commit()
        db.refresh(user) 
        print(" Успешно сохранено в БД")
    except Exception as e:
        db.rollback()
        print(f" ОШИБКА при коммите: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            500,
            f"Failed to update permissions: {type(e).__name__}: {str(e)}"
        )

    return {
        "msg": "Permissions updated successfully",
        "services_before": current_services,
        "services_after": merged_services,
        "user_id": user_id,
        "attributes_saved": new_attrs
    }
# === 5. Удалить пользователя (soft delete) ===
@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    confirm: bool = Query(False),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    print("\n" + "="*50)
    print(" УДАЛЕНИЕ ПОЛЬЗОВАТЕЛЯ")
    print("="*50)
    print(f"User ID: {user_id}")
    print(f"Confirm (query param): {confirm} (type: {type(confirm)})")

    if not confirm:
        print(" ОШИБКА: confirm не равен true")
        raise HTTPException(400, "Query param 'confirm=true' required")

    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()

    if not user:
        print(f" Пользователь с id={user_id} не найден или уже удалён")
        raise HTTPException(404, "User not found")

    # Устанавливаем deleted_at и is_active = False
    user.deleted_at = datetime.now(timezone.utc)
    user.is_active = False

    db.commit()
    db.refresh(user)

    print(f" Пользователь {user.email} помечен как удалённый и деактивирован")
    return {"msg": "User marked as deleted and deactivated"}

    return {"msg": "User marked as deleted"}
# === 6. Восстановить пользователя ===
@router.post("/users/{user_id}/restore")
def restore_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    # Ищем пользователя, который был soft-deleted
    user = db.query(User).filter(User.id == user_id, User.deleted_at.isnot(None)).first()

    if not user:
        raise HTTPException(404, "User not found in trash")

    # Снимаем флаг удаления и делаем активным
    user.deleted_at = None
    user.is_active = True

    db.commit()
    db.refresh(user)

    return {
        "msg": "User restored and reactivated",
        "user": {
            "id": user.id,
            "email": user.email,
            "is_active": user.is_active,
            "deleted_at": user.deleted_at
        }
    }

# === 7. Корзина (удалённые пользователи) ===
@router.get("/trash")
def list_trash(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    users = db.query(User).filter(User.deleted_at.isnot(None)).all()
    return {
        "deleted_users": [
            {"id": u.id, "email": u.email, "deleted_at": u.deleted_at} for u in users
        ]
    }
# === 8. Окончательно удалить пользователя из корзины (hard delete) ===
@router.delete("/trash/{user_id}")
def hard_delete_user(
    user_id: int,
    confirm: bool = Query(...),  
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Query parameter 'confirm=true' is required for permanent deletion"
        )

    # Ищем пользователя только среди тех, что в корзине (soft-deleted)
    user = db.query(User).filter(User.id == user_id, User.deleted_at.isnot(None)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found in trash")

    try:
       
        db.delete(user)
        db.commit()

        return {"msg": f"User '{user.email}' and all related data have been permanently deleted."}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred during deletion: {str(e)}"
        )
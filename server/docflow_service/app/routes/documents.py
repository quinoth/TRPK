# routes/documents.py
import os
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, BackgroundTasks
from sqlalchemy.orm import Session
from app.models.document import Document 
from shared.models.user import User
from app.core.security import get_current_user, has_permission
from app.utils.database import get_db
from app.services.event_producer import send_event

# Настройка хранилища
UPLOAD_DIR = Path("uploads/files")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Роутер
router = APIRouter(prefix="/api/docs", tags=["Documents"])


@router.post("/upload")
async def upload_file(  # ← async!
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not has_permission(current_user.attributes, "storage", "write"):
        raise HTTPException(403, "Нет прав на загрузку файлов (storage.write)")

    MAX_SIZE = 10 * 1024 * 1024
    content_bytes = await file.read(MAX_SIZE + 1)  # ← await!
    if len(content_bytes) > MAX_SIZE:
        raise HTTPException(400, "Файл слишком большой (максимум 10 МБ)")

    ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
    safe_name = f"{uuid.uuid4().hex}.{ext}"
    file_path = UPLOAD_DIR / safe_name

    with open(file_path, "wb") as f:
        f.write(content_bytes)

    doc = Document(
        title=file.filename,
        file_path=safe_name,
        file_size=len(content_bytes),
        content_type=file.content_type or "application/octet-stream",
        created_by_id=current_user.id,
        is_signed=False,
        signed_by_id=None,
        signed_at=None,
        deleted_at=None
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

  
    asyncio.create_task(send_event("document_created", {
        "id": doc.id,
        "title": doc.title,
        "user": current_user.email
    }))

    return {
        "msg": "Файл успешно загружен",
        "document_id": doc.id,
        "download_url": f"/api/docs/download/{doc.id}"
    }



# --- Скачать файл ---
@router.get("/download/{doc_id}")
def download_file(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not has_permission(current_user.attributes, "storage", "read"):
        raise HTTPException(403, "Нет прав на чтение файлов (storage.read)")

    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Файл не найден")

    if doc.deleted_at is not None:
        raise HTTPException(404, "Файл удалён")

    file_location = UPLOAD_DIR / doc.file_path
    if not file_location.exists():
        raise HTTPException(500, "Файл отсутствует на сервере")

    from fastapi.responses import FileResponse
    return FileResponse(
        path=file_location,
        filename=doc.title,
        media_type=doc.content_type or "application/octet-stream"
    )


# --- Поиск по названию ---
@router.get("/search")
def search(
    request: Request,
    q: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    print("\n" + "="*50)
    print(" DEBUG: /api/docs/search")
    print("="*50)
    print(f"Query: '{q}'")
    print(f"User: {current_user.email}")

    if not has_permission(current_user.attributes, "storage", "read"):
        raise HTTPException(403, "Нет прав на просмотр файлов")

    query = db.query(Document).filter(Document.deleted_at.is_(None))

    if q.strip():
        query = query.filter(Document.title.ilike(f"%{q}%"))

    docs = query.all()

    return {"results": [
        {
            "id": d.id,
            "title": d.title,
            "file_size": d.file_size,
            "content_type": d.content_type,
            "is_signed": d.is_signed,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "signed_at": d.signed_at.isoformat() if d.signed_at else None,
            "signed_by_id": d.signed_by_id
        }
        for d in docs
    ]}


# --- Подписать файл ---
@router.post("/sign/{doc_id}")
def sign_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = None
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Файл не найден")
    if doc.is_signed:
        raise HTTPException(400, "Файл уже подписан")

    doc.is_signed = True
    doc.signed_by_id = current_user.id
    doc.signed_at = datetime.utcnow()
    db.commit()

    
    if background_tasks:
        background_tasks.add_task(
            send_event,
            "document_signed",
            {
                "id": doc.id,
                "title": doc.title,
                "signed_by": current_user.email
            }
        )

    return {"msg": "Файл подписан"}
# --- Мягкое удаление (в корзину) ---
@router.delete("/{doc_id}")
def soft_delete(
    doc_id: int,
    confirm: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not confirm:
        raise HTTPException(400, "Требуется confirm=true")

    if not has_permission(current_user.attributes, "storage", "delete"):
        raise HTTPException(403, "Нет прав на удаление файлов")

    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.deleted_at.is_(None)
    ).first()

    if not doc:
        raise HTTPException(404, "Файл не найден или уже удалён")

    # Проверка: владелец или админ
    user_role = current_user.attributes.get("role", "user")
    if doc.created_by_id != current_user.id and user_role != "admin":
        raise HTTPException(403, "Можно удалять только свои файлы")

    doc.deleted_at = datetime.utcnow()
    db.commit()

    return {"msg": "Файл перемещён в корзину"}


# --- Просмотр корзины ---
@router.get("/trash")
def list_trash(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not has_permission(current_user.attributes, "storage", "delete"):
        raise HTTPException(403, "Нет прав на просмотр корзины")

    docs = db.query(Document).filter(Document.deleted_at.isnot(None)).all()

    return {
        "trash": [
            {
                "id": d.id,
                "title": d.title,
                "file_size": d.file_size,
                "deleted_at": d.deleted_at.isoformat() if d.deleted_at else None,
                "created_by_id": d.created_by_id
            }
            for d in docs
        ]
    }


# --- Окончательное удаление из корзины ---
@router.delete("/trash/{doc_id}")
def permanent_delete(
    doc_id: int,
    confirm: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not confirm:
        raise HTTPException(400, "Требуется confirm=true")

    if not has_permission(current_user.attributes, "storage", "delete"):
        raise HTTPException(403, "Нет прав на окончательное удаление")

    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.deleted_at.isnot(None)
    ).first()

    if not doc:
        raise HTTPException(404, "Файл не найден в корзине")

    # Удалить файл с диска
    file_location = UPLOAD_DIR / doc.file_path
    if file_location.exists():
        file_location.unlink(missing_ok=True)

    # Удалить запись
    db.delete(doc)
    db.commit()

    return {"msg": "Файл окончательно удалён"}

# --- Восстановление из корзины ---
@router.post("/restore/{doc_id}")
def restore_document(
    doc_id: int,
    confirm: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not confirm:
        raise HTTPException(400, "Требуется confirm=true")

    if not has_permission(current_user.attributes, "storage", "write"):
        raise HTTPException(403, "Нет прав на восстановление файлов")

    doc = db.query(Document).filter(
        Document.id == doc_id,
        Document.deleted_at.isnot(None)  
    ).first()

    if not doc:
        raise HTTPException(404, "Файл не найден в корзине")

    # Проверка: владелец или админ
    user_role = current_user.attributes.get("role", "user")
    if doc.created_by_id != current_user.id and user_role != "admin":
        raise HTTPException(403, "Можно восстанавливать только свои файлы")

    # Снимаем метку удаления
    doc.deleted_at = None
    db.commit()

    return {"msg": "Файл восстановлен из корзины"}
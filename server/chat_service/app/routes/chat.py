

from datetime import datetime
from typing import List, Optional
from sqlalchemy import func

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Request, Body
from sqlalchemy.orm import Session
from app.schemas.chat import CreateChatRequest  
from shared.models.user import User
from app.models.chat import Message, ChatGroup, GroupMember
from app.core.security import get_current_user
from app.utils.database import get_db, get_db_context
from app.sockets.manager import manager
import asyncio
import json
import logging
from app.utils.utils import get_user_from_token




 


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Chat"])


# === WebSocket: Подключение по токену ===
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    user_data = None
    try:
        await websocket.accept()

        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=1008, reason="Token not provided")
            return

        with get_db_context() as db:
            user = get_user_from_token(token, db)
            if not user:
                await websocket.close(code=1008, reason="Invalid token")
                return

            services = getattr(user, "attributes", {}) or {}
            chat_perms = services.get("services", {}).get("chat", {})
            if not chat_perms.get("read", False):
                await websocket.close(code=4403, reason="No read permission")
                return

            user_data = {"id": user.id}

        await manager.connect(websocket, user_data["id"])
        print(f" Пользователь {user_data['id']} подключён к WebSocket")

        #  Бесконечный цикл с нормальным поведением
        while True:
            try:
                # Ждём сообщение до 20 секунд (можно дольше)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=20.0)
                # Можно обработать команду: typing, send_message и т.д.
                print(f" Получено: {data}")
            except asyncio.TimeoutError:
                # Отправь ping или просто продолжай ждать
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break  # Если не удалось отправить — клиент отключился
                continue
            except WebSocketDisconnect:
                break

    except Exception as e:
        print(f" Ошибка: {e}")
    finally:
        if user_data:
            manager.disconnect(user_data["id"])
        print(" WebSocket соединение закрыто")


# === Получить только пользователей с доступом к чату ===
@router.get("/users")
def get_chat_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    print(f" [GET /users] Запрос от пользователя: {current_user.email} (ID={current_user.id})")

    users = db.query(User).all()
    print(f" Найдено пользователей в БД: {len(users)}")

    result = []
    for u in users:
        attrs = getattr(u, "attributes", {}) or {}
        print(f" Атрибуты пользователя {u.email}: {attrs}")

        perms = attrs.get("services", {})
        print(f"  services: {perms}")

        chat_perms = perms.get("chat", {})
        has_access = chat_perms.get("read", False)
        print(f" {u.email} -> chat.read: {has_access}")

        if has_access:
            full_name = getattr(u, "full_name", "") or u.email.split("@")[0].title()
            result.append({
                "id": u.id,
                "email": u.email,
                "full_name": full_name
            })

    print(f" Возвращаемых пользователей с доступом к чату: {len(result)}")
    return result
@router.post("/create-chat")
def create_chat(
    request_body: CreateChatRequest,  # ← получаем весь body как модель
    db: Session = Depends(get_db),
    creator: User = Depends(get_current_user)
):
    logger.info("===========================================")
    logger.info(" ПОЛУЧЕН ЗАПРОС НА СОЗДАНИЕ ЧАТА")
    logger.info(f"Тело запроса: {request_body.model_dump()}")
    logger.info(f"Автор: {creator.email} (ID={creator.id})")
 
    # Проверка прав (services, а не permissions!)
    services = getattr(creator, "attributes", {}) or {}
    chat_perms = services.get("services", {}).get("chat", {})
    if not chat_perms.get("write", False):
        logger.warning(f" У пользователя {creator.email} нет прав на создание чата")
        raise HTTPException(403, "Нет прав на создание чата")

    member_ids = request_body.member_ids.copy()

    if creator.id not in member_ids:
        member_ids.append(creator.id)

    if len(member_ids) < 2:
        raise HTTPException(400, "Чат должен быть минимум из двух участников")

    # Проверяем существование диалога (если 2 человека)
    if len(member_ids) == 2:
        existing = (
            db.query(ChatGroup)
            .join(GroupMember)
            .filter(GroupMember.user_id.in_(member_ids))
            .group_by(ChatGroup.id)
            .having(func.count(GroupMember.id) >= 2)
            .first()
        )
        if existing:
            logger.info(f" Диалог уже существует: group_id={existing.id}")
            return {"msg": "Диалог уже существует", "group_id": existing.id}

    # Создаём группу
    name = request_body.name or ("Диалог" if len(member_ids) == 2 else "Новая группа")

    group = ChatGroup(
        name=name,
        created_by_id=creator.id,
        created_at=datetime.utcnow()
    )
    db.add(group)
    db.flush()

    for uid in member_ids:
        user = db.query(User).get(uid)
        if not user:
            db.rollback()
            raise HTTPException(404, f"Пользователь {uid} не найден")

        # Проверяем доступ к чату
        user_services = getattr(user, "attributes", {}) or {}
        user_chat_perms = user_services.get("services", {}).get("chat", {})
        if not user_chat_perms.get("read", False):
            db.rollback()
            raise HTTPException(400, f"Пользователь {user.email} не имеет доступа к чату")

        member = GroupMember(group_id=group.id, user_id=uid, joined_at=datetime.utcnow())
        db.add(member)
        manager.add_to_group(group.id, uid)

    db.commit()
    logger.info(f" Группа создана: ID={group.id}, название='{name}'")
    return {"msg": "Чат создан", "group_id": group.id}

# === Отправить сообщение в чат ===
@router.post("/group/{group_id}/message")
async def send_message(
    group_id: int,
    content: str = Body(..., embed=True),  # ← embed=True: ожидаем {"content": "..."}
    file_url: str = Body(None, embed=True),  # ← тоже из body
    db: Session = Depends(get_db),
    sender: User = Depends(get_current_user)
):
    logger.info("===========================================")
    logger.info(" ПОЛУЧЕН ЗАПРОС НА ОТПРАВКУ СООБЩЕНИЯ")
    logger.info(f"Group ID: {group_id}")
    logger.info(f"Sender: {sender.email} (ID={sender.id})")
    logger.info(f"Raw content: {repr(content)}")
    logger.info(f"File URL: {file_url}")

    # Очистка и ограничение
    content = content.strip()[:1000]
    if not content and not file_url:
        logger.warning(" Сообщение пустое: нет текста и файла")
        raise HTTPException(400, "Сообщение пустое")

    # Проверяем, состоит ли пользователь в группе
    try:
        member = db.query(GroupMember).filter_by(group_id=group_id, user_id=sender.id).first()
        if not member:
            logger.warning(f" Пользователь {sender.id} не состоит в группе {group_id}")
            raise HTTPException(403, "Вы не состоите в этом чате")

        # Создаём сообщение
        msg = Message(
            content=content,
            sender_id=sender.id,
            group_id=group_id,
            file_url=file_url,
            sent_at=datetime.utcnow()
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)  # чтобы получить id и время из БД

        logger.info(f" Сообщение сохранено: ID={msg.id}, content='{content[:50]}...'")

        # Подготавливаем payload для рассылки
        payload = {
            "type": "message",
            "group_id": group_id,
            "from": sender.id,
            "from_email": sender.email,
            "from_name": getattr(sender, "full_name", sender.email),
            "content": content,
            "file_url": file_url,
            "sent_at": msg.sent_at.isoformat(),
            "id": msg.id
        }

        # Отправляем через менеджер (асинхронно)
        try:
            asyncio.create_task(manager.send_group_message(payload, group_id))
            logger.info(f"📤 Сообщение отправлено в группу {group_id}")
        except Exception as e:
            logger.error(f" Не удалось отправить сообщение через WebSocket: {e}")

        return {"msg": "Сообщение отправлено", "id": msg.id}

    except Exception as e:
        db.rollback()
        logger.error(f" Ошибка при отправке сообщения: {e}")
        raise

# === Получить историю чата ===
@router.get("/history/group/{group_id}")
def get_history(
    group_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not db.query(GroupMember).filter_by(group_id=group_id, user_id=user.id).first():
        raise HTTPException(403, "Вы не состоите в этом чате")

    messages = (
        db.query(Message)
        .filter(Message.group_id == group_id)
        .order_by(Message.sent_at.desc())
        .limit(limit)
        .all()
    )

    result = []
    for m in reversed(messages):
        sender = db.query(User).get(m.sender_id)
        result.append({
            "from": sender.id,
            "from_email": sender.email,
            "from_name": getattr(sender, "full_name", sender.email),
            "content": m.content,
            "file_url": m.file_url,
            "sent_at": m.sent_at.isoformat()
        })

    return {"messages": result}

@router.get("/groups")
def get_groups(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    groups = (
        db.query(ChatGroup)
        .join(GroupMember)
        .filter(GroupMember.user_id == current_user.id)
        .all()
    )
    return groups

# === Архивировать чат (только создатель) ===
@router.post("/group/{group_id}/archive")
def archive_chat(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logger.info(f"📦 Пользователь {current_user.email} пытается архивировать чат {group_id}")

    group = db.query(ChatGroup).filter(ChatGroup.id == group_id).first()
    if not group:
        raise HTTPException(404, "Чат не найден")

    # Проверка: пользователь — создатель
    if group.created_by_id != current_user.id:
        logger.warning(f" Пользователь {current_user.id} не является создателем чата {group_id}")
        raise HTTPException(403, "Только создатель может архивировать чат")

    # Уже архивирован?
    if group.is_archived:
        return {"msg": "Чат уже архивирован"}

    group.is_archived = True
    group.archived_at = datetime.utcnow()
    db.commit()

    logger.info(f" Чат {group_id} успешно архивирован пользователем {current_user.id}")
    return {"msg": "Чат успешно архивирован"}


@router.post("/group/{group_id}/unarchive")
def unarchive_chat(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logger.info(f" Пользователь {current_user.email} пытается разархивировать чат {group_id}")

    # Получаем группу
    group = db.query(ChatGroup).filter(ChatGroup.id == group_id).first()
    if not group:
        raise HTTPException(404, "Чат не найден")

    if not group.is_archived:
        return {"msg": "Чат не архивирован"}

    # Парсим attributes (безопасно, поддерживая JSONB и строки)
    user_attrs = getattr(current_user, "attributes", {}) or {}
    if isinstance(user_attrs, str):
        try:
            user_attrs = json.loads(user_attrs)
        except (json.JSONDecodeError, TypeError):
            user_attrs = {}

    services = user_attrs.get("services", {})
    has_admin_write = services.get("admin", {}).get("write", False)

    # Разрешаем, если: админ с write или создатель чата
    if not (has_admin_write or group.created_by_id == current_user.id):
        logger.warning(
            f" Пользователь {current_user.email} "
            f"(ID={current_user.id}) не может разархивировать чат {group_id}: "
            f"нет admin.write и не является создателем"
        )
        raise HTTPException(
            403,
            "Разархивировать может только администратор (services.admin.write) или создатель чата"
        )

    # Выполняем разархивацию
    group.is_archived = False
    group.archived_at = None
    db.commit()

    logger.info(f" Чат {group_id} разархивирован пользователем {current_user.id}")
    return {"msg": "Чат успешно разархивирован"}
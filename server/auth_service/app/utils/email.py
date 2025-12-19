import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime  

from events.producer import send_event


def send_confirmation_code_sync(email: str, code: str):
    smtp_host = "localhost"
    smtp_port = 25
    from_email = os.getenv("EMAIL_FROM", "noreply@localhost")

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = email
    msg["Subject"] = "Код подтверждения"

    body = f"Ваш код подтверждения: {code}\n\nОн действителен 15 минут."
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.send_message(msg)
        server.quit()

        print(f" Письмо с кодом отправлено на {email}")

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.create_task(send_event("email_events", {
            "type": "send_confirmation_code",
            "to": email,
            "code": code,
            "template": "confirm_registration"
        }))

    except Exception as e:
        print(f" Ошибка отправки письма: {e}")
        raise


async def send_reset_link(email: str, token: str):
    reset_link = f"http://localhost:3000/reset-password?token={token}"
    smtp_host = "localhost"
    smtp_port = 25
    from_email = os.getenv("EMAIL_FROM", "noreply@localhost")

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = email
    msg["Subject"] = "Сброс пароля"

    body = f"""
Чтобы сбросить пароль, перейдите по ссылке:
{reset_link}

Ссылка действительна 15 минут.

Если вы не запрашивали сброс — проигнорируйте это письмо.
"""
    msg.attach(MIMEText(body.strip(), "plain"))

    try:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.send_message(msg)
        server.quit()
        print(f" Ссылка для сброса отправлена на {email}")

        await send_event("email_events", {
            "type": "password_reset_requested",
            "to": email,
            "link": reset_link
        })
    except Exception as e:
        print(f" Ошибка отправки письма: {e}")


def update_profile(user, **kwargs):
    """
    Обновляет профиль пользователя: first_name, last_name, phone, bio, organization.
    """
    fields = ['first_name', 'last_name', 'phone', 'bio', 'organization']
    for field in fields:
        if field in kwargs and kwargs[field] is not None:
            setattr(user, field, kwargs[field])
    user.updated_at = datetime.utcnow()  
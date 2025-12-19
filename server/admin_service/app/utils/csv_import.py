import csv
from io import StringIO
from typing import List
from shared.models.user import User
from app.utils.database import get_password_hash

def parse_csv_users(csv_content: str) -> List[dict]:
    users = []
    f = StringIO(csv_content)
    reader = csv.DictReader(f)
    for row in reader:
        email = row["email"].strip()
        password = row["password"]
        first_name = row.get("first_name", "").strip()
        last_name = row.get("last_name", "").strip()
        if email and password:
            users.append({
                "email": email,
                "password": password,
                "first_name": first_name or None,
                "last_name": last_name or None
            })
    return users

def create_underground_user(email: str, password: str, first_name: str = None, last_name: str = None):
    return User(
        email=email,
        password_hash=get_password_hash(password),
        first_name=first_name,
        last_name=last_name,
        attributes={
            "role": "underground",
            "services": {
                "storage": {"read": True},
                "auth": {"read": True}
            },
            "is_email_confirmed": True,
            "is_underground": True
        }
    )